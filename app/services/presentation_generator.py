import uuid
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

from app.models.request_schemas import (
    DocumentPresentationRequest, 
    PromptPresentationRequest, 
    OutlinePresentationRequest,
    PresentationResponse,
    SlideData,
    GeneratedSlide,
)

logger = logging.getLogger(__name__)


class BasePresentationGenerator(ABC):
    """Abstract base class for presentation generators"""
    
    @abstractmethod
    async def generate_presentation(self, **kwargs) -> PresentationResponse:
        """Generate a presentation based on input parameters"""
        pass
    
    def _generate_presentation_id(self) -> str:
        """Generate unique presentation ID"""
        return f"pres_{uuid.uuid4().hex[:8]}"
    
    def _create_slide(self, slide_number: int, title: str, content: List[str], notes: Optional[str] = None, layout: Optional[str] = None) -> SlideData:
        """Create a slide data object"""
        return SlideData(
            slide_number=slide_number,
            title=title,
            content=content,
            notes=notes,
            layout=layout,
        )

class DocumentPresentationGenerator(BasePresentationGenerator):
    """
    Generate presentations from documents using a 2-stage LLM pipeline:
    
    Stage 1: Analyse extracted content → break into slide sections
    Stage 2: Generate polished slide content for each section in parallel
    """
    
    async def generate_presentation(self, request: DocumentPresentationRequest, document_content: str) -> PresentationResponse:
        """Generate presentation from document via the 2-stage pipeline."""
        presentation_id = self._generate_presentation_id()
        
        try:
            from app.services.llm_client import get_llm_client
            llm = get_llm_client()
        except Exception as e:
            logger.warning(f"LLM client unavailable ({e}), using stub generation")
            return await self._generate_stub_presentation(request, document_content, presentation_id)

        try:
            # ── Stage 1: Analyse the document ────────────────
            logger.info(f"[{presentation_id}] Doc Stage 1: Analysing document...")
            analysis = await self._stage1_analyse_document(llm, request, document_content)
            logger.info(f"[{presentation_id}] Doc Stage 1 complete: {analysis.ppt_type}, {len(analysis.sections)} sections")

            # ── Stage 2: Generate slides in parallel ─────────
            logger.info(f"[{presentation_id}] Doc Stage 2: Generating {len(analysis.sections)} slides in parallel...")
            slides = await self._stage2_generate_slides_parallel(llm, analysis)
            logger.info(f"[{presentation_id}] Doc Stage 2 complete: {len(slides)} slides generated")

            toc = [s.title for s in slides]

            return PresentationResponse(
                presentation_id=presentation_id,
                title=analysis.title,
                slides=slides,
                total_slides=len(slides),
                generation_method="document",
                table_of_contents=toc,
                created_at=datetime.utcnow().isoformat(),
            )

        except Exception as e:
            logger.error(f"[{presentation_id}] Doc pipeline failed: {e}, falling back to stub")
            return await self._generate_stub_presentation(request, document_content, presentation_id)

    # ──────────────────────────────────────────────
    #  Stage 1: Document Analysis
    # ──────────────────────────────────────────────

    async def _stage1_analyse_document(self, llm, request: DocumentPresentationRequest, document_content: str):
        """Call the LLM to break the document into slide sections."""
        from app.services.prompts import DOCUMENT_ANALYSIS_SYSTEM_PROMPT, DOCUMENT_ANALYSIS_USER_PROMPT
        from app.models.request_schemas import DocumentAnalysis

        # Truncate very long documents to fit within LLM context
        max_chars = 12000
        content_for_llm = document_content[:max_chars]
        if len(document_content) > max_chars:
            content_for_llm += "\n\n[... document truncated ...]"

        user_prompt = DOCUMENT_ANALYSIS_USER_PROMPT.format(
            title=request.title or "Not provided",
            max_slides=request.max_slides or 10,
            additional_text=request.additional_text or "None",
            document_content=content_for_llm,
        )
        analysis = await llm.call_llm_json(
            system_prompt=DOCUMENT_ANALYSIS_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=DocumentAnalysis,
            temperature=0.4,
            max_tokens=3000,
        )

        # Respect user's title if provided
        if request.title:
            analysis.title = request.title

        return analysis

    # ──────────────────────────────────────────────
    #  Stage 2: Parallel Slide Generation
    # ──────────────────────────────────────────────

    async def _stage2_generate_slides_parallel(self, llm, analysis) -> List[SlideData]:
        """Generate slide content for each document section in parallel."""
        from app.services.prompts import DOCUMENT_SLIDE_SYSTEM_PROMPT, DOCUMENT_SLIDE_USER_PROMPT

        async def generate_single_slide(section) -> SlideData:
            user_prompt = DOCUMENT_SLIDE_USER_PROMPT.format(
                presentation_title=analysis.title,
                ppt_type=analysis.ppt_type,
                target_audience=analysis.target_audience,
                slide_number=section.slide_number,
                total_slides=len(analysis.sections),
                section_title=section.section_title,
                source_excerpt=section.source_excerpt,
            )
            generated = await llm.call_llm_json(
                system_prompt=DOCUMENT_SLIDE_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_model=GeneratedSlide,
                temperature=0.7,
            )
            return SlideData(
                slide_number=generated.slide_number,
                title=generated.title,
                content=generated.content,
                notes=generated.notes or None,
                layout=generated.layout,
            )

        tasks = [generate_single_slide(s) for s in analysis.sections]
        slides = await asyncio.gather(*tasks)
        slides = sorted(slides, key=lambda s: s.slide_number)
        return list(slides)

    # ──────────────────────────────────────────────
    #  Fallback Stub Generator
    # ──────────────────────────────────────────────

    async def _generate_stub_presentation(
        self, request: DocumentPresentationRequest, document_content: str, presentation_id: str
    ) -> PresentationResponse:
        """Fallback: naive line-splitting when LLM is unavailable."""
        slides = []

        slides.append(self._create_slide(
            slide_number=1,
            title=request.title or "Document Summary",
            content=["Generated from uploaded document"],
            layout="title",
        ))

        max_slides = request.max_slides or 10
        content_lines = document_content.split('\n')[:max_slides - 1]

        for i, line in enumerate(content_lines, 2):
            if line.strip():
                slides.append(self._create_slide(
                    slide_number=i,
                    title=f"Slide {i}",
                    content=[line.strip()],
                    layout="content",
                ))

        return PresentationResponse(
            presentation_id=presentation_id,
            title=request.title or "Document Presentation",
            slides=slides,
            total_slides=len(slides),
            generation_method="document",
            created_at=datetime.utcnow().isoformat(),
        )


