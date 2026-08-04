from typing import List, Dict, Any

from app.knowledge_graph.domain.entities import Node
from app.knowledge_graph.services.relationship_provider import IRelationshipExtractionProvider


class RelationshipBuilder:
    """Orchestrates semantic relationship extraction utilizing the configured provider."""

    def __init__(self, provider: IRelationshipExtractionProvider):
        self.provider = provider

    async def build_relationships(
        self, text: str, nodes: List[Node]
    ) -> List[Dict[str, Any]]:
        """Invokes the underlying extraction provider to parse subject-predicate-object triples."""
        return await self.provider.extract_relationships(text, nodes)
