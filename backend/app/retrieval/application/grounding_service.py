import uuid
from typing import Optional, Dict, Any
from app.retrieval.domain.entities import GroundedContextPackage
from app.retrieval.domain.value_objects import GroundedPromptPackage
from app.retrieval.domain.grounding import (
    IContextCompressor,
    ICitationBuilder,
    IPromptBuilder,
    IGroundedContextValidator,
)


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
    ) -> GroundedPromptPackage:
        fused = context_package.fused_elements
        
        # 1. Compress context elements based on limit, preserving rank order
        compressed_fused = self.compressor.compress(fused, max_context_chars)
        
        # 2. Compile citation metadata mappings and attribution indices
        citations = self.citation_builder.build_citations(compressed_fused)
        
        # 3. Assemble prompt template containing optional instruction, context, and query
        system_prompt, formatted_context = self.prompt_builder.assemble_prompt(
            base_system_prompt, user_query, citations
        )
        
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
            }
        )
        
        # 5. Assert package integrity check
        self.validator.validate(package)
        
        return package
