import uuid
from typing import List

from app.knowledge_graph.services.entity_extractor import EntityExtractor
from app.knowledge_graph.services.entity_service import EntityService
from app.knowledge_graph.services.graph_service import GraphService


class EntityExtractionService:
    """
    Service layer orchestrating the entity extraction pipeline:
    extracting canonicalized entities from text, resolving Node records,
    and linking them via Memory-Node mapping structures.
    """

    def __init__(
        self,
        extractor: EntityExtractor,
        entity_service: EntityService,
        graph_service: GraphService,
    ):
        self.extractor = extractor
        self.entity_service = entity_service
        self.graph_service = graph_service

    async def extract_and_map_entities(
        self,
        user_id: uuid.UUID,
        memory_id: uuid.UUID,
        content: str,
    ) -> List[uuid.UUID]:
        """
        Extracts, canonicalizes, resolves, and maps entities from a memory.
        Returns the list of resolved Node IDs.
        """
        if not content or not content.strip():
            return []

        # 1. Run raw extraction and canonicalization
        extracted = await self.extractor.extract(content)

        node_ids = []
        for item in extracted:
            name = item["name"]
            entity_type = item["entity_type"]

            # 2. Node Resolution (searches existing node by canonical name, or creates a new one)
            # Passes confidence and source metadata for the entity record
            node = await self.entity_service.resolve_entity(
                user_id=user_id,
                name=name,
                entity_type=entity_type,
                metadata={
                    "extraction_source": "rule_based",
                    "confidence": 1.0,
                }
            )

            # 3. Memory ↔ Node Mapping
            await self.graph_service.create_memory_node_mapping(
                user_id=user_id,
                memory_id=memory_id,
                node_id=node.id,
                confidence=1.0,
            )

            node_ids.append(node.id)

        return node_ids
