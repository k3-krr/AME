import pytest
import uuid
from typing import List
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Memory, MemoryType, MemoryStatus
from app.retrieval.domain.entities import GroundedContextPackage
from app.retrieval.domain.value_objects import ContextFusionElement, Citation, GroundedPromptPackage
from app.retrieval.domain.grounding import (
    DefaultContextCompressor,
    DefaultCitationBuilder,
    DefaultPromptBuilder,
    DefaultGroundedContextValidator,
)
from app.retrieval.application.grounding_service import GroundingService


def test_compressor_retains_rank_and_respects_limit():
    """Verify DefaultContextCompressor preserves rank and drops elements exceeding character limits."""
    compressor = DefaultContextCompressor()
    
    el1 = ContextFusionElement(
        memory_id=uuid.uuid4(),
        content="First ranked element", # 20 chars
        relevance_score=0.95,
        source_tier="semantic"
    )
    el2 = ContextFusionElement(
        memory_id=uuid.uuid4(),
        content="Second element content", # 22 chars
        relevance_score=0.85,
        source_tier="episodic"
    )
    el3 = ContextFusionElement(
        memory_id=uuid.uuid4(),
        content="Third", # 5 chars
        relevance_score=0.75,
        source_tier="procedural"
    )
    
    # Total characters: 20 + 22 + 5 = 47.
    # Limit: 25. Should only retain el1 (20 chars) because el2 is 22 (20+22=42 > 25).
    # Limit: 45. Should retain el1 and el2 (20+22=42). el3 (5) is skipped (42+5=47 > 45).
    res1 = compressor.compress([el1, el2, el3], 25)
    assert len(res1) == 1
    assert res1[0] == el1
    
    res2 = compressor.compress([el1, el2, el3], 45)
    assert len(res2) == 2
    assert res2[0] == el1
    assert res2[1] == el2


def test_citation_builder_indices_sequence():
    """Verify DefaultCitationBuilder assigns sequential indices starting from 1."""
    builder = DefaultCitationBuilder()
    
    el1 = ContextFusionElement(
        memory_id=uuid.uuid4(),
        content="Fact 1",
        relevance_score=0.9,
        source_tier="semantic",
        provenance_metadata={"source_queries": ["query A"]}
    )
    el2 = ContextFusionElement(
        memory_id=uuid.uuid4(),
        content="Fact 2",
        relevance_score=0.8,
        source_tier="working",
        provenance_metadata={"source_queries": ["query B"]}
    )
    
    citations = builder.build_citations([el1, el2])
    assert len(citations) == 2
    assert citations[0].index == 1
    assert citations[0].content == "Fact 1"
    assert citations[0].originating_queries == ["query A"]
    
    assert citations[1].index == 2
    assert citations[1].content == "Fact 2"
    assert citations[1].originating_queries == ["query B"]


def test_prompt_builder_assembly_markup():
    """Verify DefaultPromptBuilder templates context and user query tags properly."""
    builder = DefaultPromptBuilder()
    
    cit1 = Citation(
        index=1,
        memory_id=uuid.uuid4(),
        source_tier="SEMANTIC_SEARCH",
        content="Bicycle is red",
        relevance_score=0.9,
        originating_queries=["bike"]
    )
    
    # Case A: Optional system prompt provided
    system_prompt, formatted = builder.assemble_prompt(
        base_system_prompt="Be concise.",
        user_query="Who owns the bike?",
        citations=[cit1]
    )
    assert "Be concise." in system_prompt
    assert "<grounded_context>" in system_prompt
    assert "[1] (SEMANTIC_SEARCH) Bicycle is red" in system_prompt
    assert "<user_query>\nWho owns the bike?\n</user_query>" in system_prompt
    assert formatted == "[1] (SEMANTIC_SEARCH) Bicycle is red"

    # Case B: Base system prompt is None/empty
    system_prompt_empty, _ = builder.assemble_prompt(
        base_system_prompt=None,
        user_query="Who owns the bike?",
        citations=[cit1]
    )
    # No "helpful AI assistant" fallback personality should be injected
    assert "helpful AI assistant" not in system_prompt_empty
    assert system_prompt_empty.startswith("<grounded_context>") or system_prompt_empty.strip().startswith("You MUST use")


