"""
LLM Client — Async multi-provider wrapper with JSON mode + streaming.

Supports:
  • OpenAI  (default)
  • Google  (Gemini)
  • vLLM    (OpenAI-compatible endpoint)

New in v2:
  • Streaming support via call_llm_stream()
  • Exponential-backoff retry
  • Per-call max_tokens override (for token budgeting)
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Dict, Optional, Type, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Async LLM client for the presentation pipeline."""

    def __init__(self):
        self.provider = settings.llm_provider.lower()
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens

        if self.provider == "openai":
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY is not set.")
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)

        elif self.provider == "vllm":
            self.client = AsyncOpenAI(
                api_key="EMPTY",
                base_url=settings.vllm_api_base,
            )

        elif self.provider == "google":
            if not settings.google_api_key:
                raise ValueError("GOOGLE_API_KEY is not set.")
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.google_api_key)
                self.google_client = genai.GenerativeModel(self.model)
            except ImportError:
                raise ImportError("google-generativeai required for Google provider")
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  JSON mode call (structured output)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def call_llm_json(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> T:
        """Structured JSON call with automatic retry + backoff."""
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        last_err: Exception | None = None
        for attempt in range(1, settings.max_retries + 2):  # +1 for initial try
            try:
                return await self._call_json_inner(
                    system_prompt, user_prompt, response_model, temp, tokens,
                )
            except Exception as e:
                last_err = e
                if attempt <= settings.max_retries:
                    wait = settings.retry_backoff_base * (2 ** (attempt - 1))
                    logger.warning(
                        f"LLM call attempt {attempt} failed ({e}), "
                        f"retrying in {wait:.1f}s …"
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"LLM call failed after {attempt} attempts: {e}")

        raise last_err  # type: ignore[misc]

    async def _call_json_inner(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
        temperature: float,
        max_tokens: int,
    ) -> T:
        if self.provider in ("openai", "vllm"):
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content.strip()

        elif self.provider == "google":
            import google.generativeai as genai
            prompt = f"{system_prompt}\n\n{user_prompt}"
            gen_config = genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
            )
            response = await self.google_client.generate_content_async(
                contents=prompt,
                generation_config=gen_config,
            )
            raw = response.text.strip()
        else:
            raise ValueError(f"Provider {self.provider} not implemented")

        parsed = json.loads(raw)
        return response_model.model_validate(parsed)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  Streaming call (token-by-token)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def call_llm_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """
        Yield tokens as they arrive.  Only supported on OpenAI / vLLM.
        Useful for streaming partial slide content to the SSE endpoint.
        """
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        if self.provider not in ("openai", "vllm"):
            # Fallback: non-streaming call, yield all at once
            response = await self.call_llm_json(
                system_prompt, user_prompt, BaseModel, temp, tokens,
            )
            yield response.model_dump_json()
            return

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temp,
            max_tokens=tokens,
            response_format={"type": "json_object"},
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  Raw call (no parsing)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def call_llm_raw(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Return raw string response (no JSON parsing)."""
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        if self.provider in ("openai", "vllm"):
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temp,
                max_tokens=tokens,
            )
            return response.choices[0].message.content.strip()

        elif self.provider == "google":
            import google.generativeai as genai
            prompt = f"{system_prompt}\n\n{user_prompt}"
            gen_config = genai.GenerationConfig(
                temperature=temp,
                max_output_tokens=tokens,
            )
            response = await self.google_client.generate_content_async(
                contents=prompt,
                generation_config=gen_config,
            )
            return response.text.strip()

        raise ValueError(f"Provider {self.provider} not implemented")


# ── Singleton ──────────────────────────────────

_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create the singleton LLM client."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
