import re
import abc
from typing import List, Tuple, Dict, Any
from app.retrieval.domain.value_objects import QueryIntent, RetrievalCapability, RetrievalPlan, RetrievalQuerySource, RetrievalQuery


class QueryNormalizer:
    """
    Syntactic normalizer only.
    Responsibility is strictly limited to structural/formatting normalization 
    (whitespace trimming, spacing consolidation, trailing punctuation formatting) 
    while preserving original casing and semantic meaning.
    
    Spelling corrections, query rewrites, and semantic expansions belong to Phase 3.
    """
    
    def normalize(self, query: str) -> str:
        if not query:
            return ""
        # Trim leading/trailing whitespace
        text = query.strip()
        # Collapse multiple spaces, tabs, and newlines to a single space
        text = re.sub(r"\s+", " ", text)
        # Remove trailing punctuation (except questions, which can aid intent detection)
        text = re.sub(r"[.!]$", "", text)
        return text.strip()


class IntentDetector:
    """Evaluates query text against heuristic patterns to classify intent (case-insensitive internally)."""

    RULES = [
        (QueryIntent.FACT_LOOKUP, ["who is", "what is", "where is", "tell me about", "details of", "fact", "info"]),
        (QueryIntent.SUMMARY, ["summarize", "summary", "overview", "brief", "recap", "long story short"]),
        (QueryIntent.TIMELINE, ["when did", "timeline", "chronology", "before", "after", "history", "date of"]),
        (QueryIntent.RELATIONSHIP, ["related to", "connected to", "how is", "relationship", "connection", "link"]),
        (QueryIntent.COMPARISON, ["compare", "difference", "versus", "vs", "better", "alternative"]),
        (QueryIntent.INSTRUCTION, ["how do i", "how to", "steps for", "guide", "procedure", "instructions"]),
        (QueryIntent.SEARCH, ["search for", "find memories", "look up", "query"]),
        (QueryIntent.MEMORY_RECALL, ["remember", "recall", "do you know", "past"]),
        (QueryIntent.QUESTION, ["why", "how", "what", "can you", "explain"]),
    ]

    def detect_intent(self, normalized_query: str) -> Tuple[QueryIntent, float, List[str]]:
        """
        Scans keywords case-insensitively and returns (QueryIntent, confidence_score, matched_keywords).
        Defaults to UNKNOWN with 0.0 confidence when no rules match.
        """
        if not normalized_query:
            return QueryIntent.UNKNOWN, 0.0, []

        query_lower = normalized_query.lower()

        for intent, keywords in self.RULES:
            matched = [kw for kw in keywords if kw in query_lower]
            if matched:
                confidence = min(0.5 + (0.1 * len(matched)), 1.0)
                return intent, confidence, matched

        # Fallback to question if query ends with "?" or contains questioning words
        if query_lower.endswith("?") or any(w in query_lower for w in ["what", "why", "how", "who"]):
            return QueryIntent.QUESTION, 0.6, ["?"]

        return QueryIntent.UNKNOWN, 0.0, []


class QueryClassifier:
    """Maps intent categories to recommended platform retrieval capabilities."""

    INTENT_MAP = {
        QueryIntent.FACT_LOOKUP: [RetrievalCapability.SEMANTIC_SEARCH],
        QueryIntent.SUMMARY: [RetrievalCapability.SEMANTIC_SEARCH, RetrievalCapability.EPISODIC_SEARCH],
        QueryIntent.TIMELINE: [RetrievalCapability.EPISODIC_SEARCH],
        QueryIntent.RELATIONSHIP: [RetrievalCapability.KNOWLEDGE_GRAPH],
        QueryIntent.COMPARISON: [RetrievalCapability.SEMANTIC_SEARCH, RetrievalCapability.KNOWLEDGE_GRAPH],
        QueryIntent.INSTRUCTION: [RetrievalCapability.PROCEDURAL_SEARCH],
        QueryIntent.SEARCH: [RetrievalCapability.SEMANTIC_SEARCH],
        QueryIntent.MEMORY_RECALL: [RetrievalCapability.SEMANTIC_SEARCH, RetrievalCapability.WORKING_MEMORY],
        QueryIntent.QUESTION: [RetrievalCapability.SEMANTIC_SEARCH, RetrievalCapability.KNOWLEDGE_GRAPH],
        QueryIntent.UNKNOWN: [RetrievalCapability.SEMANTIC_SEARCH],
    }

    def classify(
        self,
        normalized_query: str,
        intent: QueryIntent,
        confidence: float,
        detected_keywords: List[str]
    ) -> RetrievalPlan:
        """Resolves target capabilities and packs them into a RetrievalPlan."""
        capabilities = self.INTENT_MAP.get(intent, [RetrievalCapability.SEMANTIC_SEARCH])
        
        # Check active context triggers in original preserved casing
        query_lower = normalized_query.lower()
        if any(w in query_lower for w in ["this conversation", "our chat", "we just", "currently"]):
            if RetrievalCapability.WORKING_MEMORY not in capabilities:
                capabilities = [RetrievalCapability.WORKING_MEMORY] + capabilities

        metadata = {
            "detected_keywords": detected_keywords,
        }

        return RetrievalPlan(
            intent=intent,
            recommended_capabilities=list(dict.fromkeys(capabilities)),
            confidence=confidence,
            metadata=metadata
        )


