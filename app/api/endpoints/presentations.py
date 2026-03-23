"""
Presentation API endpoints — Gamma-style with SSE streaming.

Endpoints:
  POST /generate          → Kick off generation, returns generation_id + stream URL
  GET  /generate/{id}/stream  → SSE stream of incremental updates
  GET  /generate/{id}     → Poll current state (non-streaming fallback)
  DELETE /generate/{id}   → Cancel / delete a generation
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.models.schemas import (
    GenerateRequest,
    GenerationCreatedResponse,
    GenerationState,
    GenerationStatus,
    GenerationStatusResponse,
    SSEEvent,
)
from app.services.pipeline import PresentationPipeline
from app.services.state_manager import StateManager

router = APIRouter()
logger = logging.getLogger(__name__)

# In-flight pipelines (so the SSE endpoint can attach to an active run)
_active_pipelines: dict[str, PresentationPipeline] = {}
_active_queues: dict[str, asyncio.Queue] = {}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  POST /generate — kick off a new generation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/generate", response_model=GenerationCreatedResponse)
async def start_generation(
    request: GenerateRequest,
    mode: str = Query("parallel", enum=["parallel", "sequential"]),
):
    """
    Accept a prompt + settings, create a GenerationState, start the pipeline
    in the background, and return immediately with a stream URL.

    Query params:
      mode: "sequential" (Gamma-style, one card at a time) or "parallel" (faster)
    """
    pipeline = PresentationPipeline(request, mode=mode)
    gen_id = pipeline.state.generation_id

    # Persist initial state
    await StateManager.save(pipeline.state)

    # Create an event queue so the SSE endpoint can consume events
    queue: asyncio.Queue[Optional[SSEEvent]] = asyncio.Queue()
    _active_pipelines[gen_id] = pipeline
    _active_queues[gen_id] = queue

    # Launch the pipeline in a background task
    asyncio.create_task(_run_pipeline(gen_id, pipeline, queue))

    logger.info(f"Generation {gen_id} started for prompt: {request.prompt[:80]}…")

    return GenerationCreatedResponse(
        generation_id=gen_id,
        status=GenerationStatus.PENDING,
        stream_url=f"/api/v1/generate/{gen_id}/stream",
        created_time=pipeline.state.created_time,
    )


async def _run_pipeline(
    gen_id: str,
    pipeline: PresentationPipeline,
    queue: asyncio.Queue,
) -> None:
    """Background coroutine that drives the pipeline and pushes events to the queue."""
    try:
        async for event in pipeline.run():
            await queue.put(event)
    except Exception as e:
        logger.exception(f"Pipeline {gen_id} crashed: {e}")
        await queue.put(SSEEvent(
            event="error",
            data={"error": str(e)},
            generation_id=gen_id,
        ))
    finally:
        # Sentinel: signal end of stream
        await queue.put(None)
        # Cleanup after a delay (give late SSE connections a chance)
        await asyncio.sleep(30)
        _active_pipelines.pop(gen_id, None)
        _active_queues.pop(gen_id, None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GET /generate/{id}/stream — SSE event stream
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/generate/{generation_id}/stream")
async def stream_generation(generation_id: str):
    """
    Server-Sent Events stream.  Each event is formatted as:

        event: <type>
        data: <json>

    Event types: status, analysis, outline, slide, slide_error, complete, error
    """
    queue = _active_queues.get(generation_id)

    if queue is None:
        # Check if the generation exists but is already complete
        state = await StateManager.load(generation_id)
        if state is None:
            raise HTTPException(status_code=404, detail="Generation not found")
        if state.status == GenerationStatus.COMPLETED:
            # Return a single "complete" event with the final state
            async def _completed_stream():
                payload = json.dumps({
                    "generation_id": state.generation_id,
                    "total_slides": state.total_slides,
                    "slides": [s.model_dump() for s in state.slides],
                    "theme": state.theme,
                })
                yield f"event: complete\ndata: {payload}\n\n"
            return StreamingResponse(
                _completed_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        raise HTTPException(status_code=410, detail="Stream no longer available")

    async def _event_stream():
        """Consume the queue and format as SSE."""
        try:
            while True:
                event = await asyncio.wait_for(queue.get(), timeout=300)
                if event is None:
                    # End sentinel
                    yield "event: done\ndata: {}\n\n"
                    break
                payload = json.dumps(event.data, default=str)
                yield f"event: {event.event}\ndata: {payload}\n\n"
        except asyncio.TimeoutError:
            yield 'event: error\ndata: {"error": "Stream timed out"}\n\n'

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GET /generate/{id} — poll status (non-streaming)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/generate/{generation_id}", response_model=GenerationStatusResponse)
async def get_generation_status(generation_id: str):
    """Return the current generation state (useful as a fallback to SSE)."""
    state = await StateManager.load(generation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Generation not found")

    completed = sum(1 for s in state.slides if s.status == "completed")

    return GenerationStatusResponse(
        generation_id=state.generation_id,
        status=state.status,
        total_slides=state.total_slides,
        completed_slides=completed,
        slides=state.slides,
        analysis=state.analysis,
        outline=state.outline,
        error=state.error,
        created_time=state.created_time,
        updated_time=state.updated_time,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DELETE /generate/{id} — cancel or remove
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.delete("/generate/{generation_id}")
async def delete_generation(generation_id: str):
    """Cancel an in-progress generation or remove a completed one."""
    state = await StateManager.load(generation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Generation not found")

    # Remove from active pipelines if running
    _active_pipelines.pop(generation_id, None)
    q = _active_queues.pop(generation_id, None)
    if q:
        await q.put(None)  # kill stream

    await StateManager.delete(generation_id)

    return {"status": "deleted", "generation_id": generation_id}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GET /generations — list active generations
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/generations")
async def list_generations():
    """List all generation IDs currently in the store."""
    ids = await StateManager.list_active()
    return {"generations": ids, "count": len(ids)}
