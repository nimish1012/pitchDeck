"""
State Manager — Redis-backed (with in-memory fallback) store for GenerationState.

Every pipeline stage reads/writes through this manager so the SSE stream can
push the latest snapshot at any time.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Dict, Optional

from app.core.config import settings
from app.models.schemas import GenerationState

logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  In-Memory Fallback Store
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_memory_store: Dict[str, str] = {}
_memory_lock = asyncio.Lock()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Redis helpers (lazy import)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_redis_pool = None


async def _get_redis():
    """Lazy-initialise and return an async Redis connection."""
    global _redis_pool
    if _redis_pool is None:
        try:
            import redis.asyncio as aioredis
            _redis_pool = aioredis.from_url(
                settings.redis_url,
                decode_responses=True,
                max_connections=20,
            )
            # Verify connectivity
            await _redis_pool.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.warning(f"Redis unavailable ({e}), falling back to in-memory store")
            _redis_pool = None
    return _redis_pool


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Public API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STATE_KEY_PREFIX = "gen:"
STATE_TTL = 3600 * 2  # 2 hours


class StateManager:
    """Read/write GenerationState to the backing store."""

    # ── Write ──────────────────────────────────

    @staticmethod
    async def save(state: GenerationState) -> None:
        """Persist the full GenerationState snapshot."""
        state.touch()
        payload = state.model_dump_json()
        key = f"{STATE_KEY_PREFIX}{state.generation_id}"

        if settings.use_redis:
            redis = await _get_redis()
            if redis is not None:
                await redis.set(key, payload, ex=STATE_TTL)
                return

        # Fallback: in-memory
        async with _memory_lock:
            _memory_store[key] = payload

    # ── Read ───────────────────────────────────

    @staticmethod
    async def load(generation_id: str) -> Optional[GenerationState]:
        """Load a GenerationState by ID.  Returns None if not found."""
        key = f"{STATE_KEY_PREFIX}{generation_id}"

        raw: Optional[str] = None

        if settings.use_redis:
            redis = await _get_redis()
            if redis is not None:
                raw = await redis.get(key)

        if raw is None:
            async with _memory_lock:
                raw = _memory_store.get(key)

        if raw is None:
            return None

        return GenerationState.model_validate_json(raw)

    # ── Delete ─────────────────────────────────

    @staticmethod
    async def delete(generation_id: str) -> None:
        key = f"{STATE_KEY_PREFIX}{generation_id}"

        if settings.use_redis:
            redis = await _get_redis()
            if redis is not None:
                await redis.delete(key)
                return

        async with _memory_lock:
            _memory_store.pop(key, None)

    # ── List active generations ────────────────

    @staticmethod
    async def list_active() -> list[str]:
        """Return generation IDs currently in the store."""
        prefix = STATE_KEY_PREFIX

        if settings.use_redis:
            redis = await _get_redis()
            if redis is not None:
                keys = await redis.keys(f"{prefix}*")
                return [k.replace(prefix, "") for k in keys]

        async with _memory_lock:
            return [k.replace(prefix, "") for k in _memory_store.keys()]
