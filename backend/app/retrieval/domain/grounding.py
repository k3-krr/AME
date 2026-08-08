import abc
import uuid
from typing import List, Dict, Any, Optional, Tuple
from app.retrieval.domain.value_objects import ContextFusionElement, Citation, GroundedPromptPackage, PipelineStatus


class IContextCompressor(abc.ABC):
    """Domain contract for context selection and size reduction."""

    @abc.abstractmethod
    def compress(self, elements: List[ContextFusionElement], limit: int) -> List[ContextFusionElement]:
        """Compresses retrieved context elements to fit within the configured limit, preserving rank order."""
        raise NotImplementedError()


class ICitationBuilder(abc.ABC):
    """Domain contract for human-readable source citations mapping."""

    @abc.abstractmethod
    def build_citations(self, elements: List[ContextFusionElement]) -> List[Citation]:
        """Compiles citations tracking memory IDs, capabilities, relevance scores, and source queries."""
        raise NotImplementedError()


class IPromptBuilder(abc.ABC):
    """Domain contract for LLM system/user prompt assembly."""

    @abc.abstractmethod
    def assemble_prompt(
        self,
        base_system_prompt: Optional[str],
        user_query: str,
        citations: List[Citation],
    ) -> Tuple[str, str]:
        """Assembles base instruction prompts, grounded context annotations, and user queries into a final string."""
        raise NotImplementedError()


class IGroundedContextValidator(abc.ABC):
    """Domain contract verifying prompt package schema, formatting, and constraints consistency."""

    @abc.abstractmethod
    def validate(self, package: GroundedPromptPackage) -> None:
        """Validates the package structure, citations, formatting tags, limits, and provenance traces."""
        raise NotImplementedError()


class DefaultContextCompressor(IContextCompressor):
    """Default compressor that preserves rank ordering while filtering lowest-value trailing items exceeding limit."""

    def compress(self, elements: List[ContextFusionElement], limit: int) -> List[ContextFusionElement]:
        compressed = []
        curr_size = 0
        for el in elements:
            size = len(el.content)
            if curr_size + size <= limit:
                compressed.append(el)
                curr_size += size
            else:
                break
        return compressed


class DefaultCitationBuilder(ICitationBuilder):
    """Compiles sequential citation mappings for retrieved context elements."""

    def build_citations(self, elements: List[ContextFusionElement]) -> List[Citation]:
        citations = []
        for idx, el in enumerate(elements, start=1):
            queries = el.provenance_metadata.get("source_queries", [])
            citations.append(
                Citation(
                    index=idx,
                    memory_id=el.memory_id,
                    source_tier=el.source_tier,
                    content=el.content,
                    relevance_score=el.relevance_score,
                    originating_queries=queries,
                )
            )
        return citations


class DefaultPromptBuilder(IPromptBuilder):
    """Assembles XML-style grounded contexts and query wrappers, handling custom base prompts cleanly."""

    def assemble_prompt(
        self,
        base_system_prompt: Optional[str],
        user_query: str,
        citations: List[Citation],
    ) -> Tuple[str, str]:
        base = base_system_prompt or ""
        
        lines = []
        for c in citations:
            lines.append(f"[{c.index}] ({c.source_tier}) {c.content}")
        formatted_context = "\n".join(lines)
        
        context_block = ""
        if citations:
            context_block = (
                f"You MUST use the following retrieved memories to answer the user's queries. "
                f"Cite sources using their index number (e.g., [1], [2]).\n"
                f"<grounded_context>\n"
                f"{formatted_context}\n"
                f"</grounded_context>\n\n"
            )
            
        grounded_prompt = (
            f"{base}\n\n" if base else ""
        ) + context_block + (
            f"<user_query>\n"
            f"{user_query}\n"
            f"</user_query>"
        )
        
        return grounded_prompt, formatted_context


class DefaultGroundedContextValidator(IGroundedContextValidator):
    """Asserts format structures, sequential index integrity, character bounds, and provenance fields."""

    def validate(self, package: GroundedPromptPackage) -> None:
        if not package.request_id:
            raise ValueError("request_id is required")
        if not package.user_query or not package.user_query.strip():
            raise ValueError("user_query is required")
        if not package.status or package.status not in PipelineStatus.__members__:
            raise ValueError(f"Invalid pipeline status: {package.status}")
        
        # Validate citation indexes are sequential starting at 1
        for idx, cit in enumerate(package.citations, start=1):
            if cit.index != idx:
                raise ValueError(f"Invalid citation index mismatch: expected {idx}, got {cit.index}")
            if not cit.memory_id:
                raise ValueError("Citation memory_id is required")
            if not cit.content or not cit.content.strip():
                raise ValueError("Citation content cannot be empty")
                
        # Validate formatting tags exist in assembled prompt if context is present
        if package.citations:
            if "<grounded_context>" not in package.system_prompt:
                raise ValueError("System prompt lacks required grounded context formatting tags")
            if "</grounded_context>" not in package.system_prompt:
                raise ValueError("System prompt lacks closing grounded context formatting tags")
                
        # Always validate user query tags exist in prompt
        if "<user_query>" not in package.system_prompt:
            raise ValueError("System prompt lacks required user query formatting tags")
        if "</user_query>" not in package.system_prompt:
            raise ValueError("System prompt lacks closing user query formatting tags")
