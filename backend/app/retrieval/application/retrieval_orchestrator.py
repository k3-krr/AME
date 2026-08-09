import uuid
import asyncio
from typing import List, Dict, Any, Optional
from app.domain.entities import Memory, AccessContext
from app.domain.repositories import IMemoryStateRepository, IMemoryEmbeddingRepository
from app.domain.embedding import IEmbeddingProvider
from app.application.hybrid_ranking_service import HybridRankingService
from app.retrieval.domain.entities import RetrievalRequest, GroundedContextPackage
from app.retrieval.domain.value_objects import RetrievalResult, PipelineStatus
from app.retrieval.domain.context_fusion_service import ContextFusionService
from app.retrieval.application.query_understanding_service import QueryUnderstandingService
from app.retrieval.application.query_rewrite_service import QueryRewriteService
from app.retrieval.application.executor_registry import ExecutorRegistry
from app.retrieval.application.telemetry import RetrievalTelemetryTracker
from app.config import settings


class RetrievalOrchestrator:
    """Coordinates the retrieval execution pipeline, integrating understanding, rewrite, executors, ranking, and fusion."""

    def __init__(
        self,
        query_understanding_service: QueryUnderstandingService,
        query_rewrite_service: QueryRewriteService,
        executor_registry: ExecutorRegistry,
        hybrid_ranking_service: HybridRankingService,
        embedding_repo: IMemoryEmbeddingRepository,
        memory_state_repo: IMemoryStateRepository,
        context_fusion_service: ContextFusionService,
        embedding_provider: IEmbeddingProvider,
    ):
        self.query_understanding_service = query_understanding_service
        self.query_rewrite_service = query_rewrite_service
        self.executor_registry = executor_registry
        self.hybrid_ranking_service = hybrid_ranking_service
        self.embedding_repo = embedding_repo
        self.memory_state_repo = memory_state_repo
        self.context_fusion_service = context_fusion_service
        self.embedding_provider = embedding_provider

    async def retrieve(
        self,
        user_id: uuid.UUID,
        query: str,
        conversation_id: Optional[uuid.UUID] = None,
        options: Optional[Dict[str, Any]] = None,
        tracker: Optional[RetrievalTelemetryTracker] = None,
        access_context: Optional[AccessContext] = None,
    ) -> GroundedContextPackage:
        is_local_tracker = False
        if not tracker:
            request_id = uuid.uuid4()
            tracker = RetrievalTelemetryTracker(request_id)
            is_local_tracker = True
        
        timeout_val = (options or {}).get("timeout", settings.RETRIEVAL_TIMEOUT_SECONDS)
        
        try:
            package = await asyncio.wait_for(
                self._execute_retrieve(user_id, query, conversation_id, options, tracker, access_context),
                timeout=timeout_val
            )
            tracker.result_count = len(package.fused_elements)
            if is_local_tracker:
                tracker.log_metrics()
            return package
        except asyncio.TimeoutError:
            tracker.success = False
            tracker.error_category = "request_timeout"
            if is_local_tracker:
                tracker.log_metrics()
            raise TimeoutError("Retrieval request timed out")
        except Exception as e:
            tracker.success = False
            if not tracker.error_category:
                tracker.error_category = "system_failure"
            if is_local_tracker:
                tracker.log_metrics()
            raise e


    async def _execute_retrieve(
        self,
        user_id: uuid.UUID,
        query: str,
        conversation_id: Optional[uuid.UUID] = None,
        options: Optional[Dict[str, Any]] = None,
        tracker: Optional[RetrievalTelemetryTracker] = None,
        access_context: Optional[AccessContext] = None,
    ) -> GroundedContextPackage:
        if not tracker:
            tracker = RetrievalTelemetryTracker()
            
        pipeline_status = PipelineStatus.SUCCESS
        
        # 1. Analyze query to resolve intent and recommended capabilities
        with tracker.time_stage("query_analysis"):
            analysis_result = self.query_understanding_service.analyze_query(query)
            plan = analysis_result.retrieval_plan
        
        # 2. Rewrite query and compile prioritized subqueries
        with tracker.time_stage("query_rewrite"):
            rewrite_result = self.query_rewrite_service.rewrite_query(query)
            subqueries = rewrite_result.retrieval_queries
        
        # 3. Select and execute capability-specific executors sequentially
        # Concurrency safety: AsyncSession is not safe for concurrent database calls.
        retrieval_results: List[RetrievalResult] = []
        limit = (options or {}).get("limit_per_system", 10)
        
        with tracker.time_stage("retrieval_executors"):
            for capability in plan.recommended_capabilities:
                tracker.capability_usage.append(capability.value)
                executor = self.executor_registry.get_executor(capability)
                if executor:
                    try:
                        res = await executor.execute(
                            user_id=user_id,
                            subqueries=subqueries,
                            conversation_id=conversation_id,
                            limit=limit,
                            access_context=access_context,
                        )
                        retrieval_results.extend(res)
                    except Exception:
                        pipeline_status = PipelineStatus.DEGRADED
                        tracker.error_category = "executor_failure"
                        
        if not retrieval_results:
            # Return fallback context package if no candidates fetched
            return GroundedContextPackage(
                request_id=tracker.request_id,
                retrieved_memories=[],
                fused_elements=[],
                metadata={
                    "intent": plan.intent.value,
                    "confidence": plan.confidence,
                    "rewritten_query": rewrite_result.rewritten_query,
                    "fallback": True,
                },
                status=pipeline_status
            )

        # 4. Deduplicate memories by ID to build ranking lists
        unique_memories_map: Dict[uuid.UUID, Memory] = {}
        for res in retrieval_results:
            unique_memories_map[res.memory.id] = res.memory
            
        memories = list(unique_memories_map.values())
        
        # Defense-in-depth check
        if access_context:
            from app.domain.entities import MemoryStatus
            for memory in memories:
                if memory.user_id != access_context.tenant_id:
                    raise ValueError("Security violation: Tenant boundary mismatch detected.")
                if access_context.principal_type.value == "AGENT" and memory.status == MemoryStatus.DELETED:
                    raise ValueError("Security violation: DELETED memory access attempted.")

        memory_ids = list(unique_memories_map.keys())
        
        # 5. Fetch associated state records for recency/access weight checks
        try:
            states = await self.memory_state_repo.get_by_memory_ids(memory_ids)
        except Exception:
            states = []
            pipeline_status = PipelineStatus.DEGRADED
            tracker.error_category = "states_load_failure"
        
        # 6. Generate embedding for primary rewritten query to calculate cosine similarities
        primary_query = rewrite_result.rewritten_query
        try:
            query_embedding = await self.embedding_provider.get_embedding(primary_query)
        except Exception:
            query_embedding = None
            pipeline_status = PipelineStatus.DEGRADED
            tracker.error_category = "embedding_failure"
        
        semantic_scores: Dict[uuid.UUID, float] = {}
        for memory in memories:
            if query_embedding:
                try:
                    emb = await self.embedding_repo.get_by_memory_id(memory.id)
                    if emb:
                        dot = sum(x * y for x, y in zip(query_embedding, emb.embedding))
                        mag1 = sum(x * x for x in query_embedding) ** 0.5
                        mag2 = sum(x * x for x in emb.embedding) ** 0.5
                        similarity = dot / (mag1 * mag2) if (mag1 > 0 and mag2 > 0) else 0.0
                        semantic_scores[memory.id] = similarity
                    else:
                        semantic_scores[memory.id] = 0.0
                except Exception:
                    semantic_scores[memory.id] = 0.0
            else:
                semantic_scores[memory.id] = 0.0
                
        # 7. Rank memories using existing HybridRankingService
        with tracker.time_stage("ranking"):
            try:
                ranked_tuples = self.hybrid_ranking_service.rank_hybrid_memories(
                    memories=memories,
                    states=states,
                    semantic_scores=semantic_scores,
                )
            except Exception:
                # Safe degradation fallback: retain deterministic executor sequence without new weights
                ranked_tuples = [(m, 0.0) for m in memories]
                pipeline_status = PipelineStatus.DEGRADED
                tracker.error_category = "ranking_failure"
        
        # 8. Compile GroundedContextPackage using ContextFusionService
        with tracker.time_stage("fusion"):
            package_metadata = {
                "intent": plan.intent.value,
                "confidence": plan.confidence,
                "rewritten_query": rewrite_result.rewritten_query,
            }
            package = self.context_fusion_service.fuse(
                request_id=tracker.request_id,
                ranked_memories=ranked_tuples,
                retrieval_results=retrieval_results,
                metadata=package_metadata,
            )
            package.status = pipeline_status
        
        return package
