import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, List, Optional
import logging

from app.domain.repositories import (
    IConversationRepository,
    IMessageRepository,
    ILLMService,
    IMemoryService,
)
from app.infrastructure.db.models import ConversationTable, MessageTable

logger = logging.getLogger("ame_backend.chat_service")


class ChatService:
    """
    Application service orchestrating chat use cases: managing conversation canvas sessions
    and handling streaming dialogue history.
    """

    def __init__(
        self,
        conversation_repo: IConversationRepository,
        message_repo: IMessageRepository,
        llm_service: ILLMService,
        memory_service: IMemoryService,
    ):
        self.conversation_repo = conversation_repo
        self.message_repo = message_repo
        self.llm_service = llm_service
        self.memory_service = memory_service

    async def list_conversations(
        self, user_id: uuid.UUID, page: int, limit: int
    ) -> List[ConversationTable]:
        """Lists conversations for a given user sorted by last updated."""
        return await self.conversation_repo.list_by_user(user_id, page, limit)

    async def create_conversation(
        self, user_id: uuid.UUID, title: Optional[str] = None, system_prompt: Optional[str] = None
    ) -> ConversationTable:
        """Creates a new conversation canvas."""
        title_val = title or "New Conversation"
        system_prompt_val = system_prompt or "You are a helpful AI assistant."
        return await self.conversation_repo.create(user_id, title_val, system_prompt_val)

    async def delete_conversation(self, user_id: uuid.UUID, conversation_id: uuid.UUID) -> bool:
        """Deletes a conversation after verifying user ownership."""
        conversation = await self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise KeyError("Conversation not found")
        if conversation.user_id != user_id:
            raise PermissionError("User does not own this conversation")
        return await self.conversation_repo.delete(conversation_id)

    async def list_messages(
        self,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        limit: int,
        before_id: Optional[uuid.UUID] = None,
    ) -> List[MessageTable]:
        """Lists message logs for a conversation after verifying user ownership."""
        conversation = await self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise KeyError("Conversation not found")
        if conversation.user_id != user_id:
            raise PermissionError("User does not own this conversation")
        return await self.message_repo.list_by_conversation(conversation_id, limit, before_id)

    async def post_message_stream(
        self,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        content: str,
    ) -> AsyncGenerator[str, None]:
        """
        Processes a user message:
        1. Validates conversation ownership.
        2. Saves user message to database.
        3. Pre-creates assistant placeholder message.
        4. Queries memory enrichment context.
        5. Queries LLM service for stream.
        6. Yields SSE chunks.
        7. On completion, updates database with final assistant response.
        """
        # Validate conversation ownership
        conversation = await self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise KeyError("Conversation not found")
        if conversation.user_id != user_id:
            raise PermissionError("User does not own this conversation")

        # 1. Save user message to database
        user_message = await self.message_repo.create(
            conversation_id=conversation_id,
            sender_role="user",
            content=content,
            memory_status="pending",
        )
        logger.info(f"Saved user message {user_message.id} in conversation {conversation_id}")

        # 2. Pre-create assistant placeholder message
        assistant_message = await self.message_repo.create(
            conversation_id=conversation_id,
            sender_role="assistant",
            content="",  # empty initially
            memory_status="pending",
        )
        logger.info(f"Pre-created assistant message placeholder {assistant_message.id}")

        # Yield assistant message ID immediately
        yield f"event: message_id\ndata: {assistant_message.id}\n\n"

        # 3. Fetch past conversation context (last 15 messages) for sliding window
        history_records = await self.message_repo.list_by_conversation(
            conversation_id=conversation_id, limit=15
        )
        
        # Format history (excluding the current pending assistant message and user message)
        prompt_messages = []
        for msg in history_records:
            if msg.id != assistant_message.id and msg.id != user_message.id:
                prompt_messages.append({"role": msg.sender_role, "content": msg.content})

        # Append the new user message
        prompt_messages.append({"role": "user", "content": content})

        # 4. Enrich context via Memory Service (v0.2 hook)
        enriched_facts = await self.memory_service.enrich_context(user_id, content)
        system_prompt = conversation.system_prompt or "You are a helpful AI assistant."
        if enriched_facts:
            facts_str = "\n".join(enriched_facts)
            system_prompt += f"\n\nRelevant past memories/facts:\n{facts_str}"

        # 5. Initialize streaming from LLM Service
        accumulated_content = ""
        try:
            async for token in self.llm_service.generate_stream(system_prompt, prompt_messages):
                accumulated_content += token
                yield f"event: delta\ndata: {token}\n\n"
        except Exception as e:
            logger.error(f"Error during streaming completed: {e}")
            yield f"event: error\ndata: Stream generation failed\n\n"
            raise e

        # Yield done event
        yield "event: done\ndata: [DONE]\n\n"

        # 6. Save final assistant response to the database
        # To ensure it is safely committed, we update the database record.
        # Since we are inside an AsyncGenerator, we use a separate session or update via the current session.
        # Because we are using repositories, we update the message content.
        try:
            assistant_message.content = accumulated_content
            # Trigger updated_at modification for conversation sorting
            conversation.updated_at = datetime.now(timezone.utc)
            
            # Flush changes in the current session
            # Note: the get_db dependency takes care of committing this at request teardown, 
            # but we explicitly flush to ensure the memory state is written.
            await self.conversation_repo.session.commit()
            logger.info(f"Updated assistant message {assistant_message.id} with content (Length: {len(accumulated_content)})")
            
            # 7. Ingestion trigger (v0.2 hook)
            await self.memory_service.enqueue_ingest(user_message.id)
            await self.memory_service.enqueue_ingest(assistant_message.id)
        except Exception as db_err:
            logger.error(f"Failed to save assistant message stream contents: {db_err}")
            raise db_err
