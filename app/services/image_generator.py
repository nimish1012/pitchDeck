"""
Image Generator — generates presentation-friendly images via a configurable
diffusion model backend (Replicate, Stability AI, DALL·E, or mock).

Each slide that has `image_required=True` gets an image prompt composed of:
  slide context + art style preset + "presentation-friendly" suffix

The generator runs concurrently with slide text generation.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class ImageGenerator:
    """Async image generation client."""

    def __init__(self):
        self.provider = settings.image_provider.lower()
        self.api_key = settings.image_api_key
        self.api_base = settings.image_api_base
        self.model = settings.image_default_model
        self.style_suffix = settings.image_default_style
        self.width = settings.image_width
        self.height = settings.image_height

    # ── Public API ─────────────────────────────

    async def generate(
        self,
        prompt: str,
        art_style_prompt: str = "",
        timeout: float = 60.0,
    ) -> Optional[str]:
        """
        Generate a single image.  Returns a URL string or None on failure.

        The final prompt sent to the model is:
          {prompt}. {art_style_prompt}. {self.style_suffix}
        """
        if self.provider == "none":
            logger.debug("Image generation disabled (provider=none)")
            return None

        full_prompt = f"{prompt}. {art_style_prompt}. {self.style_suffix}".strip(". ")

        try:
            if self.provider == "replicate":
                return await self._generate_replicate(full_prompt, timeout)
            elif self.provider == "stability":
                return await self._generate_stability(full_prompt, timeout)
            elif self.provider == "dalle":
                return await self._generate_dalle(full_prompt, timeout)
            else:
                logger.warning(f"Unknown image provider: {self.provider}")
                return None
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return None

    # ── Replicate ──────────────────────────────

    async def _generate_replicate(self, prompt: str, timeout: float) -> Optional[str]:
        """Call Replicate's HTTP API."""
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Start prediction
            resp = await client.post(
                "https://api.replicate.com/v1/predictions",
                headers={
                    "Authorization": f"Token {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "version": self.model,
                    "input": {
                        "prompt": prompt,
                        "width": self.width,
                        "height": self.height,
                    },
                },
            )
            resp.raise_for_status()
            prediction = resp.json()
            prediction_url = prediction.get("urls", {}).get("get")

            if not prediction_url:
                return None

            # Poll until completed
            for _ in range(60):
                poll = await client.get(
                    prediction_url,
                    headers={"Authorization": f"Token {self.api_key}"},
                )
                poll.raise_for_status()
                data = poll.json()
                status = data.get("status")

                if status == "succeeded":
                    output = data.get("output")
                    if isinstance(output, list) and output:
                        return output[0]
                    return output
                elif status == "failed":
                    logger.error(f"Replicate prediction failed: {data.get('error')}")
                    return None

                await asyncio.sleep(1)

        return None

    # ── Stability AI ───────────────────────────

    async def _generate_stability(self, prompt: str, timeout: float) -> Optional[str]:
        """Call Stability AI REST API."""
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{self.api_base or 'https://api.stability.ai'}/v1/generation/text-to-image",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "text_prompts": [{"text": prompt}],
                    "cfg_scale": 7,
                    "width": self.width,
                    "height": self.height,
                    "samples": 1,
                    "steps": 30,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            artifacts = data.get("artifacts", [])
            if artifacts:
                # Return base64-encoded image as data URI
                return f"data:image/png;base64,{artifacts[0]['base64']}"
        return None

    # ── DALL·E (via OpenAI) ────────────────────

    async def _generate_dalle(self, prompt: str, timeout: float) -> Optional[str]:
        """Call OpenAI DALL·E API."""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size=f"{self.width}x{self.height}",
            quality="standard",
        )
        if response.data:
            return response.data[0].url
        return None


# ── Singleton ──────────────────────────────────

_instance: Optional[ImageGenerator] = None


def get_image_generator() -> ImageGenerator:
    global _instance
    if _instance is None:
        _instance = ImageGenerator()
    return _instance
