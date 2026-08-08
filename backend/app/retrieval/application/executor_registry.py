from typing import List, Optional
from app.retrieval.domain.value_objects import RetrievalCapability
from app.retrieval.domain.executor import IRetrievalExecutor


class ExecutorRegistry:
    """Dynamic mapping registry resolving executor instances by capability."""
    
    def __init__(self, executors: List[IRetrievalExecutor]):
        self._executors = {e.capability: e for e in executors}

    def get_executor(self, capability: RetrievalCapability) -> Optional[IRetrievalExecutor]:
        return self._executors.get(capability)
