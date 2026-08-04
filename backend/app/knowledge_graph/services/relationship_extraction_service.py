import uuid
import logging
from typing import List

from app.knowledge_graph.domain.entities import Node, Relationship
from app.knowledge_graph.services.relationship_builder import RelationshipBuilder
from app.knowledge_graph.services.relationship_service import RelationshipService

logger = logging.getLogger("ame_backend.relationship_extraction_service")


class RelationshipExtractionService:
    """
    Coordinates semantic relationship extraction: running the extraction builder,
    resolving relationships through RelationshipService, and populating debug metadata.
    """

    def __init__(
        self,
        builder: RelationshipBuilder,
        relationship_service: RelationshipService,
    ):
        self.builder = builder
        self.relationship_service = relationship_service

    async def extract_and_build_relationships(
        self,
        user_id: uuid.UUID,
        memory_id: uuid.UUID,
        content: str,
        nodes: List[Node],
    ) -> List[Relationship]:
        """
        Runs extraction pipeline on memory content and maps relationships.
        Returns the resolved Relationship records.
        """
        if not content or len(nodes) < 2:
            return []

        # 1. Extract relationship triples from text
        triples = await self.builder.build_relationships(content, nodes)

        relationships = []
        for triple in triples:
            source = triple["source_node"]
            target = triple["target_node"]
            rel_type = triple["relationship_type"]
            matched_pattern = triple["matched_pattern"]
            sentence_index = triple["sentence_index"]
            confidence = triple["confidence"]

            # 2. Build metadata payload containing debugging context
            metadata = {
                "extraction_source": "rule_based",
                "extractor_version": "1.0.0",
                "source_memory_id": str(memory_id),
                "matched_pattern": matched_pattern,
                "sentence_index": sentence_index,
                "confidence": confidence,
            }

            try:
                # 3. Resolve relationship edge, enforcing self-loop blocks during extraction
                rel = await self.relationship_service.resolve_relationship(
                    user_id=user_id,
                    source_node_id=source.id,
                    target_node_id=target.id,
                    relationship_type=rel_type,
                    confidence=confidence,
                    metadata=metadata,
                    prevent_self_loops=True,
                )
                relationships.append(rel)
            except Exception as e:
                logger.error(
                    f"Failed to resolve relationship edge {source.name} -> {target.name} ({rel_type.value}): {e}",
                    exc_info=True,
                )

        return relationships
