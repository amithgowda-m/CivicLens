import json
import asyncio
import logging
import re
from typing import Optional, Dict, Any, Type, List
import httpx
from pydantic import BaseModel
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from backend.config import settings

logger = logging.getLogger("civiclens.llm_client")

class LLMGenerationError(Exception):
    pass

def sanitize_llm_output(text: str) -> str:
    """
    Strips internal model reasoning traces (<think>...</think>, <thought>...</thought>),
    scratchpads, and internal analysis headers that reasoning models (DeepSeek-R1, Qwen,
    GPT-OSS) output before their actual citizen-facing answer.
    """
    if not text or not isinstance(text, str):
        return ""

    # 1. Strip complete <think>...</think>, <thought>...</thought>, etc.
    cleaned = re.sub(r'<(think|thought|reasoning|scratchpad)[^>]*>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)

    # 2. Handle unclosed or truncated think blocks:
    if re.search(r'<(think|thought|reasoning|scratchpad)[^>]*>', cleaned, re.IGNORECASE):
        if re.search(r'</(think|thought|reasoning|scratchpad)>', cleaned, re.IGNORECASE):
            cleaned = re.split(r'</(?:think|thought|reasoning|scratchpad)>', cleaned, flags=re.IGNORECASE)[-1]
        else:
            # Check if there is a markdown transition like double newline followed by list or header
            m = re.search(r'\n\n(?=[-*\d#A-Z])', cleaned)
            if m:
                cleaned = cleaned[m.start():]
            else:
                cleaned = re.sub(r'<(think|thought|reasoning|scratchpad)[^>]*>.*', '', cleaned, flags=re.DOTALL | re.IGNORECASE)

    # 3. Strip any stray leftover tags
    cleaned = re.sub(r'</?(?:think|thought|reasoning|scratchpad)[^>]*>', '', cleaned, flags=re.IGNORECASE)

    # 4. Strip LLM meta-chatter headers if they appear at the top
    meta_patterns = [
        r"^(?:Here'?s a thinking process:?|Thinking Process:?|Thought Process:?|Internal reasoning:?)\s*",
        r"^(?:\.?\s*\*\*Analyze User Input:\*\*.*?(?=\n\n|\n-|\n\*|\n\d|\Z))",
        r"^(?:\*\*Role:\*\*.*?(?=\n\n|\n-|\n\*|\n\d|\Z))",
        r"^(?:\*\*Style:\*\*.*?(?=\n\n|\n-|\n\*|\n\d|\Z))",
        r"^(?:\*\*Task:\*\*.*?(?=\n\n|\n-|\n\*|\n\d|\Z))",
        r"^(?:\*\*Constraint:\*\*.*?(?=\n\n|\n-|\n\*|\n\d|\Z))",
        r"^(?:\*\*Input Clauses:\*\*.*?(?=\n\n|\n-|\n\*|\n\d|\Z))",
    ]
    for pat in meta_patterns:
        cleaned = re.sub(pat, '', cleaned, flags=re.DOTALL | re.IGNORECASE | re.MULTILINE)

    return cleaned.strip()

def is_retryable_exception(exc: BaseException) -> bool:
    # Do not retry on connection refused - daemon is not running!
    if isinstance(exc, httpx.ConnectError):
        return False
    return isinstance(exc, (httpx.HTTPStatusError, TimeoutError))

import time
from collections import deque

class PreemptiveRateLimiter:
    """
    Sliding-window rate limiter that pre-emptively paces requests BEFORE sending them.
    Prevents triggering 429 errors on Groq by pacing calls under the 30 RPM limit.
    """
    def __init__(self, max_requests: int = 28, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.timestamps: deque = deque()
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            while self.timestamps and self.timestamps[0] <= now - self.window_seconds:
                self.timestamps.popleft()

            if len(self.timestamps) >= self.max_requests:
                oldest = self.timestamps[0]
                wait_time = (oldest + self.window_seconds) - now + 0.1
                if wait_time > 0:
                    logger.info(f"[Pre-emptive Rate Limiter] Pacing request ({len(self.timestamps)}/{self.max_requests} in window). Waiting {wait_time:.2f}s...")
                    await asyncio.sleep(wait_time)
                    now = time.monotonic()
                    while self.timestamps and self.timestamps[0] <= now - self.window_seconds:
                        self.timestamps.popleft()

            self.timestamps.append(time.monotonic())

_GROQ_RATE_LIMITER = PreemptiveRateLimiter(max_requests=28, window_seconds=60.0)
_GEMINI_RATE_LIMITER = PreemptiveRateLimiter(max_requests=12, window_seconds=60.0)

_GEMINI_DISCOVERED_MODELS: Optional[List[str]] = None

async def _get_available_gemini_models() -> List[str]:
    global _GEMINI_DISCOVERED_MODELS
    if _GEMINI_DISCOVERED_MODELS:
        return _GEMINI_DISCOVERED_MODELS
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={settings.GEMINI_API_KEY}"
        async with httpx.AsyncClient(timeout=6.0) as client:
            res = await client.get(url)
            if res.status_code == 200:
                discovered = []
                for m in res.json().get("models", []):
                    if "generateContent" in m.get("supportedGenerationMethods", []):
                        name = m.get("name", "").replace("models/", "")
                        if "flash" in name or "pro" in name or "gemma" in name:
                            discovered.append(name)
                if discovered:
                    # Prioritize fast flash models over pro
                    discovered.sort(key=lambda x: (0 if "flash" in x else 1, 0 if "lite" in x else 1))
                    _GEMINI_DISCOVERED_MODELS = discovered
                    logger.info(f"[Gemini Model Discovery] Available models: {discovered[:5]}")
                    return discovered
    except Exception as err:
        logger.warning(f"Dynamic Gemini model discovery failed: {err}")
    # Live fallback aliases verified against Google API
    return ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite", "gemini-pro-latest"]

# Shared module-level singleton semaphore — limits concurrent LLM calls across ALL agents and
# batch pipelines to prevent API 429 rate-limit spikes. NEVER instantiate per-pipeline.
_GLOBAL_LLM_SEMAPHORE = asyncio.Semaphore(2)
# Legacy alias kept for any internal references
_GROQ_SEMAPHORE = _GLOBAL_LLM_SEMAPHORE

class LLMClient:
    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.model = settings.LLM_MODEL
        self.timeout = settings.LLM_TIMEOUT_SECONDS
        self.max_retries = settings.LLM_MAX_RETRIES
        # Expose the singleton semaphore on the instance so batch tasks can verify id() equality
        self.semaphore = _GLOBAL_LLM_SEMAPHORE
        self.call_count = 0

    def reset_metrics(self):
        self.call_count = 0

    def get_call_count(self) -> int:
        return self.call_count

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str = "",
        json_mode: bool = False,
        schema: Optional[Type[BaseModel]] = None
    ) -> str:
        """
        Unified generation method routing to the configured LLM backend.
        Supports automatic failover across Groq, Gemini, Anthropic, OpenAI, and Ollama.
        """
        self.call_count += 1
        groq_key = settings.GROQ_API_KEY or (settings.OPENAI_API_KEY if settings.OPENAI_API_KEY.startswith("gsk_") else "")
        providers_to_try = []

        # Determine primary provider
        primary = self.provider
        if primary in ("groq", "openai") and groq_key:
            providers_to_try.append("groq")
        elif primary == "gemini" and settings.GEMINI_API_KEY:
            providers_to_try.append("gemini")
        elif primary == "anthropic" and settings.ANTHROPIC_API_KEY:
            providers_to_try.append("anthropic")
        elif primary == "openai" and settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("gsk_"):
            providers_to_try.append("openai")
        elif primary == "ollama":
            providers_to_try.append("ollama")
        else:
            if groq_key:
                providers_to_try.append("groq")
            elif settings.GEMINI_API_KEY:
                providers_to_try.append("gemini")
            else:
                providers_to_try.append("ollama")

        # Append resilient alternates in priority order (gemini -> groq -> openai -> anthropic)
        for alt, has_creds in [
            ("gemini", bool(settings.GEMINI_API_KEY)),
            ("groq", bool(groq_key)),
            ("openai", bool(settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("gsk_"))),
            ("anthropic", bool(settings.ANTHROPIC_API_KEY)),
        ]:
            if has_creds and alt not in providers_to_try:
                providers_to_try.append(alt)

        last_err = None
        for prov in providers_to_try:
            try:
                raw_text = ""
                if prov == "groq":
                    raw_text = await self._call_groq(prompt, system_prompt, json_mode)
                elif prov == "gemini":
                    raw_text = await self._call_gemini(prompt, system_prompt, json_mode)
                elif prov == "anthropic":
                    raw_text = await self._call_anthropic(prompt, system_prompt, json_mode)
                elif prov == "openai":
                    raw_text = await self._call_openai(prompt, system_prompt, json_mode)
                elif prov == "ollama":
                    raw_text = await self._call_ollama(prompt, system_prompt, json_mode)
                return sanitize_llm_output(raw_text)
            except Exception as e:
                logger.warning(f"LLM provider '{prov}' failed ({e}). Checking backup provider...")
                last_err = e
                continue

        if last_err:
            logger.error(f"[LLM FAILOVER EXHAUSTED] All candidate providers ({providers_to_try}) failed. Last error: {last_err}")
            raise last_err
        raise LLMGenerationError(f"[LLM FAILOVER EXHAUSTED] No configured LLM provider available in {providers_to_try}.")

    async def _call_groq(self, prompt: str, system_prompt: str, json_mode: bool) -> str:
        api_key = settings.GROQ_API_KEY or (settings.OPENAI_API_KEY if settings.OPENAI_API_KEY.startswith("gsk_") else "")
        if not api_key:
            raise LLMGenerationError("No Groq API key available.")

        url = f"{settings.GROQ_BASE_URL.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Reliable high-capacity models first to prevent token limit errors
        candidate_models = [
            "openai/gpt-oss-120b",
            "qwen/qwen3.8-27b",
            "openai/gpt-oss-20b",
            "groq/compound",
        ]
        if self.model and self.model not in candidate_models and "gemini" not in self.model:
            candidate_models.insert(0, self.model)

        last_error = None
        # Pre-emptively pace request to stay under Groq 30 RPM limit BEFORE hitting the network
        await _GROQ_RATE_LIMITER.acquire()
        async with _GLOBAL_LLM_SEMAPHORE:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                for model in candidate_models:
                    model_messages = [dict(m) for m in messages]
                    payload: Dict[str, Any] = {
                        "model": model,
                        "messages": model_messages,
                        "temperature": 0.1,
                        "max_tokens": 1500,
                    }
                    if json_mode:
                        payload["response_format"] = {"type": "json_object"}
                        # Groq requires 'json' to be explicitly mentioned in messages when response_format is json_object
                        if not any("json" in m["content"].lower() for m in model_messages):
                            model_messages[-1]["content"] += "\nReturn valid JSON format."

                    # Exponential backoff: 1.5s → 3s → 6s before rotating to next model
                    backoff = 1.5
                    for attempt in range(3):
                        try:
                            response = await client.post(url, headers=headers, json=payload)
                            if response.status_code == 429:
                                wait = backoff * (2 ** attempt)
                                logger.info(f"Groq rate limit on '{model}' — backing off {wait:.1f}s (attempt {attempt+1}/3)...")
                                await asyncio.sleep(wait)
                                last_error = httpx.HTTPStatusError("Groq Rate Limit Exceeded", request=response.request, response=response)
                                if attempt == 2:
                                    break  # rotate to next model
                                continue
                            if response.status_code >= 400:
                                logger.warning(f"Groq error on '{model}': {response.status_code} - {response.text[:200]}")
                            response.raise_for_status()
                            data = response.json()
                            content = data["choices"][0]["message"]["content"]
                            return sanitize_llm_output(content)
                        except httpx.HTTPStatusError as err:
                            last_error = err
                            break
                        except Exception as err:
                            last_error = err
                            break
        if last_error:
            raise last_error
        raise LLMGenerationError("Groq requests failed.")

    async def _call_ollama(self, prompt: str, system_prompt: str, json_mode: bool) -> str:
        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate"
        model = self.model
        if not model or "gemini" in model or "gpt" in model or "claude" in model or "groq" in model:
            model = "llama3.1:8b"
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
        }
        if json_mode:
            payload["format"] = "json"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")

    async def _call_gemini(self, prompt: str, system_prompt: str, json_mode: bool) -> str:
        # Dynamic Gemini model discovery ensures we never failover to deprecated or nonexistent model IDs
        discovered = await _get_available_gemini_models()
        candidate_models = list(discovered)
        if self.model and self.model.startswith("gemini") and self.model in candidate_models:
            candidate_models.remove(self.model)
            candidate_models.insert(0, self.model)

        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"System Instructions: {system_prompt}"}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {"contents": contents}
        if json_mode:
            payload["generationConfig"] = {"responseMimeType": "application/json"}

        last_exc = None
        # Pre-emptively pace request to stay under Gemini free-tier RPM limit
        await _GEMINI_RATE_LIMITER.acquire()
        for model in candidate_models[:4]:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={settings.GEMINI_API_KEY}"
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, json=payload)
                    if response.status_code == 429:
                        logger.info(f"Gemini 429 on '{model}' — backing off 2.0s...")
                        await asyncio.sleep(2.0)
                    response.raise_for_status()
                    res_json = response.json()
                    candidates = res_json.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "")
                    return ""
            except httpx.HTTPStatusError as e:
                last_exc = e
                if e.response.status_code in (404, 503, 429):
                    # Model unavailable, deprecated or overloaded; try next candidate model
                    continue
                raise
            except Exception as e:
                last_exc = e
                continue

        if last_exc:
            raise last_exc
        return ""

    async def _call_anthropic(self, prompt: str, system_prompt: str, json_mode: bool) -> str:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = {
            "model": self.model or "claude-3-5-sonnet-20240620",
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}]
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            blocks = data.get("content", [])
            return blocks[0].get("text", "") if blocks else ""

    async def _call_openai(self, prompt: str, system_prompt: str, json_mode: bool) -> str:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model or "gpt-4o",
            "messages": messages
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[BaseModel],
        system_prompt: str = ""
    ) -> BaseModel:
        """
        Enforces structured output parsing with a retry-repair mechanism on json error.
        """
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        augmented_prompt = (
            f"{prompt}\n\nRespond strictly with valid JSON conforming to this JSON Schema:\n{schema_json}"
        )
        raw_res = await self.generate_text(augmented_prompt, system_prompt=system_prompt, json_mode=True)
        raw_res = sanitize_llm_output(raw_res)
        clean_json = re.sub(r'^```(?:json)?\s*', '', raw_res.strip(), flags=re.IGNORECASE)
        clean_json = re.sub(r'\s*```$', '', clean_json).strip()
        try:
            parsed = json.loads(clean_json)
            return schema.model_validate(parsed)
        except Exception as e:
            logger.warning(f"Failed to parse structured response on first attempt: {e}. Retrying with repair.")
            repair_prompt = (
                f"The following output was expected to conform to schema:\n{schema_json}\n\n"
                f"Actual output was:\n{clean_json}\n\n"
                f"Fix any syntax errors and return ONLY valid JSON matching the schema."
            )
            repaired_res = await self.generate_text(repair_prompt, system_prompt=system_prompt, json_mode=True)
            repaired_res = sanitize_llm_output(repaired_res)
            clean_repaired = re.sub(r'^```(?:json)?\s*', '', repaired_res.strip(), flags=re.IGNORECASE)
            clean_repaired = re.sub(r'\s*```$', '', clean_repaired).strip()
            try:
                parsed_repaired = json.loads(clean_repaired)
                return schema.model_validate(parsed_repaired)
            except Exception as final_err:
                raise LLMGenerationError(f"Failed to validate response against schema {schema.__name__}: {final_err}")

llm_client = LLMClient()