def test_validator_enforces_formatting_rules():
    """Verify DefaultGroundedContextValidator catches malformed prompt packages."""
    validator = DefaultGroundedContextValidator()
    
    now = datetime.now(timezone.utc)
    cit = Citation(
        index=1,
        memory_id=uuid.uuid4(),
        source_tier="semantic",
        content="Valid element",
        relevance_score=0.9,
        originating_queries=[]
    )
    
    # Scenario A: Missing query
    package_no_query = GroundedPromptPackage(
        request_id=uuid.uuid4(),
        user_query="",
        system_prompt="<grounded_context>\n[1] (semantic) Valid element\n</grounded_context>\n\n<user_query>\n\n</user_query>",
        formatted_context="",
        citations=[cit],
        compiled_at=now
    )
    with pytest.raises(ValueError, match="user_query is required"):
        validator.validate(package_no_query)

    # Scenario B: Missing grounded context tags
    package_no_tags = GroundedPromptPackage(
        request_id=uuid.uuid4(),
        user_query="Query",
        system_prompt="[1] (semantic) Valid element\n\n<user_query>\nQuery\n</user_query>",
        formatted_context="",
        citations=[cit],
        compiled_at=now
    )
    with pytest.raises(ValueError, match="lacks required grounded context formatting tags"):
        validator.validate(package_no_tags)

    # Scenario C: Missing user query tags
    package_no_qtags = GroundedPromptPackage(
        request_id=uuid.uuid4(),
        user_query="Query",
        system_prompt="<grounded_context>\n[1] (semantic) Valid element\n</grounded_context>\n\nQuery",
        formatted_context="",
        citations=[cit],
        compiled_at=now
    )
    with pytest.raises(ValueError, match="lacks required user query formatting tags"):
        validator.validate(package_no_qtags)


@pytest.mark.asyncio
async def test_api_ground_endpoint_e2e(client: AsyncClient, db_session: AsyncSession):
    """Verify end-to-end retrieve and ground endpoint compiles prompt details correctly."""
    # 1. Register and login
    await client.post(
        "/api/v1/auth/register",
        json={"email": "ground_flow@example.com", "password": "securepassword123"}
    )
    
    # 2. Create conversation
    conv_resp = await client.post("/api/v1/conversations", json={"title": "Prompt Chat"})
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["id"]

    # 3. Create a memory
    mem_resp = await client.post(
        "/api/v1/memories",
        json={
            "content": "User owns a brick house in Seattle.",
            "memory_type": "Fact",
            "importance": 0.8,
            "confidence": 0.95,
        }
    )
    assert mem_resp.status_code == 201
    
    # 4. Call /ground endpoint
    ground_resp = await client.post(
        "/api/v1/retrieval/ground",
        json={
            "query": "Tell me about my brick house",
            "conversation_id": conv_id,
            "options": {
                "base_system_prompt": "Answer in French.",
                "max_context_chars": 2000
            }
        }
    )
    
    assert ground_resp.status_code == 200
    data = ground_resp.json()
    assert data["user_query"] == "Tell me about my brick house"
    assert "Answer in French." in data["system_prompt"]
    assert "<grounded_context>" in data["system_prompt"]
    assert "<user_query>\nTell me about my brick house\n</user_query>" in data["system_prompt"]
    
    assert len(data["citations"]) >= 1
    citation = data["citations"][0]
    assert citation["index"] == 1
    assert "brick house" in citation["content"]
    assert citation["source_tier"] == "SEMANTIC_SEARCH"
    
    assert "retained_element_ratio" in data["grounding_metadata"]