class PromptPresentationGenerator(BasePresentationGenerator):
    """
    Generate presentations from prompts using a 3-stage LLM pipeline:
    
    Stage 1: Analyse the prompt → extract intent, ppt type, slide count
    Stage 2: Generate outline + table of contents
    Stage 3: Generate each slide's content in parallel
    """
    
    async def generate_presentation(self, request: PromptPresentationRequest) -> PresentationResponse:
        """Generate presentation from prompt via the 3-stage pipeline."""
        presentation_id = self._generate_presentation_id()
        
        try:
            # Lazy import to avoid crash when openai is not installed
            from app.services.llm_client import get_llm_client
            llm = get_llm_client()
        except Exception as e:
            logger.warning(f"LLM client unavailable ({e}), using stub generation")
            return await self._generate_stub_presentation(request, presentation_id)

        try:
            # ── Stage 1: Analyse the prompt ──────────────────
            logger.info(f"[{presentation_id}] Stage 1: Analysing prompt...")
            analysis = await self._stage1_analyse_prompt(llm, request)
            logger.info(f"[{presentation_id}] Stage 1 complete: {analysis.ppt_type}, {analysis.recommended_slides} slides")
            
            # ── Stage 2: Generate outline + TOC ──────────────
            logger.info(f"[{presentation_id}] Stage 2: Generating outline...")
            outline = await self._stage2_generate_outline(llm, analysis)
            logger.info(f"[{presentation_id}] Stage 2 complete: {len(outline.slide_outlines)} slide outlines")

            # ── Stage 3: Generate slides in parallel ─────────
            logger.info(f"[{presentation_id}] Stage 3: Generating {len(outline.slide_outlines)} slides in parallel...")
            slides = await self._stage3_generate_slides_parallel(llm, analysis, outline)
            logger.info(f"[{presentation_id}] Stage 3 complete: {len(slides)} slides generated")

            return PresentationResponse(
                presentation_id=presentation_id,
                title=analysis.title,
                slides=slides,
                total_slides=len(slides),
                generation_method="prompt",
                table_of_contents=outline.table_of_contents,
                created_at=datetime.utcnow().isoformat(),
            )

        except Exception as e:
            logger.error(f"[{presentation_id}] Pipeline failed: {e}, falling back to stub")
            return await self._generate_stub_presentation(request, presentation_id)

    # ──────────────────────────────────────────────
    #  Stage 1: Prompt Analysis
    # ──────────────────────────────────────────────

    async def _stage1_analyse_prompt(self, llm, request: PromptPresentationRequest):
        """Call the LLM to analyse the user's prompt."""
        from app.services.prompts import ANALYSIS_SYSTEM_PROMPT, ANALYSIS_USER_PROMPT
        from app.models.request_schemas import PromptAnalysis

        user_prompt = ANALYSIS_USER_PROMPT.format(
            prompt=request.prompt,
            max_slides=request.max_slides or 10,
            target_audience=request.target_audience or "general",
        )
        analysis = await llm.call_llm_json(
            system_prompt=ANALYSIS_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=PromptAnalysis,
            temperature=0.5,  # Lower temp for analytical task
        )

        # Cap slide count to user's requested max
        max_slides = request.max_slides or 10
        if analysis.recommended_slides > max_slides:
            analysis.recommended_slides = max_slides
            analysis.slide_intents = analysis.slide_intents[:max_slides]

        # Use user-provided title if given
        if request.title:
            analysis.title = request.title

        return analysis

    # ──────────────────────────────────────────────
    #  Stage 2: Outline + Table of Contents
    # ──────────────────────────────────────────────

    async def _stage2_generate_outline(self, llm, analysis):
        """Call the LLM to generate a detailed outline and TOC."""
        from app.services.prompts import OUTLINE_SYSTEM_PROMPT, OUTLINE_USER_PROMPT
        from app.models.request_schemas import PresentationOutline

        slide_intents_text = "\n".join(
            f"  Slide {si.slide_number}: {si.intent}"
            for si in analysis.slide_intents
        )
        user_prompt = OUTLINE_USER_PROMPT.format(
            title=analysis.title,
            ppt_type=analysis.ppt_type,
            target_audience=analysis.target_audience,
            recommended_slides=analysis.recommended_slides,
            slide_intents_text=slide_intents_text,
        )
        return await llm.call_llm_json(
            system_prompt=OUTLINE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=PresentationOutline,
            temperature=0.6,
        )

    # ──────────────────────────────────────────────
    #  Stage 3: Parallel Slide Generation
    # ──────────────────────────────────────────────

    async def _stage3_generate_slides_parallel(
        self, llm, analysis, outline
    ) -> List[SlideData]:
        """Generate all slides in parallel via asyncio.gather()."""
        from app.services.prompts import SLIDE_SYSTEM_PROMPT, SLIDE_USER_PROMPT

        async def generate_single_slide(slide_outline) -> SlideData:
            """Generate content for a single slide."""
            user_prompt = SLIDE_USER_PROMPT.format(
                presentation_title=analysis.title,
                ppt_type=analysis.ppt_type,
                target_audience=analysis.target_audience,
                slide_number=slide_outline.slide_number,
                slide_title=slide_outline.title,
                bullet_points=", ".join(slide_outline.bullet_points),
                speaker_notes_hint=slide_outline.speaker_notes_hint,
                layout=slide_outline.layout,
            )
            generated = await llm.call_llm_json(
                system_prompt=SLIDE_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_model=GeneratedSlide,
                temperature=0.7,
            )
            return SlideData(
                slide_number=generated.slide_number,
                title=generated.title,
                content=generated.content,
                notes=generated.notes or None,
                layout=generated.layout,
            )

        # Fire all slide generation calls in parallel
        tasks = [generate_single_slide(so) for so in outline.slide_outlines]
        slides = await asyncio.gather(*tasks)

        # Sort by slide number to ensure correct order
        slides = sorted(slides, key=lambda s: s.slide_number)
        return list(slides)

    # ──────────────────────────────────────────────
    #  Fallback Stub Generator
    # ──────────────────────────────────────────────

    async def _generate_stub_presentation(
        self, request: PromptPresentationRequest, presentation_id: str
    ) -> PresentationResponse:
        """Fallback: generate placeholder slides when LLM is unavailable."""
        slides = []
        max_slides = request.max_slides or 10

        slides.append(self._create_slide(
            slide_number=1,
            title=request.title or request.prompt[:50] + "...",
            content=[request.prompt],
            layout="title",
        ))

        for i in range(2, max_slides + 1):
            slides.append(self._create_slide(
                slide_number=i,
                title=f"Key Point {i-1}",
                content=[f"Generated content based on: {request.prompt}"],
                layout="content",
            ))

        return PresentationResponse(
            presentation_id=presentation_id,
            title=request.title or "Generated Presentation",
            slides=slides,
            total_slides=len(slides),
            generation_method="prompt",
            created_at=datetime.utcnow().isoformat(),
        )


