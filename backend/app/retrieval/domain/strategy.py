import abc
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from app.retrieval.domain.entities import RetrievalRequest, GroundedContextPackage
from app.retrieval.domain.value_objects import QueryIntent, ContextFusionElement

@dataclass
class RetrievalContextState:
    """Context state passed sequentially through execution steps."""
    request: RetrievalRequest
    query_intent: Optional[QueryIntent] = None
    rewritten_query: Optional[str] = None
    fused_elements: List[ContextFusionElement] = field(default_factory=list)
    grounded_package: Optional[GroundedContextPackage] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class IRetrievalStep(abc.ABC):
    """Enforces standard interface execution across modular retrieval modules."""
    
    @property
    @abc.abstractmethod
    def name(self) -> str:
        pass

    @abc.abstractmethod
    async def execute(self, state: RetrievalContextState) -> RetrievalContextState:
        pass


class IRetrievalStrategy(abc.ABC):
    """Abstraction specifying step composition policies based on query analysis."""
    
    @property
    @abc.abstractmethod
    def name(self) -> str:
        pass

    @abc.abstractmethod
    def resolve_steps(self, request: RetrievalRequest) -> List[IRetrievalStep]:
        """Resolves sequence of steps to run for a given request."""
        raise NotImplementedError()
