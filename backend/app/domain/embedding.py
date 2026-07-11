import abc
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass
class MemoryEmbedding:
    """
    Domain entity representing the vector embedding representation of a memory,
    along with metadata regarding the provider, model, and configuration used.
    """
    id: uuid.UUID
    memory_id: uuid.UUID
    embedding: List[float]
    provider: str
    model: str
    dimension: int
    created_at: datetime
    updated_at: datetime


class IEmbeddingProvider(abc.ABC):
    """
    Domain contract defining text vector embedding generation capability.
    Implementations interface with external providers (e.g. OpenAI) or local simulators.
    """

    @abc.abstractmethod
    async def get_embedding(self, text: str) -> List[float]:
        """
        Generates a float vector embedding for a single text fragment.
        """
        pass

    @abc.abstractmethod
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generates a batch of float vector embeddings for multiple text fragments.
        """
        pass

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """
        Name of the provider (e.g. 'openai').
        """
        pass

    @property
    @abc.abstractmethod
    def model_name(self) -> str:
        """
        Name of the model (e.g. 'text-embedding-3-small').
        """
        pass

    @property
    @abc.abstractmethod
    def dimension(self) -> int:
        """
        Size/dimension of the generated embedding vectors (e.g. 1536).
        """
        pass
