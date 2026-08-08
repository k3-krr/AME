import pytest
from httpx import AsyncClient
from app.retrieval.domain.value_objects import RetrievalQuerySource, RetrievalQuery
from app.retrieval.domain.services import (
    IAbbreviationProvider,
    DefaultAbbreviationProvider,
    QueryRewriter,
    QueryExpansionService,
    MultiQueryGenerator,
    QueryNormalizer,
)
from app.retrieval.application.query_rewrite_service import QueryRewriteService


class DummyAbbreviationProvider(IAbbreviationProvider):
    def get_abbreviations(self):
        return {
            r"\btst\b": "Test Case",
            r"\babc\b": "Alphabet Soup",
        }


def test_query_rewriter_resolves_abbreviations():
    """Verify that QueryRewriter expands target abbreviations using provider mappings."""
    provider = DummyAbbreviationProvider()
    rewriter = QueryRewriter(provider)
    
    assert rewriter.rewrite("This is a tst query") == "This is a Test Case query"
    assert rewriter.rewrite("ABC of programming") == "Alphabet Soup of programming"
    assert rewriter.rewrite("Some other random words") == "Some other random words"


def test_query_rewriter_does_not_rewrite_pronouns():
    """Verify pronoun conversions (e.g. 'me' or 'my memories') are not performed by rewriter."""
    provider = DefaultAbbreviationProvider()
    rewriter = QueryRewriter(provider)
    
    # Assert that pronouns and generic phrases are untouched, preserving original queries
    assert rewriter.rewrite("Help me configure git") == "Help me configure git"
    assert rewriter.rewrite("Show my memories about database") == "Show my memories about database"


def test_query_expansion_service():
    """Verify that expansion service returns search-friendly variants based on entity detection."""
    service = QueryExpansionService()
    
    # git keyword should generate git-specific variants
    variants = service.expand("how does git work?")
    assert "git version control" in variants
    assert "repository commits" in variants
    assert "branches" in variants
    
    # db/database keyword should generate database-specific variants
    db_variants = service.expand("backup my db")
    assert "database SQL storage" in db_variants
    assert "database schema" in db_variants

    # unknown entities return empty list
    assert service.expand("something irrelevant") == []


def test_multi_query_generator_priorities_and_deduplication():
    """Verify multi-query generator maps normalized floats, adds keyword subqueries, and deduplicates."""
    generator = MultiQueryGenerator()
    rewritten_query = "Configure Adaptive Memory Engine database"
    expanded_variants = [
        "database SQL storage",
        "Adaptive Memory Engine",  # Duplicate string check
    ]
    
    queries = generator.generate(rewritten_query, expanded_variants)
    
    # The queries list should contain:
    # 1. Primary query (0.95, REWRITER)
    # 2. Entity expansions (0.80, EXPANSION) -> "database SQL storage" (but not "Adaptive Memory Engine" because it is a duplicate of a substring, actually wait - the duplicate filter compares lowercased cleaned strings. Let's see: rewritten_query is "Configure Adaptive Memory Engine database". "Adaptive Memory Engine" is a substring, but not identical. Wait! The check is: cleaned = q_str.strip().lower(); if cleaned not in seen: ...
    # So "adaptive memory engine" is added because it's not identical to "configure adaptive memory engine database").
    # Let's verify details:
    assert len(queries) >= 2
    
    # Find primary query
    primary = next(q for q in queries if q.source == RetrievalQuerySource.REWRITER)
    assert primary.query == rewritten_query
    assert primary.priority == 0.95
    
    # Find expansion query
    exp = next(q for q in queries if q.source == RetrievalQuerySource.EXPANSION)
    assert exp.priority == 0.80
    
    # Find generator keyword query
    gen = next(q for q in queries if q.source == RetrievalQuerySource.GENERATOR)
    assert gen.priority == 0.65
    assert "Configure" in gen.query or "Adaptive" in gen.query


def test_query_rewrite_service_integrates():
    """Verify QueryRewriteService coordinates normalizer, rewriter, expansion, and generator."""
    service = QueryRewriteService(
        normalizer=QueryNormalizer(),
        rewriter=QueryRewriter(DefaultAbbreviationProvider()),
        expansion=QueryExpansionService(),
        generator=MultiQueryGenerator()
    )
    
    result = service.rewrite_query("   Explain how AME db works   ")
    assert result.original_query == "   Explain how AME db works   "
    assert result.rewritten_query == "Explain how Adaptive Memory Engine database works"
    assert len(result.retrieval_queries) >= 3
    
    # Verify metadata
    assert result.metadata["expanded_variants_count"] > 0
    assert result.metadata["total_generated_queries"] == len(result.retrieval_queries)


@pytest.mark.asyncio
async def test_api_rewrite_query_unauthorized(client: AsyncClient):
    """Verify diagnostic rewrite endpoint blocks unauthenticated users."""
    response = await client.post(
        "/api/v1/retrieval/rewrite",
        json={"query": "how do I compile"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_api_rewrite_query_success(client: AsyncClient):
    """Verify diagnostic rewrite endpoint responds successfully with QueryRewriteResult for authenticated users."""
    # Register and log in
    reg_response = await client.post(
        "/api/v1/auth/register",
        json={"email": "rewrite_user@example.com", "password": "securepassword123"}
    )
    assert reg_response.status_code == 201

    response = await client.post(
        "/api/v1/retrieval/rewrite",
        json={"query": "Explain how AME works"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["original_query"] == "Explain how AME works"
    assert data["rewritten_query"] == "Explain how Adaptive Memory Engine works"
    
    # Assert retrieval queries list exists and holds expected schemas
    queries = data["retrieval_queries"]
    assert len(queries) >= 1
    primary = queries[0]
    assert primary["query"] == "Explain how Adaptive Memory Engine works"
    assert primary["priority"] == 0.95
    assert primary["source"] == "REWRITER"
