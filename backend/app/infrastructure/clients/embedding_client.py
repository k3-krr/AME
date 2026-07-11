import hashlib
import json
import logging
import random
from typing import List
import httpx

from app.config import settings
from app.domain.embedding import IEmbeddingProvider

logger = logging.getLogger("ame_backend.embedding_client")


class OpenAIEmbeddingProvider(IEmbeddingProvider):
    """
    Infrastructure implementation of IEmbeddingProvider interfacing with OpenAI's
    Embeddings API or falling back to a deterministic simulation vector when
    no OpenAI API key is configured.
    """

    def __init__(self):
        # We can dynamically pull model configuration from settings
        # Defaulting to OpenAI standard text-embedding-3-small (1536 dimensions)
        self._model = getattr(settings, "EMBEDDING_MODEL", "text-embedding-3-small")
        self._dimension = 1536

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    async def get_embedding(self, text: str) -> List[float]:
        """
        Generates a 1536-dimensional float vector embedding for the input text.
        """
        api_key = settings.OPENAI_API_KEY

        if api_key and api_key != "your-openai-api-key-here":
            try:
                embeddings = await self._query_openai([text])
                if embeddings:
                    return embeddings[0]
            except Exception as e:
                logger.error(f"Error querying OpenAI Embeddings API: {e}")
                logger.info("Falling back to local simulated embedding.")
        
        return self._generate_simulated_embedding(text)

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generates 1536-dimensional float vector embeddings for a batch of text inputs.
        """
        api_key = settings.OPENAI_API_KEY

        if api_key and api_key != "your-openai-api-key-here":
            try:
                return await self._query_openai(texts)
            except Exception as e:
                logger.error(f"Error querying OpenAI Embeddings API for batch: {e}")
                logger.info("Falling back to local simulated embeddings for batch.")
        
        return [self._generate_simulated_embedding(text) for text in texts]

    async def _query_openai(self, inputs: List[str]) -> List[List[float]]:
        """Queries the official OpenAI embeddings endpoint."""
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "input": inputs,
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers=headers,
                json=payload,
            )
            if response.status_code != 200:
                error_text = response.text
                raise RuntimeError(
                    f"OpenAI Embeddings API error: {response.status_code} - {error_text}"
                )
            
            data = response.json()
            # Extract embeddings preserving input order
            results = [item["embedding"] for item in data["data"]]
            return results

    def _generate_simulated_embedding(self, text: str) -> List[float]:
        """
        Generates a deterministic unit-length normalized simulated embedding vector (1536 dims)
        seeded from the hash value of the input text.
        """
        if not text:
            # Return zero vector for empty text
            return [0.0] * self._dimension

        # Generate a stable seed from the SHA-256 hash of the input content
        hasher = hashlib.sha256(text.encode("utf-8"))
        seed = int(hasher.hexdigest(), 16) % (2**32)
        rng = random.Random(seed)

        # Draw values from standard normal distribution
        vector = [rng.uniform(-1.0, 1.0) for _ in range(self._dimension)]
        
        # Normalize the vector to unit length (L2 norm = 1.0)
        # This guarantees correct mathematical properties for Cosine Similarity
        magnitude = sum(x * x for x in vector) ** 0.5
        if magnitude > 0:
            vector = [x / magnitude for x in vector]
        
        return vector
