from app.knowledge_graph.domain.entities import RelationshipType

# Rules mapping RelationshipType to a list of tuples (regex_pattern, base_confidence).
# These patterns will be matched against the text between two entities inside a sentence.
RELATIONSHIP_RULES = {
    RelationshipType.USES: [
        (r"\buses\b", 0.98),
        (r"\busing\b", 0.95),
        (r"\butilizes\b", 0.98),
        (r"\butilizing\b", 0.95),
        (r"\bbuilt with\b", 0.90),
        (r"\bruns on\b", 0.92),
    ],
    RelationshipType.INDEXED_BY: [
        (r"\bindexed by\b", 0.98),
        (r"\bindexed\b", 0.90),
    ],
    RelationshipType.DEPENDS_ON: [
        (r"\bdepends on\b", 0.98),
        (r"\bdependent on\b", 0.95),
        (r"\bdepends\b", 0.90),
        (r"\brequires\b", 0.98),
    ],
    RelationshipType.IMPLEMENTS: [
        (r"\bimplements\b", 0.98),
        (r"\bimplementing\b", 0.95),
    ],
    RelationshipType.REFERENCES: [
        (r"\breferences\b", 0.98),
        (r"\breferencing\b", 0.95),
    ],
    RelationshipType.PART_OF: [
        (r"\bpart of\b", 0.98),
        (r"\bbelongs to\b", 0.98),
    ],
    RelationshipType.CREATED_BY: [
        (r"\bcreated by\b", 0.98),
        (r"\bbuilt by\b", 0.95),
    ],
    RelationshipType.LOCATED_IN: [
        (r"\blocated in\b", 0.98),
        (r"\bruns in\b", 0.95),
        (r"\brunning in\b", 0.95),
    ],
}
