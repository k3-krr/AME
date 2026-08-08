import pytest
import uuid
from httpx import AsyncClient
from app.retrieval.domain.value_objects import QueryIntent, RetrievalCapability
from app.retrieval.domain.services import QueryNormalizer, IntentDetector, QueryClassifier
from app.retrieval.application.query_understanding_service import QueryUnderstandingService


def test_query_normalizer_preserves_case_collapses_spacing():
    """Verify that QueryNormalizer normalizes spacing/punctuation but preserves case."""
    normalizer = QueryNormalizer()
    
    # preserved case
    assert normalizer.normalize("  Tell Me About AME!  ") == "Tell Me About AME"
    assert normalizer.normalize("Multiple   Redundant \n\t  Spaces.") == "Multiple Redundant Spaces"
    assert normalizer.normalize("What is my name?") == "What is my name?"  # preserves question mark
    assert normalizer.normalize("") == ""


def test_intent_detector_case_insensitive_heuristics():
    """Verify IntentDetector matches keywords case-insensitively and computes confidence."""
    detector = IntentDetector()
    
    # Fact lookup check
    intent, confidence, keywords = detector.detect_intent("WHO IS the primary contact?")
    assert intent == QueryIntent.FACT_LOOKUP
    assert confidence > 0.0
    assert "who is" in keywords

    # Instructions check
    intent, confidence, keywords = detector.detect_intent("How to build a kayak")
    assert intent == QueryIntent.INSTRUCTION
    assert confidence > 0.0
    assert "how to" in keywords

    # Question mark fallback
    intent, confidence, keywords = detector.detect_intent("Is there anything else?")
    assert intent == QueryIntent.QUESTION
    assert "?" in keywords

    # Unknown query
    intent, confidence, keywords = detector.detect_intent("Some completely unrelated text.")
    assert intent == QueryIntent.UNKNOWN
    assert confidence == 0.0
    assert not keywords


def test_query_classifier_maps_intents():
    """Verify QueryClassifier maps QueryIntent to RetrievalCapabilities."""
    classifier = QueryClassifier()
    
    # Relationship intent -> Knowledge Graph
    plan = classifier.classify("how is Bob connected to Alice?", QueryIntent.RELATIONSHIP, 0.7, ["connected to"])
    assert plan.intent == QueryIntent.RELATIONSHIP
    assert plan.confidence == 0.7
    assert plan.recommended_capabilities == [RetrievalCapability.KNOWLEDGE_GRAPH]
    assert plan.metadata["detected_keywords"] == ["connected to"]


def test_query_classifier_injects_working_memory():
    """Verify QueryClassifier dynamically prefixes RetrievalCapabilities with WORKING_MEMORY on active context clues."""
    classifier = QueryClassifier()

    # Normal factual query -> SEMANTIC_SEARCH
    plan_normal = classifier.classify("who is user", QueryIntent.FACT_LOOKUP, 0.6, ["who is"])
    assert plan_normal.recommended_capabilities == [RetrievalCapability.SEMANTIC_SEARCH]

    # Factual query referencing this conversation -> prefixes WORKING_MEMORY
    plan_contextual = classifier.classify("in our chat, who is user?", QueryIntent.FACT_LOOKUP, 0.6, ["who is"])
    assert plan_contextual.recommended_capabilities == [RetrievalCapability.WORKING_MEMORY, RetrievalCapability.SEMANTIC_SEARCH]


def test_query_understanding_service_integrates():
    """Verify QueryUnderstandingService coordinates normalizer, detector, and classifier steps."""
    service = QueryUnderstandingService(
        normalizer=QueryNormalizer(),
        detector=IntentDetector(),
        classifier=QueryClassifier()
    )

    result = service.analyze_query("  Tell Me How To build a kayak.  ")
    assert result.original_query == "  Tell Me How To build a kayak.  "
    assert result.normalized_query == "Tell Me How To build a kayak"
    assert result.retrieval_plan.intent == QueryIntent.INSTRUCTION
    assert result.retrieval_plan.recommended_capabilities == [RetrievalCapability.PROCEDURAL_SEARCH]
    assert "how to" in result.retrieval_plan.metadata["detected_keywords"]

    # Test invalid inputs raise value error
    with pytest.raises(ValueError, match="cannot be empty"):
        service.analyze_query("")


@pytest.mark.asyncio
async def test_api_analyze_query_unauthorized(client: AsyncClient):
    """Verify diagnostic analyze endpoint blocks unauthenticated users."""
    response = await client.post(
        "/api/v1/retrieval/analyze",
        json={"query": "who is user"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_api_analyze_query_success(client: AsyncClient):
    """Verify diagnostic analyze endpoint responds successfully with RetrievalPlan for authenticated users."""
    # Register and log in
    reg_response = await client.post(
        "/api/v1/auth/register",
        json={"email": "understanding_user@example.com", "password": "securepassword123"}
    )
    assert reg_response.status_code == 201

    response = await client.post(
        "/api/v1/retrieval/analyze",
        json={"query": "How do I configure git?  "}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["original_query"] == "How do I configure git?  "
    assert data["normalized_query"] == "How do I configure git?"
    assert data["retrieval_plan"]["intent"] == "INSTRUCTION"
    assert data["retrieval_plan"]["recommended_capabilities"] == ["PROCEDURAL_SEARCH"]
    assert "how do i" in data["retrieval_plan"]["metadata"]["detected_keywords"]
