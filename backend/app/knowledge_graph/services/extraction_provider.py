import abc
import re
from typing import List, Dict, Any

from app.knowledge_graph.domain.entities import EntityType
from app.knowledge_graph.services.entity_dictionary import RULES


class IEntityExtractionProvider(abc.ABC):
    """Abstract interface defining the contract for parsing entity nodes from text context."""

    @abc.abstractmethod
    async def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Parses text input and extracts list of entities.
        Returns format: [{"name": str, "entity_type": EntityType}]
        """
        raise NotImplementedError()


class LLMEntityExtractionProvider(IEntityExtractionProvider):
    """Future LLM-based entity extraction provider stub implementation."""

    async def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        # LLM entity extraction belongs to future milestones
        return []


class RuleBasedProvider(IEntityExtractionProvider):
    """Deterministic named entity extraction provider relying on regular expressions and dictionary mappings."""

    def __init__(self):
        self.rules = RULES

    async def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Matches regular expressions from RULES, resolving overlapping substrings."""
        if not text or not text.strip():
            return []

        all_matches = []
        for entity_type, patterns in self.rules.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    start, end = match.span()
                    matched_text = match.group(0)
                    all_matches.append((start, end, matched_text, entity_type))

        # Sort matches by length descending to prefer matching longer compounds
        # (e.g. "Stripe API" over "API"), preventing subset substring overlap conflicts
        all_matches.sort(key=lambda x: (x[1] - x[0]), reverse=True)

        extracted = []
        matched_intervals = []

        for start, end, matched_text, entity_type in all_matches:
            # Check overlap against already matched intervals
            overlap = False
            for s, e in matched_intervals:
                if not (end <= s or start >= e):
                    overlap = True
                    break
            if not overlap:
                matched_intervals.append((start, end))
                extracted.append({
                    "name": matched_text,
                    "entity_type": entity_type
                })

        return extracted