class IAbbreviationProvider(abc.ABC):
    """Abstraction for loading technology/platform abbreviation mappings."""
    
    @abc.abstractmethod
    def get_abbreviations(self) -> Dict[str, str]:
        raise NotImplementedError()


class DefaultAbbreviationProvider(IAbbreviationProvider):
    """Standard dictionary-backed provider for project-specific abbreviations."""
    
    def __init__(self):
        self._abbreviations = {
            r"\bame\b": "Adaptive Memory Engine",
            r"\bdb\b": "database",
            r"\bkg\b": "knowledge graph",
            r"\bllm\b": "large language model",
            r"\bpy\b": "Python",
            r"\bjs\b": "JavaScript",
            r"\brag\b": "retrieval augmented generation",
            r"\bapi\b": "application programming interface",
        }
        
    def get_abbreviations(self) -> Dict[str, str]:
        return self._abbreviations


class QueryRewriter:
    """Standardizes raw queries via abbreviation expansions loaded from IAbbreviationProvider."""

    def __init__(self, abbreviation_provider: IAbbreviationProvider):
        self.abbreviation_provider = abbreviation_provider

    def rewrite(self, query: str) -> str:
        if not query:
            return ""
        
        rewritten = query
        abbreviations = self.abbreviation_provider.get_abbreviations()
        
        # Expand target abbreviations case-insensitively while preserving original case elsewhere
        for pattern, replacement in abbreviations.items():
            rewritten = re.sub(pattern, replacement, rewritten, flags=re.IGNORECASE)

        return rewritten.strip()


class QueryExpansionService:
    """
    Rule-based expansions mapping detected entities into search-friendly variant forms.
    
    NOTE: In future phases, these expansion mappings are intended to be backed by 
    external configuration files or registry providers.
    """

    EXPANSION_RULES = {
        "git": ["git version control", "repository commits", "branches"],
        "database": ["database SQL storage", "PostgreSQL tables", "database schema"],
        "db": ["database SQL storage", "PostgreSQL tables", "database schema"],
        "postgres": ["database SQL storage", "PostgreSQL tables"],
        "knowledge graph": ["entity-relationship network", "nodes and relationships", "graph traversal"],
        "kg": ["entity-relationship network", "nodes and relationships", "graph traversal"],
        "memory": ["semantic episodic recall", "long-term memory tiers", "memory consolidation"],
        "memories": ["semantic episodic recall", "long-term memory tiers", "memory consolidation"],
        "reinforce": ["importance confidence score reinforcement", "memory decay feedback"],
        "auth": ["user authentication sessions", "JWT token cookies"],
        "login": ["user authentication sessions", "JWT token cookies"],
    }

    def expand(self, query: str) -> List[str]:
        """Generates retrieval-oriented variant strings based on entity detection."""
        if not query:
            return []

        query_lower = query.lower()
        expanded_variants = []

        for entity, variants in self.EXPANSION_RULES.items():
            if entity in query_lower:
                expanded_variants.extend(variants)

        return list(dict.fromkeys(expanded_variants))  # Deduplicate while preserving order


class MultiQueryGenerator:
    """Assembles multiple prioritized, unique retrieval queries with normalized scores."""

    def generate(self, rewritten_query: str, expanded_variants: List[str]) -> List[RetrievalQuery]:
        """Compiles prioritized candidates and removes duplicates."""
        if not rewritten_query:
            return []

        queries: List[RetrievalQuery] = []
        seen = set()

        def add_query(q_str: str, priority: float, reason: str, source: RetrievalQuerySource) -> None:
            cleaned = q_str.strip().lower()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                queries.append(RetrievalQuery(query=q_str, priority=priority, reason=reason, source=source))

        # 1. Primary query (0.95 priority score)
        add_query(rewritten_query, priority=0.95, reason="Primary query", source=RetrievalQuerySource.REWRITER)

        # 2. Secondary queries: Direct entity expansion variants (0.80 priority score)
        for variant in expanded_variants:
            add_query(variant, priority=0.80, reason="Entity expansion variant", source=RetrievalQuerySource.EXPANSION)

        # 3. Tertiary queries: Simple keyword extraction sub-queries (0.65 priority score)
        words = [w.strip(",.?!()\"'") for w in rewritten_query.split() if len(w) > 4]
        if len(words) >= 2:
            keyword_subquery = " ".join(words[:3])
            add_query(keyword_subquery, priority=0.65, reason="Keyword sub-query", source=RetrievalQuerySource.GENERATOR)

        return queries
