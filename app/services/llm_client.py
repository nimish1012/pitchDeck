"""
LLM Client - Async OpenAI wrapper for the presentation generation pipeline.

Provides structured JSON output via multiple providers:
- OpenAI (default)
- Google (Gemini)
- vLLM (Local/Remote OpenAI-compatible endpoint)
"""

import json
import logging
from typing import Any, Dict, Optional, Type, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Async client wrapper for the presentation pipeline across multiple providers."""

    def __init__(self):
        self.provider = settings.llm_provider.lower()
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens

        # Initialize clients based on provider
        if self.provider == "openai":
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY is not set. Add it to your .env file.")
            self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
            
        elif self.provider == "vllm":
            # vLLM provides an OpenAI compatible endpoint
            self.openai_client = AsyncOpenAI(
                api_key="EMPTY", # vLLM often doesn't require an API key
                base_url=settings.vllm_api_base
            )
            
        elif self.provider == "google":
            if not settings.google_api_key:
                raise ValueError("GOOGLE_API_KEY is not set. Add it to your .env file.")
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.google_api_key)
                self.google_client = genai.GenerativeModel(self.model)
            except ImportError:
                raise ImportError("google-generativeai is required for Google provider. Install it using 'pip install google-generativeai'")
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    async def call_llm_json(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> T:
        """
        Make a chat completion call with JSON mode enabled.
        Parses the response into the given Pydantic model.
        """
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        try:
            return await self._call_provider_json(system_prompt, user_prompt, response_model, temp, tokens)
        except Exception as e:
            logger.warning(f"LLM JSON call failed with {self.provider}: {e}. Retrying once...")
            try:
                # Retry once
                return await self._call_provider_json(system_prompt, user_prompt, response_model, temp, tokens)
            except Exception as retry_err:
                logger.error(f"LLM JSON retry also failed: {retry_err}")
                raise

    async def _call_provider_json(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
        temperature: float,
        max_tokens: int,
    ) -> T:
        
        if self.provider in ["openai", "vllm"]:
            response = await self.openai_client.chat.completions.create(
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
            # Google API uses a different prompt structure and generation config
            import google.generativeai as genai
            
            prompt = f"{system_prompt}\n\n{user_prompt}"
            
            generation_config = genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                response_mime_type="application/json"
            )
            
            # Note: The official python SDK has an async generating method: `generate_content_async`
            response = await self.google_client.generate_content_async(
                contents=prompt,
                generation_config=generation_config
            )
            raw = response.text.strip()
            
        else:
            raise ValueError(f"Provider {self.provider} not implemented for JSON calls")
            
        parsed = json.loads(raw)
        return response_model.model_validate(parsed)


# Singleton instance — created lazily to avoid crash when key is missing
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create the singleton LLM client."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
