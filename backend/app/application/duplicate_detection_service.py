import uuid
from typing import Optional, Tuple
from app.domain.entities import MemoryType, ExtractionAction
from app.domain.repositories import IMemoryEmbeddingRepository, IMemoryRepository, IConversationRepository
from app.domain.embedding import IEmbeddingProvider
from app.application.extraction_provider import IExtractionProvider

class DuplicateDetectionService:
    """
    Service responsible for checking semantic duplicate memory candidates
    and evaluating relations (reinforce, merge, overwrite).
    """

    def __init__(
        self,
        embedding_repo: IMemoryEmbeddingRepository,
        embedding_provider: IEmbeddingProvider,
        memory_repo: IMemoryRepository,
        conversation_repo: IConversationRepository,
        extraction_provider: IExtractionProvider,
        similarity_threshold: float = 0.82
    ):
        self.embedding_repo = embedding_repo
        self.embedding_provider = embedding_provider
        self.memory_repo = memory_repo
        self.conversation_repo = conversation_repo
        self.extraction_provider = extraction_provider
        self.similarity_threshold = similarity_threshold

    async def analyze_candidate(
        self,
        conversation_id: uuid.UUID,
        candidate_content: str,
        memory_type: MemoryType,
        importance: float,
        confidence: float
    ) -> Tuple[ExtractionAction, Optional[uuid.UUID], Optional[str]]:
        """
        Determines what action to perform on a candidate memory.
        Returns (action_taken, target_memory_id, final_content).
        """
        # 1. Fetch user_id from conversation
        conversation = await self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise KeyError("Conversation not found")
        user_id = conversation.user_id

        # 2. Generate candidate embedding
        vector = await self.embedding_provider.get_embedding(candidate_content)

        # 3. Perform vector similarity search
        matches = await self.embedding_repo.similarity_search(
            user_id=user_id,
            query_embedding=vector,
            top_k=3,
            memory_type=memory_type
        )
        
        # Filter matches strictly above threshold
        candidate_matches = [m for m in matches if m[1] >= self.similarity_threshold]

        if not candidate_matches:
            # Check basic threshold: if candidate matches min quality
            if importance >= 0.5 and confidence >= 0.5:
                return ExtractionAction.CREATE, None, None
            return ExtractionAction.IGNORE, None, None

        # 4. Fetch similar memories
        matched_ids = [m[0] for m in candidate_matches]
        memories = await self.memory_repo.get_by_ids(matched_ids)
        memory_tuples = [(m.id, m.content) for m in memories]

        # 5. Call LLM to evaluate relationship
        eval_result = await self.extraction_provider.evaluate_relationship(
            candidate_content, memory_tuples
        )

        action = ExtractionAction(eval_result["relationship"])
        target_id = eval_result.get("target_id")
        merged_content = eval_result.get("merged_content")

        return action, target_id, merged_content
