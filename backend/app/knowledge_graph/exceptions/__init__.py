class KnowledgeGraphError(Exception):
    """Base exception for all Knowledge Graph context errors."""
    pass


class EntityNotFoundError(KnowledgeGraphError):
    """Raised when a specific Entity node cannot be retrieved from the store."""
    pass


class RelationshipNotFoundError(KnowledgeGraphError):
    """Raised when a specific Relationship edge cannot be retrieved from the store."""
    pass


class DuplicateEntityError(KnowledgeGraphError):
    """Raised when an Entity with the same canonical name already exists for the user."""
    pass


class DuplicateRelationshipError(KnowledgeGraphError):
    """Raised when a Relationship with identical endpoints and type already exists for the user."""
    pass
