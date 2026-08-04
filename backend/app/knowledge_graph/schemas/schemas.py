import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from app.knowledge_graph.domain.entities import EntityType, RelationshipType


# --- Entity (Node Table) Schemas ---

class EntityCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Raw entity name")
    canonical_name: Optional[str] = Field(None, max_length=255, description="Optional custom canonical name")
    entity_type: EntityType = Field(..., description="Classification category for the entity")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional properties of the entity")


class EntityUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Updated entity name")
    canonical_name: Optional[str] = Field(None, max_length=255, description="Updated canonical name")
    entity_type: Optional[EntityType] = Field(None, description="Updated entity type category")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated metadata dictionary")


class EntityResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    canonical_name: str
    entity_type: EntityType
    metadata: Dict[str, Any] = Field(..., alias="metadata")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


# --- Relationship (Edge Table) Schemas ---

class RelationshipCreateRequest(BaseModel):
    source_entity_id: uuid.UUID = Field(..., description="UUID of source entity node")
    target_entity_id: uuid.UUID = Field(..., description="UUID of target entity node")
    relationship_type: RelationshipType = Field(..., description="Edge predicate semantic relationship type")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence of connection assertion")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional predicate context attributes")


class RelationshipUpdateRequest(BaseModel):
    relationship_type: Optional[RelationshipType] = Field(None, description="Updated predicate relationship type")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Updated confidence value")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated metadata dictionary")


class RelationshipResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    source_node_id: uuid.UUID = Field(..., alias="source_entity_id")
    target_node_id: uuid.UUID = Field(..., alias="target_entity_id")
    relationship_type: RelationshipType
    confidence: float
    metadata: Dict[str, Any] = Field(..., alias="metadata")
    created_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


# --- Traversal Schemas (Phase 4) ---

class TraversalMetadata(BaseModel):
    traversal_strategy: str
    max_depth: int
    traversal_depth: int
    visited_node_count: int
    visited_relationship_count: int
    path_length: Optional[int] = None
    execution_time_ms: float
    termination_reason: str


class TraversalNodeInfo(BaseModel):
    node: EntityResponse
    depth: int


class TraversalResponse(BaseModel):
    nodes: list[TraversalNodeInfo]
    metadata: TraversalMetadata


class PathResponse(BaseModel):
    nodes: list[EntityResponse]
    relationships: list[RelationshipResponse]
    hop_count: int
    metadata: TraversalMetadata


class NeighborResponse(BaseModel):
    node: EntityResponse
    relationship: RelationshipResponse
    direction: str

