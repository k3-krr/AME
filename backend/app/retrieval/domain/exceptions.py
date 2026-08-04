class RetrievalError(Exception):
    """Base exception for all retrieval module errors."""
    pass


class StrategyNotFoundError(RetrievalError):
    """Raised when a requested retrieval strategy is not registered."""
    pass


class PipelineExecutionError(RetrievalError):
    """Raised when a retrieval pipeline step execution fails."""
    pass
