import uuid
from typing import Optional
from sqlalchemy import select, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories import (
    IUserRepository,
    ISessionRepository,
    IConversationRepository,
    IMessageRepository,
)
from app.infrastructure.db.models import UserTable, AuthSessionTable, ConversationTable, MessageTable


class SQLUserRepository(IUserRepository):
    """SQLAlchemy implementation of the User repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[UserTable]:
        result = await self.session.execute(
            select(UserTable).where(UserTable.id == user_id)
        )
        return result.scalars().first()

    async def get_by_email(self, email: str) -> Optional[UserTable]:
        result = await self.session.execute(
            select(UserTable).where(UserTable.email == email)
        )
        return result.scalars().first()

    async def create(self, email: str, password_hash: str) -> UserTable:
        user = UserTable(email=email, password_hash=password_hash)
        self.session.add(user)
        # Flush to populate automatically generated fields (UUID, created_at)
        await self.session.flush()
        return user


class SQLSessionRepository(ISessionRepository):
    """SQLAlchemy implementation of the Session repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_token(self, token_hash: str) -> Optional[AuthSessionTable]:
        result = await self.session.execute(
            select(AuthSessionTable).where(AuthSessionTable.token_hash == token_hash)
        )
        return result.scalars().first()

    async def create(
        self,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: any,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuthSessionTable:
        auth_session = AuthSessionTable(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.session.add(auth_session)
        await self.session.flush()
        return auth_session

    async def delete_by_token(self, token_hash: str) -> bool:
        result = await self.session.execute(
            delete(AuthSessionTable).where(AuthSessionTable.token_hash == token_hash)
        )
        return result.rowcount > 0


class SQLConversationRepository(IConversationRepository):
    """SQLAlchemy implementation of the Conversation repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, conversation_id: uuid.UUID) -> Optional[ConversationTable]:
        result = await self.session.execute(
            select(ConversationTable).where(ConversationTable.id == conversation_id)
        )
        return result.scalars().first()

    async def list_by_user(self, user_id: uuid.UUID, page: int, limit: int) -> list[ConversationTable]:
        offset = (page - 1) * limit
        result = await self.session.execute(
            select(ConversationTable)
            .where(ConversationTable.user_id == user_id)
            .order_by(desc(ConversationTable.updated_at))
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def create(self, user_id: uuid.UUID, title: str, system_prompt: Optional[str] = None) -> ConversationTable:
        conversation = ConversationTable(
            user_id=user_id,
            title=title,
            system_prompt=system_prompt,
        )
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def delete(self, conversation_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            delete(ConversationTable).where(ConversationTable.id == conversation_id)
        )
        return result.rowcount > 0


class SQLMessageRepository(IMessageRepository):
    """SQLAlchemy implementation of the Message repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_by_conversation(
        self, conversation_id: uuid.UUID, limit: int, before_id: Optional[uuid.UUID] = None
    ) -> list[MessageTable]:
        query = (
            select(MessageTable)
            .where(MessageTable.conversation_id == conversation_id)
        )

        if before_id:
            # Query the target message to check creation timestamp
            message_result = await self.session.execute(
                select(MessageTable.created_at).where(MessageTable.id == before_id)
            )
            created_at_limit = message_result.scalar()
            if created_at_limit:
                query = query.where(MessageTable.created_at < created_at_limit)

        query = query.order_by(desc(MessageTable.created_at)).limit(limit)
        result = await self.session.execute(query)
        # Reverse the order so client gets chronological log order
        messages = list(result.scalars().all())
        messages.reverse()
        return messages

    async def create(
        self, conversation_id: uuid.UUID, sender_role: str, content: str, memory_status: str = "pending"
    ) -> MessageTable:
        message = MessageTable(
            conversation_id=conversation_id,
            sender_role=sender_role,
            content=content,
            memory_status=memory_status,
        )
        self.session.add(message)
        await self.session.flush()
        return message
