import json
import asyncio
import logging
from typing import Optional, Dict, Any, Type
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

def is_retryable_exception(exc: BaseException) -> bool:
    # Do not retry on connection refused - daemon is not running!
    if isinstance(exc, httpx.ConnectError):
        return False
    return isinstance(exc, (httpx.HTTPStatusError, TimeoutError))

_GROQ_SEMAPHORE = asyncio.Semaphore(2)

class LLMClient:
    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.model = settings.LLM_MODEL
        self.timeout = settings.LLM_TIMEOUT_SECONDS
        self.max_retries = settings.LLM_MAX_RETRIES

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

        # Append resilient alternates
        for alt, has_creds in [
            ("groq", bool(groq_key)),
            ("gemini", bool(settings.GEMINI_API_KEY)),
            ("openai", bool(settings.OPENAI_API_KEY and not settings.OPENAI_API_KEY.startswith("gsk_"))),
            ("anthropic", bool(settings.ANTHROPIC_API_KEY)),
            ("ollama", True),
        ]:
            if has_creds and alt not in providers_to_try:
                providers_to_try.append(alt)

        last_err = None
        for prov in providers_to_try:
            try:
                if prov == "groq":
                    return await self._call_groq(prompt, system_prompt, json_mode)
                elif prov == "gemini":
                    return await self._call_gemini(prompt, system_prompt, json_mode)
                elif prov == "anthropic":
                    return await self._call_anthropic(prompt, system_prompt, json_mode)
                elif prov == "openai":
                    return await self._call_openai(prompt, system_prompt, json_mode)
                elif prov == "ollama":
                    return await self._call_ollama(prompt, system_prompt, json_mode)
            except Exception as e:
                logger.warning(f"LLM provider '{prov}' failed ({e}). Checking backup provider...")
                last_err = e
                continue

        if last_err:
            raise last_err
        raise LLMGenerationError("No LLM provider available.")

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

        candidate_models = ["openai/gpt-oss-20b", "qwen/qwen3.6-27b", "openai/gpt-oss-120b"]
        if self.model and self.model in candidate_models:
            candidate_models.remove(self.model)
            candidate_models.insert(0, self.model)
        elif self.model:
            candidate_models.insert(0, self.model)

        last_error = None
        async with _GROQ_SEMAPHORE:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                for model in candidate_models:
                    payload: Dict[str, Any] = {
                        "model": model,
                        "messages": messages,
                        "temperature": 0.1
                    }
                    if json_mode:
                        payload["response_format"] = {"type": "json_object"}

                    for attempt in range(2):
                        try:
                            response = await client.post(url, headers=headers, json=payload)
                            if response.status_code == 429:
                                logger.info(f"Groq rate limit on '{model}' — backing off 1.5s before retry/failover...")
                                await asyncio.sleep(1.5)
                                last_error = httpx.HTTPStatusError("Groq Rate Limit Exceeded", request=response.request, response=response)
                                break
                            response.raise_for_status()
                            data = response.json()
                            return data["choices"][0]["message"]["content"]
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
        # Google Generative AI REST API endpoint
        model = self.model
        if not model or not model.startswith("gemini"):
            model = "gemini-2.0-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={settings.GEMINI_API_KEY}"
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"System Instructions: {system_prompt}"}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {"contents": contents}
        if json_mode:
            payload["generationConfig"] = {"responseMimeType": "application/json"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            res_json = response.json()
            candidates = res_json.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "")
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
        try:
            parsed = json.loads(raw_res)
            return schema.model_validate(parsed)
        except Exception as e:
            logger.warning(f"Failed to parse structured response on first attempt: {e}. Retrying with repair.")
            repair_prompt = (
                f"The following output was expected to conform to schema:\n{schema_json}\n\n"
                f"Actual output was:\n{raw_res}\n\n"
                f"Fix any syntax errors and return ONLY valid JSON matching the schema."
            )
            repaired_res = await self.generate_text(repair_prompt, system_prompt=system_prompt, json_mode=True)
            try:
                parsed_repaired = json.loads(repaired_res)
                return schema.model_validate(parsed_repaired)
            except Exception as final_err:
                raise LLMGenerationError(f"Failed to validate response against schema {schema.__name__}: {final_err}")

llm_client = LLMClient()
