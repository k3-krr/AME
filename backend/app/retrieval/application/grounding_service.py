import uuid
import time
from typing import Optional, Dict, Any
from app.retrieval.domain.entities import GroundedContextPackage
from app.retrieval.domain.value_objects import GroundedPromptPackage, PipelineStatus
from app.retrieval.domain.grounding import (
    IContextCompressor,
    ICitationBuilder,
    IPromptBuilder,
    IGroundedContextValidator,
)
from app.retrieval.application.telemetry import RetrievalTelemetryTracker


class GroundingService:
    """Orchestrates citation building, rank-preserving context compression, prompt formatting, and package validation."""

    def __init__(
        self,
        compressor: IContextCompressor,
        citation_builder: ICitationBuilder,
        prompt_builder: IPromptBuilder,
        validator: IGroundedContextValidator,
    ):
        self.compressor = compressor
        self.citation_builder = citation_builder
        self.prompt_builder = prompt_builder
        self.validator = validator

    def prepare_grounded_prompt(
        self,
        user_query: str,
        context_package: GroundedContextPackage,
        base_system_prompt: Optional[str] = None,
        max_context_chars: int = 4000,
        tracker: Optional[RetrievalTelemetryTracker] = None,
    ) -> GroundedPromptPackage:
        if not tracker:
            tracker = RetrievalTelemetryTracker(context_package.request_id)
            
        fused = context_package.fused_elements
        
        # 1. Compress context elements based on limit, preserving rank order
        start_comp = time.perf_counter()
        compressed_fused = self.compressor.compress(fused, max_context_chars)
        tracker.record_latency("compression", time.perf_counter() - start_comp)
        
        # 2. Compile citation metadata mappings and attribution indices
        start_cit = time.perf_counter()
        citations = self.citation_builder.build_citations(compressed_fused)
        tracker.record_latency("citation", time.perf_counter() - start_cit)
        
        # 3. Assemble prompt template containing optional instruction, context, and query
        start_prompt = time.perf_counter()
        system_prompt, formatted_context = self.prompt_builder.assemble_prompt(
            base_system_prompt, user_query, citations
        )
        tracker.record_latency("prompt_assembly", time.perf_counter() - start_prompt)
        
        # 4. Construct the final grounded prompt package
        package = GroundedPromptPackage(
            request_id=context_package.request_id,
            user_query=user_query,
            system_prompt=system_prompt,
            formatted_context=formatted_context,
            citations=citations,
            grounding_metadata={
                "original_metadata": context_package.metadata,
                "max_context_chars": max_context_chars,
                "retained_element_ratio": len(compressed_fused) / len(fused) if fused else 1.0,
            },
            status=context_package.status
        )
        
        # 5. Assert package integrity check
        try:
            self.validator.validate(package)
        except ValueError as val_err:
            tracker.success = False
            tracker.validation_failure_category = "integrity_violation"
            raise val_err
            
        tracker.context_size_chars = len(system_prompt)
        tracker.retained_element_ratio = len(compressed_fused) / len(fused) if fused else 1.0
        
        return package
