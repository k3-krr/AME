import logging
from typing import Dict, List
from app.retrieval.domain.entities import RetrievalRequest, GroundedContextPackage
from app.retrieval.domain.strategy import IRetrievalStrategy, RetrievalContextState
from app.retrieval.domain.exceptions import StrategyNotFoundError

logger = logging.getLogger("ame_backend.retrieval.orchestrator")


class RetrievalPipelineOrchestrator:
    """Coordinates dynamic retrieval strategy resolution and pipeline execution."""

    def __init__(self, strategies: List[IRetrievalStrategy], default_strategy_name: str = "standard_rag"):
        self._strategies: Dict[str, IRetrievalStrategy] = {s.name: s for s in strategies}
        self._default_strategy_name = default_strategy_name

    async def execute_retrieval(self, request: RetrievalRequest) -> GroundedContextPackage:
        """Resolves strategy, runs steps sequentially, and outputs GroundedContextPackage."""
        request.validate()

        # 1. Resolve strategy from query options or configuration
        strategy_name = request.options.get("strategy", self._default_strategy_name)
        strategy = self._strategies.get(strategy_name)
        
        if not strategy:
            logger.warning(f"Strategy {strategy_name} not registered. Falling back to default.")
            strategy = self._strategies.get(self._default_strategy_name)
            
        if not strategy:
            raise StrategyNotFoundError(f"No valid retrieval strategy resolved for: {strategy_name}")

        # 2. Compile dynamic list of steps
        steps = strategy.resolve_steps(request)
        state = RetrievalContextState(request=request)
        state.metadata["resolved_strategy"] = strategy.name

        # 3. Sequentially execute steps
        for step in steps:
            logger.debug(f"Executing retrieval pipeline step: {step.name}")
            state = await step.execute(state)

        # 4. Extract package or generate minimal fallback
        if not state.grounded_package:
            state.grounded_package = GroundedContextPackage(
                request_id=request.id,
                retrieved_memories=[],
                fused_elements=[],
                metadata={"resolved_strategy": strategy.name, "fallback": True}
            )

        return state.grounded_package