class OutlinePresentationGenerator(BasePresentationGenerator):
    """
    Generate presentations from user-provided outlines using a 2-stage LLM pipeline:
    
    Stage 1: Analyse the outline → understand intent, ppt type, audience
    Stage 2: Generate polished content for each slide in parallel (faithful to outline)
    """
    
    async def generate_presentation(self, request: OutlinePresentationRequest) -> PresentationResponse:
        """Generate presentation from outline via the 2-stage pipeline."""
        presentation_id = self._generate_presentation_id()
        
        try:
            from app.services.llm_client import get_llm_client
            llm = get_llm_client()
        except Exception as e:
            logger.warning(f"LLM client unavailable ({e}), using direct mapping")
            return await self._generate_direct_mapping(request, presentation_id)

        try:
            # ── Stage 1: Analyse the outline ─────────────────
            logger.info(f"[{presentation_id}] Outline Stage 1: Analysing outline...")
            analysis = await self._stage1_analyse_outline(llm, request)
            logger.info(f"[{presentation_id}] Outline Stage 1 complete: {analysis.ppt_type}, audience={analysis.target_audience}")

            # ── Stage 2: Generate slide content in parallel ──
            logger.info(f"[{presentation_id}] Outline Stage 2: Generating {len(request.outline)} slides in parallel...")
            slides = await self._stage2_generate_slides_parallel(llm, request, analysis)
            logger.info(f"[{presentation_id}] Outline Stage 2 complete: {len(slides)} slides generated")

            # Build TOC from the generated slide titles
            toc = [s.title for s in slides]

            return PresentationResponse(
                presentation_id=presentation_id,
                title=analysis.title,
                slides=slides,
                total_slides=len(slides),
                generation_method="outline",
                table_of_contents=toc,
                created_at=datetime.utcnow().isoformat(),
            )

        except Exception as e:
            logger.error(f"[{presentation_id}] Outline pipeline failed: {e}, falling back to direct mapping")
            return await self._generate_direct_mapping(request, presentation_id)

    # ──────────────────────────────────────────────
    #  Stage 1: Outline Analysis
    # ──────────────────────────────────────────────

    async def _stage1_analyse_outline(self, llm, request: OutlinePresentationRequest):
        """Call the LLM to analyse the user's outline."""
        from app.services.prompts import OUTLINE_ANALYSIS_SYSTEM_PROMPT, OUTLINE_ANALYSIS_USER_PROMPT
        from app.models.request_schemas import OutlineAnalysis

        outline_text = ""
        for i, item in enumerate(request.outline, 1):
            title = item.get("title", f"Slide {i}")
            content = item.get("content", [])
            content_str = ", ".join(content) if isinstance(content, list) else str(content)
            outline_text += f"  Slide {i}: {title}"
            if content_str:
                outline_text += f" — {content_str}"
            outline_text += "\n"

        user_prompt = OUTLINE_ANALYSIS_USER_PROMPT.format(
            title=request.title or "Untitled Presentation",
            num_slides=len(request.outline),
            outline_text=outline_text,
        )
        analysis = await llm.call_llm_json(
            system_prompt=OUTLINE_ANALYSIS_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=OutlineAnalysis,
            temperature=0.4,
        )

        # Respect user's title if provided
        if request.title:
            analysis.title = request.title

        return analysis

    # ──────────────────────────────────────────────
    #  Stage 2: Parallel Slide Generation
    # ──────────────────────────────────────────────

    async def _stage2_generate_slides_parallel(self, llm, request, analysis) -> List[SlideData]:
        """Generate polished content for each outline item in parallel."""
        from app.services.prompts import OUTLINE_SLIDE_SYSTEM_PROMPT, OUTLINE_SLIDE_USER_PROMPT

        async def generate_single_slide(i: int, outline_item: dict) -> SlideData:
            title = outline_item.get("title", f"Slide {i}")
            content = outline_item.get("content", [])
            notes = outline_item.get("notes", "")
            content_str = ", ".join(content) if isinstance(content, list) else str(content)

            user_prompt = OUTLINE_SLIDE_USER_PROMPT.format(
                presentation_title=analysis.title,
                ppt_type=analysis.ppt_type,
                target_audience=analysis.target_audience,
                slide_number=i,
                total_slides=len(request.outline),
                slide_title=title,
                user_content=content_str or "No content provided — generate relevant points",
                user_notes=notes or "No notes provided",
            )
            generated = await llm.call_llm_json(
                system_prompt=OUTLINE_SLIDE_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                response_model=GeneratedSlide,
                temperature=0.7,
            )
            return SlideData(
                slide_number=generated.slide_number,
                title=generated.title,
                content=generated.content,
                notes=generated.notes or None,
                layout=generated.layout,
            )

        tasks = [
            generate_single_slide(i, item)
            for i, item in enumerate(request.outline, 1)
        ]
        slides = await asyncio.gather(*tasks)
        slides = sorted(slides, key=lambda s: s.slide_number)
        return list(slides)

    # ──────────────────────────────────────────────
    #  Fallback: Direct Mapping (no LLM)
    # ──────────────────────────────────────────────

    async def _generate_direct_mapping(
        self, request: OutlinePresentationRequest, presentation_id: str
    ) -> PresentationResponse:
        """Fallback: map outline items directly to slides without LLM."""
        slides = []
        for i, outline_item in enumerate(request.outline, 1):
            title = outline_item.get("title", f"Slide {i}")
            content = outline_item.get("content", [])
            notes = outline_item.get("notes")
            slides.append(self._create_slide(
                slide_number=i,
                title=title,
                content=content if isinstance(content, list) else [content],
                notes=notes,
                layout="content",
            ))
        return PresentationResponse(
            presentation_id=presentation_id,
            title=request.title or "Outline Presentation",
            slides=slides,
            total_slides=len(slides),
            generation_method="outline",
            created_at=datetime.utcnow().isoformat(),
        )

class PresentationGeneratorFactory:
    """Factory to create appropriate presentation generators"""
    
    @staticmethod
    def get_generator(presentation_type: str) -> BasePresentationGenerator:
        """Get the appropriate generator based on presentation type"""
        generators = {
            "document": DocumentPresentationGenerator(),
            "prompt": PromptPresentationGenerator(),
            "outline": OutlinePresentationGenerator()
        }
        
        return generators.get(presentation_type, DocumentPresentationGenerator())