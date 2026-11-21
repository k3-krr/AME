import uuid
import logging
from typing import Optional
from app.domain.entities import MemoryType, ExtractionStatus, ExtractionAction
from app.domain.repositories import IMessageRepository, IMemoryExtractionRepository
from app.application.extraction_provider import IExtractionProvider
from app.application.duplicate_detection_service import DuplicateDetectionService
from app.application.memory_update_service import MemoryUpdateService

logger = logging.getLogger("ame_backend.extraction_service")

class MemoryExtractionService:
    """
    Orchestrates the dialogue extraction pipeline: fetching conversation turns,
    invoking the LLM parser, evaluating duplicates/conflicts, applying updates,
    and writing audit logs.
    """

    def __init__(
        self,
        extraction_provider: IExtractionProvider,
        duplicate_detection_service: DuplicateDetectionService,
        memory_update_service: MemoryUpdateService,
        extraction_repo: IMemoryExtractionRepository,
        message_repo: IMessageRepository
    ):
        self.extraction_provider = extraction_provider
        self.duplicate_detection_service = duplicate_detection_service
        self.memory_update_service = memory_update_service
        self.extraction_repo = extraction_repo
        self.message_repo = message_repo

    async def extract_memories_from_turns(
        self, conversation_id: uuid.UUID, message_id: Optional[uuid.UUID] = None
    ) -> uuid.UUID:
        """
        Extracts memory candidates from dialogue history turns and persists decisions.
        """
        # 1. Fetch dialogue history turns (up to 10 turns for context)
        messages = await self.message_repo.list_by_conversation(
            conversation_id=conversation_id, limit=10
        )

        # Sort chronologically (oldest to newest)
        messages.sort(key=lambda m: m.created_at)

        dialogue_turns = [
            {"role": m.sender_role, "content": m.content}
            for m in messages
        ]

        if not dialogue_turns:
            ext = await self.extraction_repo.create_extraction(
                conversation_id=conversation_id,
                message_id=message_id,
                status=ExtractionStatus.IGNORED,
                error_message="No dialogue turns found."
            )
            return ext.id

        candidates_to_log = []
        try:
            # 2. Call OpenAI Extraction Provider to parse dialogue turns
            candidates_data = await self.extraction_provider.extract_candidates(dialogue_turns)

            # 3. Assess overlap relationships
            for item in candidates_data:
                content = item.get("content")
                if not content or not content.strip():
                    continue

                type_str = item.get("memory_type")
                try:
                    memory_type = MemoryType(type_str)
                except ValueError:
                    logger.warning(f"Unknown memory type '{type_str}' returned by LLM. Defaulting to Fact.")
                    memory_type = MemoryType.FACT

                importance = float(item.get("importance", 0.5))
                confidence = float(item.get("confidence", 0.5))

                action, target_id, final_content = await self.duplicate_detection_service.analyze_candidate(
                    conversation_id=conversation_id,
                    candidate_content=content,
                    memory_type=memory_type,
                    importance=importance,
                    confidence=confidence
                )

                candidates_to_log.append((content, memory_type, importance, confidence, action, target_id, final_content))

            # 4. Save main audit log
            status = ExtractionStatus.SUCCESS if candidates_to_log else ExtractionStatus.IGNORED
            extraction = await self.extraction_repo.create_extraction(
                conversation_id=conversation_id,
                message_id=message_id,
                status=status
            )

            # 5. Apply modifications and log items
            for content, m_type, imp, conf, action, target_id, final_content in candidates_to_log:
                resolved_id = await self.memory_update_service.apply_action(
                    conversation_id=conversation_id,
                    content=final_content or content,
                    memory_type=m_type,
                    importance=imp,
                    confidence=conf,
                    action=action,
                    target_memory_id=target_id
                )

                await self.extraction_repo.add_candidate(
                    extraction_id=extraction.id,
                    content=content,
                    memory_type=m_type,
                    importance_score=imp,
                    confidence_score=conf,
                    action_taken=action,
                    target_memory_id=resolved_id
                )

            # 6. Update memory_status of processed pending messages
            new_status = "consolidated" if candidates_to_log else "ignored"
            for m in messages:
                if m.memory_status == "pending":
                    m.memory_status = new_status

            await self.message_repo.session.flush()
            return extraction.id

        except Exception as e:
            logger.error(f"Autonomous extraction failed: {e}", exc_info=True)
            # Fail closed: Set pending messages to ignored on failure so they don't hang as pending forever
            for m in messages:
                if m.memory_status == "pending":
                    m.memory_status = "ignored"

            extraction = await self.extraction_repo.create_extraction(
                conversation_id=conversation_id,
                message_id=message_id,
                status=ExtractionStatus.FAILED,
                error_message=str(e)
            )
            await self.message_repo.session.flush()
            return extraction.id
