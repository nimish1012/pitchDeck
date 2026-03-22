"""
Pipeline Orchestrator — the core engine that drives the Gamma-style
presentation generation lifecycle.

Observed Gamma.app behaviour (via Chrome DevTools analysis):
  • SSE-based streaming with `onmessage` handlers
  • Cards processed SEQUENTIALLY (~3-4s each), not in parallel
  • Event lifecycle: streamStart → processed card N → response → complete
  • Images generated concurrently AFTER all cards (21s gap between response/complete)
  • Separate image endpoint: ai.api.gamma.app/media/images/generate
  • State backed by GraphQL mutations + Yjs collaborative doc

Our pipeline supports BOTH modes:
  • mode="sequential" — matches Gamma exactly (stream one card at a time)
  • mode="parallel"  — faster total time (all cards concurrently, emit as each finishes)

Flow:
  1. ANALYSE   → Extract topic, intent, audience, complexity from user prompt
  2. OUTLINE   → Generate structured slide outline with image/layout hints
  3. GENERATE  → Slide content generation (sequential OR parallel)
  4. IMAGES    → Parallel image generation for slides that need them
  5. LAYOUT    → Dynamic layout correction pass
  6. COMPLETE  → Final state snapshot

SSE Events emitted (mirrors Gamma's [AIStream] pattern):
  status          → pipeline stage changes
  analysis        → Step 1 result
  outline         → Step 2 result
  streamStart     → slide generation begins
  slide           → each slide as it completes ("processed card N")
  slide_error     → a slide failed after retries
  response        → all slides done (text complete)
  image_progress  → image generation progress
  complete        → everything done (Gamma: ai.request.complete)
  error           → pipeline failure
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator, Optional

from app.core.config import settings
from app.models.schemas import (
    AnalysisResult,
    DraftInput,
    GenerateRequest,
    GenerationState,
    GenerationStatus,
    ImageType,
    OutlineResult,
    OutlineSlide,
    Slide,
    SlideContent,
    SlideLayout,
    SSEEvent,
    TextAmount,
)
from app.services.image_generator import get_image_generator
from app.services.layout_engine import apply_layout_correction, decide_layout
from app.services.prompts import (
    ANALYSE_SYSTEM_PROMPT,
    ANALYSE_USER_PROMPT,
    OUTLINE_SYSTEM_PROMPT,
    OUTLINE_USER_PROMPT,
    SLIDE_SYSTEM_PROMPT,
    SLIDE_USER_PROMPT,
)
from app.services.state_manager import StateManager
from app.services.token_budget import budget_prompt_fragment, get_budget

logger = logging.getLogger(__name__)


class PresentationPipeline:
    """
    Orchestrates the full generation lifecycle.

    Usage:
        pipeline = PresentationPipeline(request)
        async for sse_event in pipeline.run():
            yield sse_event  # push to SSE stream
    """

    def __init__(self, request: GenerateRequest, mode: str = "parallel"):
        self.request = request
        self.state = self._init_state(request)
        self.mode = mode  # "parallel" (default, faster) or "sequential" (Gamma-style)
        self._llm = None  # lazy

    # ── Lazy LLM accessor ─────────────────────

    @property
    def llm(self):
        if self._llm is None:
            from app.services.llm_client import get_llm_client
            self._llm = get_llm_client()
        return self._llm

    # ── State initialisation ──────────────────

    @staticmethod
    def _init_state(req: GenerateRequest) -> GenerationState:
        state = GenerationState()
        state.draft_input = DraftInput(
            doc_generation_id=state.generation_id,
            prompt=req.prompt,
            settings=req.settings,
        )
        state.theme = req.settings.style.value
        state.metadata = {
            "text_amount": req.settings.text_amount.value,
            "image_generation": req.settings.image_generation,
            "image_model": req.settings.image_model,
            "requested_slides": req.settings.num_slides,
        }
        return state

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  Main entry point — yields SSE events
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def run(self) -> AsyncIterator[SSEEvent]:
        """Execute the pipeline and yield SSE events at each stage."""
        try:
            # ── Persist initial state ──────────
            await StateManager.save(self.state)

            # ── Step 1: ANALYSE ────────────────
            yield self._event("status", {"status": "analyzing", "message": "Analysing your prompt…"})
            self.state.status = GenerationStatus.ANALYZING
            await StateManager.save(self.state)

            analysis = await self._step1_analyse()
            self.state.analysis = analysis
            self.state.total_slides = analysis.num_slides
            await StateManager.save(self.state)

            yield self._event("analysis", analysis.model_dump())

            # ── Step 2: OUTLINE ────────────────
            yield self._event("status", {"status": "outlining", "message": "Building slide outline…"})
            self.state.status = GenerationStatus.OUTLINING
            await StateManager.save(self.state)

            outline = await self._step2_outline(analysis)
            self.state.outline = outline

            # Pre-populate slides list with pending stubs
            self.state.slides = [
                Slide(
                    slide_id=os.slide_id,
                    title=os.title,
                    layout=decide_layout(
                        slide_id=os.slide_id,
                        total_slides=len(outline.slides),
                        title=os.title,
                        key_points=os.key_points,
                        image_required=os.image_required,
                        image_type=os.image_type,
                        layout_hint=os.layout_hint,
                    ),
                    image_type=os.image_type,
                    status="pending",
                )
                for os in outline.slides
            ]
            self.state.total_slides = len(outline.slides)
            await StateManager.save(self.state)

            yield self._event("outline", {
                "slides": [s.model_dump() for s in outline.slides],
                "total": len(outline.slides),
            })

            # ── Step 3: SLIDE GENERATION ──────
            yield self._event("status", {"status": "generating", "message": "Generating slides…"})
            self.state.status = GenerationStatus.GENERATING
            await StateManager.save(self.state)

            # Emit streamStart (matches Gamma's ai.request.streamStart)
            yield self._event("streamStart", {
                "total_slides": len(outline.slides),
                "mode": self.mode,
            })

            if self.mode == "sequential":
                # Gamma-style: one card at a time, streamed sequentially
                async for slide_event in self._step3_sequential(analysis, outline):
                    yield slide_event
            else:
                # Parallel mode: all cards concurrently, emit as each finishes
                async for slide_event in self._step3_parallel(analysis, outline):
                    yield slide_event

            # Emit response (matches Gamma's ai.request.response — all text done)
            yield self._event("response", {
                "total_slides": self.state.total_slides,
                "completed": sum(1 for s in self.state.slides if s.status == "completed"),
                "failed": sum(1 for s in self.state.slides if s.status == "failed"),
            })

            # ── Step 4: IMAGE GENERATION ───────
            if self.request.settings.image_generation:
                yield self._event("status", {"status": "generating", "message": "Generating images…"})
                async for img_event in self._step4_generate_images():
                    yield img_event
                await StateManager.save(self.state)

            # ── Step 5: LAYOUT CORRECTION ──────
            self.state.slides = apply_layout_correction(self.state.slides)
            await StateManager.save(self.state)

            # ── Step 6: COMPLETE ───────────────
            # (matches Gamma's ai.request.complete)
            self.state.status = GenerationStatus.COMPLETED
            await StateManager.save(self.state)

            yield self._event("complete", {
                "generation_id": self.state.generation_id,
                "total_slides": self.state.total_slides,
                "slides": [s.model_dump() for s in self.state.slides],
                "theme": self.state.theme,
            })

        except Exception as e:
            logger.exception(f"Pipeline failed for {self.state.generation_id}: {e}")
            self.state.status = GenerationStatus.FAILED
            self.state.error = str(e)
            await StateManager.save(self.state)

            yield self._event("error", {
                "generation_id": self.state.generation_id,
                "error": str(e),
            })

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  Step 1: ANALYSE
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def _step1_analyse(self) -> AnalysisResult:
        user_prompt = ANALYSE_USER_PROMPT.format(
            prompt=self.request.prompt,
            num_slides=self.request.settings.num_slides,
            audience=self.request.settings.audience or "general (infer from topic)",
            tone=self.request.settings.tone or "infer from topic",
        )
        analysis = await self.llm.call_llm_json(
            system_prompt=ANALYSE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=AnalysisResult,
            temperature=settings.analysis_temperature,
            max_tokens=1500,
        )

        # Enforce user's slide count
        if analysis.num_slides > self.request.settings.num_slides:
            analysis.num_slides = self.request.settings.num_slides

        # Override title if user provided one
        if self.request.title:
            analysis.title = self.request.title

        # Fill in audience/tone from analysis if user left blank
        if not self.request.settings.audience:
            self.request.settings.audience = analysis.audience
        if not self.request.settings.tone:
            self.request.settings.tone = analysis.tone

        return analysis

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  Step 2: OUTLINE
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def _step2_outline(self, analysis: AnalysisResult) -> OutlineResult:
        user_prompt = OUTLINE_USER_PROMPT.format(
            title=analysis.title,
            presentation_type=analysis.presentation_type,
            audience=analysis.audience,
            tone=analysis.tone,
            complexity=analysis.complexity,
            num_slides=analysis.num_slides,
        )
        return await self.llm.call_llm_json(
            system_prompt=OUTLINE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=OutlineResult,
            temperature=settings.outline_temperature,
            max_tokens=3000,
        )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  Step 3a: SEQUENTIAL SLIDE GENERATION (Gamma-style)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def _step3_sequential(
        self,
        analysis: AnalysisResult,
        outline: OutlineResult,
    ) -> AsyncIterator[SSEEvent]:
        """
        Generate slides one at a time, in order.
        Matches Gamma's observed behaviour: [AIStream] processed card 2, 3, 4…
        Each card is streamed to the client as soon as it's done.
        """
        budget = get_budget(self.request.settings.text_amount)
        budget_text = budget_prompt_fragment(budget)
        all_titles = [s.title for s in outline.slides]

        for outline_slide in outline.slides:
            idx = outline_slide.slide_id - 1
            slide = await self._generate_single_slide(
                analysis, outline, outline_slide, budget, budget_text, all_titles, idx,
            )
            if slide:
                yield self._event("slide", {
                    "slide_id": slide.slide_id,
                    "slide": slide.model_dump(),
                    "progress": f"{sum(1 for s in self.state.slides if s.status == 'completed')}/{len(self.state.slides)}",
                })
            else:
                yield self._event("slide_error", {
                    "slide_id": outline_slide.slide_id,
                    "error": self.state.slides[idx].error,
                })

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  Step 3b: PARALLEL SLIDE GENERATION (faster)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def _step3_parallel(
        self,
        analysis: AnalysisResult,
        outline: OutlineResult,
    ) -> AsyncIterator[SSEEvent]:
        """Generate all slides concurrently, yielding an SSE event per completed slide."""
        budget = get_budget(self.request.settings.text_amount)
        budget_text = budget_prompt_fragment(budget)
        sem = asyncio.Semaphore(settings.max_parallel_slides)
        all_titles = [s.title for s in outline.slides]

        async def gen_one(outline_slide: OutlineSlide) -> tuple[int, Optional[Slide]]:
            idx = outline_slide.slide_id - 1
            async with sem:
                slide = await self._generate_single_slide(
                    analysis, outline, outline_slide, budget, budget_text, all_titles, idx,
                )
                return (idx, slide)

        tasks = [gen_one(os) for os in outline.slides]

        for coro in asyncio.as_completed(tasks):
            idx, slide = await coro
            if slide:
                yield self._event("slide", {
                    "slide_id": slide.slide_id,
                    "slide": slide.model_dump(),
                    "progress": f"{sum(1 for s in self.state.slides if s.status == 'completed')}/{len(self.state.slides)}",
                })
            else:
                yield self._event("slide_error", {
                    "slide_id": idx + 1,
                    "error": self.state.slides[idx].error,
                })

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  Single slide generation (shared by both modes)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def _generate_single_slide(
        self,
        analysis: AnalysisResult,
        outline: OutlineResult,
        outline_slide: OutlineSlide,
        budget,
        budget_text: str,
        all_titles: list[str],
        idx: int,
    ) -> Optional[Slide]:
        """Generate content for one slide with retry logic. Returns Slide or None."""
        # Mark as generating
        self.state.slides[idx].status = "generating"
        await StateManager.save(self.state)

        context_titles = [t for i, t in enumerate(all_titles) if i != idx]

        user_prompt = SLIDE_USER_PROMPT.format(
            title=analysis.title,
            presentation_type=analysis.presentation_type,
            audience=analysis.audience,
            tone=analysis.tone,
            slide_id=outline_slide.slide_id,
            total_slides=len(outline.slides),
            slide_title=outline_slide.title,
            key_points=", ".join(outline_slide.key_points),
            image_required=outline_slide.image_required,
            image_type=outline_slide.image_type.value if hasattr(outline_slide.image_type, 'value') else outline_slide.image_type,
            layout_hint=outline_slide.layout_hint.value if hasattr(outline_slide.layout_hint, 'value') else outline_slide.layout_hint,
            budget_constraints=budget_text,
            context_titles=", ".join(context_titles[:5]),
        )

        last_err = None
        for attempt in range(1, settings.max_retries + 2):
            try:
                generated = await self.llm.call_llm_json(
                    system_prompt=SLIDE_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    response_model=SlideContent,
                    temperature=settings.slide_temperature,
                    max_tokens=budget.max_tokens + 200,
                )

                layout = decide_layout(
                    slide_id=outline_slide.slide_id,
                    total_slides=len(outline.slides),
                    title=generated.title,
                    key_points=generated.content,
                    image_required=outline_slide.image_required,
                    image_type=outline_slide.image_type,
                    layout_hint=outline_slide.layout_hint,
                )

                slide = Slide(
                    slide_id=generated.slide_id,
                    title=generated.title,
                    content=generated.content,
                    layout=layout,
                    notes=generated.notes,
                    image_prompt=generated.image_prompt,
                    image_type=generated.image_type,
                    status="completed",
                    token_budget=budget.max_tokens,
                )

                self.state.slides[idx] = slide
                await StateManager.save(self.state)
                logger.info(f"[AIStream] processed card {outline_slide.slide_id}")
                return slide

            except Exception as e:
                last_err = e
                if attempt <= settings.max_retries:
                    wait = settings.retry_backoff_base * (2 ** (attempt - 1))
                    logger.warning(
                        f"Slide {outline_slide.slide_id} attempt {attempt} "
                        f"failed ({e}), retrying in {wait:.1f}s"
                    )
                    await asyncio.sleep(wait)

        # All retries exhausted
        logger.error(f"Slide {outline_slide.slide_id} failed: {last_err}")
        self.state.slides[idx].status = "failed"
        self.state.slides[idx].error = str(last_err)
        await StateManager.save(self.state)
        return None

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  Step 4: IMAGE GENERATION
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def _step4_generate_images(self) -> AsyncIterator[SSEEvent]:
        """
        Generate images for slides that have an image_prompt.
        Runs all image requests concurrently (matches Gamma's behaviour
        where images fill in ~21s after all cards are done).
        """
        image_gen = get_image_generator()
        art_style = self.request.settings.art_style_prompt

        slides_needing_images = [s for s in self.state.slides if s.image_prompt]
        if not slides_needing_images:
            return

        total = len(slides_needing_images)
        completed = 0

        async def gen_image(slide: Slide) -> None:
            nonlocal completed
            url = await image_gen.generate(
                prompt=slide.image_prompt,
                art_style_prompt=art_style,
            )
            if url:
                slide.image_url = url
            completed += 1

        tasks = [gen_image(s) for s in slides_needing_images]
        # Run concurrently and yield progress
        for coro in asyncio.as_completed(tasks):
            await coro
            yield self._event("image_progress", {
                "completed": completed,
                "total": total,
            })

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  Helpers
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _event(self, event_type: str, data: dict) -> SSEEvent:
        return SSEEvent(
            event=event_type,
            data=data,
            generation_id=self.state.generation_id,
        )
