import abc
import uuid
from typing import List, Dict, Any, Optional
from app.retrieval.domain.value_objects import RetrievalCapability, RetrievalQuery, RetrievalResult
from app.domain.entities import AccessContext


class IRetrievalExecutor(abc.ABC):
    """Domain contract for capability-specific retrieval execution tiers."""

    @property
    @abc.abstractmethod
    def capability(self) -> RetrievalCapability:
        raise NotImplementedError()

    @abc.abstractmethod
    async def execute(
        self,
        user_id: uuid.UUID,
        subqueries: List[RetrievalQuery],
        conversation_id: Optional[uuid.UUID] = None,
        limit: int = 10,
        access_context: Optional[AccessContext] = None,
    ) -> List[RetrievalResult]:
        raise NotImplementedError()
