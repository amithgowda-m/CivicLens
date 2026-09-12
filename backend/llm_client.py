import json
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

class LLMClient:
    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.model = settings.LLM_MODEL
        self.timeout = settings.LLM_TIMEOUT_SECONDS
        self.max_retries = settings.LLM_MAX_RETRIES

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    async def generate_text(
        self,
        prompt: str,
        system_prompt: str = "",
        json_mode: bool = False,
        schema: Optional[Type[BaseModel]] = None
    ) -> str:
        """
        Unified generation method routing to the configured LLM backend.
        Defaults to Ollama (offline local) if no external API key is set.
        """
        effective_provider = self.provider

        # Check credentials: If an API key is missing for hosted providers, fallback to ollama
        if effective_provider == "gemini" and not settings.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not found; falling back to ollama.")
            effective_provider = "ollama"
        elif effective_provider == "anthropic" and not settings.ANTHROPIC_API_KEY:
            logger.warning("ANTHROPIC_API_KEY not found; falling back to ollama.")
            effective_provider = "ollama"
        elif effective_provider == "openai" and not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not found; falling back to ollama.")
            effective_provider = "ollama"

        if effective_provider == "ollama":
            return await self._call_ollama(prompt, system_prompt, json_mode)
        elif effective_provider == "gemini":
            return await self._call_gemini(prompt, system_prompt, json_mode)
        elif effective_provider == "anthropic":
            return await self._call_anthropic(prompt, system_prompt, json_mode)
        elif effective_provider == "openai":
            return await self._call_openai(prompt, system_prompt, json_mode)
        else:
            return await self._call_ollama(prompt, system_prompt, json_mode)

    async def _call_ollama(self, prompt: str, system_prompt: str, json_mode: bool) -> str:
        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate"
        payload = {
            "model": self.model if self.model else "llama3.1:8b",
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
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model or 'gemini-1.5-flash'}:generateContent?key={settings.GEMINI_API_KEY}"
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
