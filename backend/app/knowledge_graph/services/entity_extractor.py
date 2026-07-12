from typing import List, Dict, Any

from app.knowledge_graph.services.extraction_provider import IEntityExtractionProvider


class EntityExtractor:
    """Orchestrates named entity extraction and name canonicalization/alias mapping."""

    def __init__(self, provider: IEntityExtractionProvider):
        self.provider = provider

    async def extract(self, text: str) -> List[Dict[str, Any]]:
        """
        Extracts entities from text using the configured provider,
        applies name canonicalization, and returns resolved details.
        """
        raw_entities = await self.provider.extract_entities(text)

        canonicalized_entities = []
        for raw in raw_entities:
            name = raw.get("name")
            entity_type = raw.get("entity_type")
            if not name or not name.strip() or not entity_type:
                continue

            canonical_name = self.canonicalize(name)
            canonicalized_entities.append({
                "name": canonical_name,
                "entity_type": entity_type
            })

        return canonicalized_entities

    def canonicalize(self, name: str) -> str:
        """Applies explicit casing and alias mapping normalization rules."""
        cleaned = name.strip()
        normalized_key = " ".join(cleaned.lower().split())

        # Canonical map containing standard casing and alias translations
        canonical_map = {
            "fastapi": "FastAPI",
            "fast api": "FastAPI",
            "fast_api": "FastAPI",
            "postgresql": "PostgreSQL",
            "postgres": "PostgreSQL",
            "mongodb": "MongoDB",
            "next.js": "Next.js",
            "nextjs": "Next.js",
            "spring boot": "Spring Boot",
            "springboot": "Spring Boot",
            "python": "Python",
            "rust": "Rust",
            "docker": "Docker",
            "kubernetes": "Kubernetes",
            "openai": "OpenAI",
            "openai api": "OpenAI API",
            "ame": "AME",
            "adaptive memory engine": "AME",
            "github": "GitHub",
            "github api": "GitHub API",
            "js": "JavaScript",
            "javascript": "JavaScript",
            "ts": "TypeScript",
            "typescript": "TypeScript",
            "mysql": "MySQL",
            "sqlite": "SQLite",
            "redis": "Redis",
            "graphql": "GraphQL",
            "grpc": "gRPC",
            "django": "Django",
            "flask": "Flask",
            "react": "React",
            "vue": "Vue",
            "angular": "Angular",
            "express": "Express",
            "laravel": "Laravel",
            "pytorch": "PyTorch",
            "tensorflow": "TensorFlow",
            "cassandra": "Cassandra",
            "neo4j": "Neo4j",
            "dynamodb": "DynamoDB",
            "rest api": "REST API",
            "stripe api": "Stripe API",
            "google": "Google",
            "microsoft": "Microsoft",
            "apple": "Apple",
            "amazon": "Amazon",
            "meta": "Meta",
            "anthropic": "Anthropic",
            "copilot": "Copilot",
            "ruby": "Ruby",
            "php": "PHP",
            "swift": "Swift",
            "kotlin": "Kotlin",
            "go": "Go",
            "java": "Java",
            "c++": "C++",
            "c#": "C#",
            "linux": "Linux",
            "aws": "AWS",
            "gcp": "GCP",
            "azure": "Azure",
            "vector db": "Vector DB",
            "llm": "LLM",
        }

        return canonical_map.get(normalized_key, cleaned)
