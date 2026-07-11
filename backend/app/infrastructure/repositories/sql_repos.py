import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import select, delete, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories import (
    IUserRepository,
    ISessionRepository,
    IConversationRepository,
    IMessageRepository,
    IMemoryRepository,
)
from app.infrastructure.db.models import (
    UserTable,
    AuthSessionTable,
    ConversationTable,
    MessageTable,
    MemoryTable,
)
from app.domain.entities import Memory, MemoryType, MemoryStatus, normalize_memory_content



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
        from datetime import datetime, timezone
        message = MessageTable(
            conversation_id=conversation_id,
            sender_role=sender_role,
            content=content,
            memory_status=memory_status,
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(message)
        await self.session.flush()
        return message


def _to_domain(table: MemoryTable) -> Memory:
    """Helper mapper translating SQLAlchemy MemoryTable model to pure domain Memory entity."""
    return Memory(
        id=table.id,
        user_id=table.user_id,
        conversation_id=table.conversation_id,
        content=table.content,
        memory_type=MemoryType(table.memory_type),
        importance=table.importance,
        confidence=table.confidence,
        status=MemoryStatus(table.status),
        created_at=table.created_at,
        updated_at=table.updated_at,
        last_accessed_at=table.last_accessed_at,
        version=table.version,
        metadata=table.metadata_dict or {},
    )


class SQLMemoryRepository(IMemoryRepository):
    """SQLAlchemy concrete implementation of the IMemoryRepository contract."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, memory_id: uuid.UUID) -> Optional[Memory]:
        result = await self.session.execute(
            select(MemoryTable).where(MemoryTable.id == memory_id)
        )
        table = result.scalars().first()
        return _to_domain(table) if table else None

    async def create(
        self,
        user_id: uuid.UUID,
        conversation_id: Optional[uuid.UUID],
        content: str,
        memory_type: MemoryType,
        importance: float,
        confidence: float,
        status: MemoryStatus,
        last_accessed_at: datetime,
        version: int,
        metadata: dict,
    ) -> Memory:
        table = MemoryTable(
            user_id=user_id,
            conversation_id=conversation_id,
            content=content,
            memory_type=memory_type.value,
            importance=importance,
            confidence=confidence,
            status=status.value,
            last_accessed_at=last_accessed_at,
            version=version,
            metadata_dict=metadata or {},
        )
        self.session.add(table)
        await self.session.flush()
        await self.session.refresh(table)
        return _to_domain(table)


    async def update(
        self,
        memory_id: uuid.UUID,
        content: Optional[str] = None,
        memory_type: Optional[MemoryType] = None,
        importance: Optional[float] = None,
        confidence: Optional[float] = None,
        status: Optional[MemoryStatus] = None,
        last_accessed_at: Optional[datetime] = None,
        version: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> Memory:
        result = await self.session.execute(
            select(MemoryTable).where(MemoryTable.id == memory_id)
        )
        table = result.scalars().first()
        if not table:
            raise KeyError("Memory not found")

        if content is not None:
            table.content = content
        if memory_type is not None:
            table.memory_type = memory_type.value
        if importance is not None:
            table.importance = importance
        if confidence is not None:
            table.confidence = confidence
        if status is not None:
            table.status = status.value
        if last_accessed_at is not None:
            table.last_accessed_at = last_accessed_at
        if version is not None:
            table.version = version
        if metadata is not None:
            table.metadata_dict = metadata

        await self.session.flush()
        await self.session.refresh(table)
        return _to_domain(table)


    async def list_by_user(
        self,
        user_id: uuid.UUID,
        memory_type: Optional[MemoryType] = None,
        status: Optional[MemoryStatus] = None,
        page: int = 1,
        limit: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> List[Memory]:
        query = select(MemoryTable).where(MemoryTable.user_id == user_id)
        if memory_type:
            query = query.where(MemoryTable.memory_type == memory_type.value)
        if status:
            query = query.where(MemoryTable.status == status.value)

        # Build dynamic sorting order
        sort_col = getattr(MemoryTable, sort_by, MemoryTable.created_at)
        if sort_order == "desc":
            query = query.order_by(desc(sort_col))
        else:
            query = query.order_by(asc(sort_col))

        # Build pagination boundaries
        offset = (page - 1) * limit
        query = query.limit(limit).offset(offset)

        result = await self.session.execute(query)
        return [_to_domain(m) for m in result.scalars().all()]

    async def list_by_conversation(
        self,
        conversation_id: uuid.UUID,
        memory_type: Optional[MemoryType] = None,
        status: Optional[MemoryStatus] = None,
        page: int = 1,
        limit: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> List[Memory]:
        query = select(MemoryTable).where(MemoryTable.conversation_id == conversation_id)
        if memory_type:
            query = query.where(MemoryTable.memory_type == memory_type.value)
        if status:
            query = query.where(MemoryTable.status == status.value)

        # Build dynamic sorting order
        sort_col = getattr(MemoryTable, sort_by, MemoryTable.created_at)
        if sort_order == "desc":
            query = query.order_by(desc(sort_col))
        else:
            query = query.order_by(asc(sort_col))

        # Build pagination boundaries
        offset = (page - 1) * limit
        query = query.limit(limit).offset(offset)

        result = await self.session.execute(query)
        return [_to_domain(m) for m in result.scalars().all()]

    async def get_active_by_conversation_and_content(
        self, conversation_id: uuid.UUID, content: str
    ) -> Optional[Memory]:
        result = await self.session.execute(
            select(MemoryTable).where(
                MemoryTable.conversation_id == conversation_id,
                MemoryTable.status == MemoryStatus.ACTIVE.value
            )
        )
        active_records = result.scalars().all()
        normalized_target = normalize_memory_content(content)

        for record in active_records:
            if normalize_memory_content(record.content) == normalized_target:
                return _to_domain(record)
        return None

