import abc
import re
from typing import List, Dict, Any, Tuple

from app.knowledge_graph.domain.entities import RelationshipType, Node
from app.knowledge_graph.services.relationship_dictionary import RELATIONSHIP_RULES


class IRelationshipExtractionProvider(abc.ABC):
    """Abstract interface defining the contract for parsing semantic relationship edges from text context."""

    @abc.abstractmethod
    async def extract_relationships(
        self, text: str, nodes: List[Node]
    ) -> List[Dict[str, Any]]:
        """
        Parses text input and extracts relationship triples.
        Returns: [{"source_node": Node, "target_node": Node, "relationship_type": RelationshipType,
                   "matched_pattern": str, "sentence_index": int, "confidence": float}]
        """
        raise NotImplementedError()


class LLMRelationshipProvider(IRelationshipExtractionProvider):
    """Future LLM-based relationship extraction provider stub."""

    async def extract_relationships(
        self, text: str, nodes: List[Node]
    ) -> List[Dict[str, Any]]:
        return []


class RuleBasedRelationshipProvider(IRelationshipExtractionProvider):
    """Deterministic relationship extraction provider using sentence-level subject-predicate-object proximity matching."""

    def __init__(self):
        self.rules = RELATIONSHIP_RULES

    async def extract_relationships(
        self, text: str, nodes: List[Node]
    ) -> List[Dict[str, Any]]:
        if not text or len(nodes) < 2:
            return []

        # 1. Split text into sentences
        sentences = re.split(r"(?<=[.!?])\s+|\n+", text)

        extracted = []
        for sentence_index, sentence in enumerate(sentences):
            if not sentence.strip():
                continue

            # 2. Find all occurrences of the resolved nodes in the sentence
            mentions = []
            for node in nodes:
                aliases = {node.name, node.canonical_name}
                for alias in aliases:
                    pattern = r"\b" + re.escape(alias) + r"\b"
                    for match in re.finditer(pattern, sentence, re.IGNORECASE):
                        mentions.append((match.start(), match.end(), node))

            if len(mentions) < 2:
                continue

            # Resolve overlapping mention spans (prefer longer aliases)
            mentions.sort(key=lambda x: (x[1] - x[0]), reverse=True)
            filtered_mentions = []
            matched_spans = []
            for start, end, node in mentions:
                overlap = False
                for s, e in matched_spans:
                    if not (end <= s or start >= e):
                        overlap = True
                        break
                if not overlap:
                    filtered_mentions.append((start, end, node))
                    matched_spans.append((start, end))

            # Re-sort filtered mentions back to appearance order in the sentence
            filtered_mentions.sort(key=lambda x: x[0])


            # 3. Find all predicate patterns in the sentence
            predicates = []
            for rel_type, rules in self.rules.items():
                for pattern, base_conf in rules:
                    for match in re.finditer(pattern, sentence, re.IGNORECASE):
                        predicates.append((match.start(), match.end(), match.group(0), rel_type, base_conf))

            if not predicates:
                continue

            # Resolve overlapping predicate spans
            predicates.sort(key=lambda x: (x[1] - x[0]), reverse=True)
            filtered_predicates = []
            pred_spans = []
            for start, end, text_pat, rel_type, base_conf in predicates:
                overlap = False
                for s, e in pred_spans:
                    if not (end <= s or start >= e):
                        overlap = True
                        break
                if not overlap:
                    filtered_predicates.append((start, end, text_pat, rel_type, base_conf))
                    pred_spans.append((start, end))

            # Sort predicates back to appearance order
            filtered_predicates.sort(key=lambda x: x[0])

            # 4. Proximity matching for Subject-Predicate-Object triples
            for idx, pred in enumerate(filtered_predicates):
                start_pred, end_pred, text_pat, rel_type, base_conf = pred

                # Subject: the closest entity mention ending before the predicate starts
                subjects = [m for m in filtered_mentions if m[1] <= start_pred]
                subject = max(subjects, key=lambda x: x[1]) if subjects else None

                if not subject:
                    continue

                # Objects: all entities starting after the predicate and before the next predicate starts
                next_pred_start = min(
                    [p[0] for p in filtered_predicates[idx + 1:]],
                    default=len(sentence)
                )
                objects = [
                    m for m in filtered_mentions 
                    if end_pred <= m[0] < next_pred_start
                ]

                # Build triples
                for obj in objects:
                    extracted.append({
                        "source_node": subject[2],
                        "target_node": obj[2],
                        "relationship_type": rel_type,
                        "matched_pattern": text_pat,
                        "sentence_index": sentence_index,
                        "confidence": base_conf,
                    })

        return extracted
