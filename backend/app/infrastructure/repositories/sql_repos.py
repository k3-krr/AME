import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import select, delete, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories import (
    IUserRepository,
    ISessionRepository,
    IConversationRepository,
    IMessageRepository,
    IMemoryRepository,
    ISemanticMemoryRepository,
    IEpisodicMemoryRepository,
    IProceduralMemoryRepository,
    IWorkingMemoryRepository,
    IRepositoryFactory,
    IMemoryEmbeddingRepository,
    IMemoryStateRepository,
    IMemoryAccessLogRepository,
    IMemoryExtractionRepository,
    IAgentRepository,
    IAgentCredentialRepository,
    IMemoryAccessGrantRepository,
)
from app.infrastructure.db.models import (
    UserTable,
    AuthSessionTable,
    ConversationTable,
    MessageTable,
    MemoryTable,
    MemoryEmbeddingTable,
    MemoryStateTable,
    MemoryAccessLogTable,
    MemoryExtractionTable,
    MemoryExtractionCandidateTable,
    AgentTable,
    AgentCredentialTable,
    MemoryAccessGrantTable,
)
from app.domain.embedding import MemoryEmbedding
from app.domain.entities import (
    Memory,
    MemoryType,
    MemoryStatus,
    normalize_memory_content,
    MemoryState,
    MemorySourceType,
    MemoryExtraction,
    MemoryExtractionCandidate,
    ExtractionStatus,
    ExtractionAction,
    Agent,
    AgentStatus,
    AgentCredential,
    PrincipalType,
    AccessContext,
    MemoryAccessLevel,
    MemoryAccessGrant,
    MemoryAuthorizationFilterSpec,
)
from app.domain.memory_system import MemorySystem


def apply_memory_auth_filter(query, spec: MemoryAuthorizationFilterSpec):
    """
    Compiles the MemoryAuthorizationFilterSpec domain rules into database-level SQL clauses.
    Ensures optimal execution plans on both pgvector and SQLite.
    """
    if not spec.is_agent:
        return query.where(MemoryTable.user_id == spec.tenant_id)
    else:
        from sqlalchemy.sql import exists
        from app.infrastructure.db.models import MemoryAccessGrantTable, AgentTable
        
        # Enforce recipient (requesting agent) is active
        recipient_active = exists().where(
            AgentTable.id == spec.agent_id,
            AgentTable.status == "ACTIVE"
        )
        
        grant_exists = exists().where(
            MemoryAccessGrantTable.memory_id == MemoryTable.id,
            MemoryAccessGrantTable.agent_id == spec.agent_id,
            MemoryAccessGrantTable.revoked_at.is_(None),
            (MemoryAccessGrantTable.expires_at.is_(None) | (MemoryAccessGrantTable.expires_at > spec.current_time)),
            MemoryAccessGrantTable.access_level.in_(["READ", "WRITE", "MANAGE"])
        )
        return query.where(
            MemoryTable.user_id == spec.tenant_id,
            MemoryTable.status != MemoryStatus.DELETED.value,
            recipient_active,
            (
                (MemoryTable.agent_id == spec.agent_id) |
                grant_exists
            )
        )



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
        memory_system=MemorySystem(table.memory_system),
        occurred_at=table.occurred_at,
        expires_at=table.expires_at,
        agent_id=table.agent_id,
    )


class SQLMemoryRepository(IMemoryRepository):
    """SQLAlchemy concrete implementation of the IMemoryRepository contract."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, memory_id: uuid.UUID, access_context: Optional[AccessContext] = None) -> Optional[Memory]:
        query = select(MemoryTable).where(MemoryTable.id == memory_id)
        if access_context:
            spec = MemoryAuthorizationFilterSpec(access_context, datetime.now(timezone.utc))
            query = apply_memory_auth_filter(query, spec)
        result = await self.session.execute(query)
        table = result.scalars().first()
        return _to_domain(table) if table else None

    async def get_by_ids(self, memory_ids: List[uuid.UUID], access_context: Optional[AccessContext] = None) -> List[Memory]:
        if not memory_ids:
            return []
        query = select(MemoryTable).where(MemoryTable.id.in_(memory_ids))
        if access_context:
            spec = MemoryAuthorizationFilterSpec(access_context, datetime.now(timezone.utc))
            query = apply_memory_auth_filter(query, spec)
        result = await self.session.execute(query)
        # Preserve input order
        table_map = {t.id: t for t in result.scalars().all()}
        ordered_memories = []
        for mid in memory_ids:
            if mid in table_map:
                ordered_memories.append(_to_domain(table_map[mid]))
        return ordered_memories


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
        memory_system: MemorySystem = MemorySystem.SEMANTIC,
        occurred_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        agent_id: Optional[uuid.UUID] = None,
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
            memory_system=memory_system.value,
            occurred_at=occurred_at,
            expires_at=expires_at,
            agent_id=agent_id,
        )
        self.session.add(table)
        await self.session.flush()

        # Initialize the memory state record transactionally
        state_table = MemoryStateTable(
            memory_id=table.id,
            access_count=0,
            retrieval_count=0,
            reinforcement_count=0,
            last_accessed_at=last_accessed_at,
            last_reinforced_at=None,
            decay_score=0.0,
            confidence_score=confidence,
            importance_score=importance,
            source_type="user",
        )
        self.session.add(state_table)
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
        memory_system: Optional[MemorySystem] = None,
        occurred_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
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
        if memory_system is not None:
            table.memory_system = memory_system.value
            if memory_system != MemorySystem.WORKING:
                table.expires_at = None
        if occurred_at is not None:
            table.occurred_at = occurred_at
        if expires_at is not None:
            table.expires_at = expires_at

        await self.session.flush()
        await self.session.refresh(table)
        return _to_domain(table)


    async def list_by_user(
        self,
        user_id: uuid.UUID,
        memory_type: Optional[MemoryType] = None,
        status: Optional[MemoryStatus] = None,
        memory_system: Optional[MemorySystem] = None,
        page: int = 1,
        limit: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        access_context: Optional[AccessContext] = None,
    ) -> List[Memory]:
        query = select(MemoryTable)
        if access_context:
            spec = MemoryAuthorizationFilterSpec(access_context, datetime.now(timezone.utc))
            query = apply_memory_auth_filter(query, spec)
        else:
            query = query.where(MemoryTable.user_id == user_id)

        if memory_type:
            query = query.where(MemoryTable.memory_type == memory_type.value)
        if status:
            query = query.where(MemoryTable.status == status.value)
        if memory_system:
            query = query.where(MemoryTable.memory_system == memory_system.value)

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
        memory_system: Optional[MemorySystem] = None,
        page: int = 1,
        limit: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        access_context: Optional[AccessContext] = None,
    ) -> List[Memory]:
        query = select(MemoryTable).where(MemoryTable.conversation_id == conversation_id)
        if access_context:
            spec = MemoryAuthorizationFilterSpec(access_context, datetime.now(timezone.utc))
            query = apply_memory_auth_filter(query, spec)

        if memory_type:
            query = query.where(MemoryTable.memory_type == memory_type.value)
        if status:
            query = query.where(MemoryTable.status == status.value)
        if memory_system:
            query = query.where(MemoryTable.memory_system == memory_system.value)

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


class SQLSemanticMemoryRepository(SQLMemoryRepository, ISemanticMemoryRepository):
    """SQLAlchemy concrete implementation for Semantic memory system."""

    async def list_semantic_memories(self, user_id: uuid.UUID, page: int = 1, limit: int = 20, access_context: Optional[AccessContext] = None) -> List[Memory]:
        return await self.list_by_user(
            user_id=user_id,
            memory_system=MemorySystem.SEMANTIC,
            page=page,
            limit=limit,
            access_context=access_context,
        )

    async def get_semantic_memories_by_type(self, user_id: uuid.UUID, memory_types: List[MemoryType], access_context: Optional[AccessContext] = None) -> List[Memory]:
        query = select(MemoryTable).where(
            MemoryTable.memory_system == MemorySystem.SEMANTIC.value,
            MemoryTable.memory_type.in_([t.value for t in memory_types]),
        )
        if access_context:
            spec = MemoryAuthorizationFilterSpec(access_context, datetime.now(timezone.utc))
            query = apply_memory_auth_filter(query, spec)
        else:
            query = query.where(MemoryTable.user_id == user_id)
        result = await self.session.execute(query)
        return [_to_domain(r) for r in result.scalars().all()]

    async def retrieve_semantic(
        self,
        user_id: uuid.UUID,
        query_embedding: Optional[list[float]] = None,
        limit: int = 20,
        access_context: Optional[AccessContext] = None,
    ) -> List[Memory]:
        if query_embedding:
            if self.session.sync_session.get_bind().dialect.name == "sqlite":
                query = (
                    select(MemoryEmbeddingTable)
                    .join(MemoryTable, MemoryTable.id == MemoryEmbeddingTable.memory_id)
                    .where(
                        MemoryTable.memory_system == MemorySystem.SEMANTIC.value,
                        MemoryTable.status == MemoryStatus.ACTIVE.value
                    )
                )
                if access_context:
                    spec = MemoryAuthorizationFilterSpec(access_context, datetime.now(timezone.utc))
                    query = apply_memory_auth_filter(query, spec)
                else:
                    query = query.where(MemoryTable.user_id == user_id)
                result = await self.session.execute(query)
                tables = result.scalars().all()
                matches = []
                for t in tables:
                    similarity = cosine_similarity(query_embedding, t.embedding)
                    matches.append((t.memory_id, similarity))
                matches.sort(key=lambda x: x[1], reverse=True)
                top_ids = [m[0] for m in matches[:limit]]
                if not top_ids:
                    return []
                return await self.get_by_ids(top_ids, access_context=access_context)
            else:
                distance_expr = MemoryEmbeddingTable.embedding.cosine_distance(query_embedding)
                query = (
                    select(MemoryTable)
                    .join(MemoryEmbeddingTable, MemoryTable.id == MemoryEmbeddingTable.memory_id)
                    .where(
                        MemoryTable.memory_system == MemorySystem.SEMANTIC.value,
                        MemoryTable.status == MemoryStatus.ACTIVE.value
                    )
                )
                if access_context:
                    spec = MemoryAuthorizationFilterSpec(access_context, datetime.now(timezone.utc))
                    query = apply_memory_auth_filter(query, spec)
                else:
                    query = query.where(MemoryTable.user_id == user_id)
                query = query.order_by(distance_expr).limit(limit)
                result = await self.session.execute(query)
                return [_to_domain(r) for r in result.scalars().all()]
        else:
            return await self.list_semantic_memories(user_id=user_id, limit=limit, access_context=access_context)


class SQLEpisodicMemoryRepository(SQLMemoryRepository, IEpisodicMemoryRepository):
    """SQLAlchemy concrete implementation for Episodic memory system."""

    async def get_timeline(
        self,
        user_id: uuid.UUID,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        limit: int = 20,
        access_context: Optional[AccessContext] = None,
    ) -> List[Memory]:
        query = select(MemoryTable).where(
            MemoryTable.memory_system == MemorySystem.EPISODIC.value,
        )
        if access_context:
            spec = MemoryAuthorizationFilterSpec(access_context, datetime.now(timezone.utc))
            query = apply_memory_auth_filter(query, spec)
        else:
            query = query.where(MemoryTable.user_id == user_id)

        if start_time:
            query = query.where(MemoryTable.occurred_at >= start_time)
        if end_time:
            query = query.where(MemoryTable.occurred_at <= end_time)

        # Chronological ordering for timeline queries
        query = query.order_by(asc(MemoryTable.occurred_at))

        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)

        result = await self.session.execute(query)
        return [_to_domain(r) for r in result.scalars().all()]

    async def list_by_conversation_episodic(
        self,
        conversation_id: uuid.UUID,
        page: int = 1,
        limit: int = 20,
        access_context: Optional[AccessContext] = None,
    ) -> List[Memory]:
        return await self.list_by_conversation(
            conversation_id=conversation_id,
            memory_system=MemorySystem.EPISODIC,
            page=page,
            limit=limit,
            sort_by="occurred_at",
            sort_order="asc",
            access_context=access_context,
        )

    async def retrieve_episodic(
        self,
        user_id: uuid.UUID,
        conversation_id: Optional[uuid.UUID] = None,
        limit: int = 20,
        access_context: Optional[AccessContext] = None,
    ) -> List[Memory]:
        if conversation_id:
            return await self.list_by_conversation_episodic(conversation_id=conversation_id, limit=limit, access_context=access_context)
        return await self.get_timeline(user_id=user_id, limit=limit, access_context=access_context)


class SQLProceduralMemoryRepository(SQLMemoryRepository, IProceduralMemoryRepository):
    """SQLAlchemy concrete implementation for Procedural memory system."""

    async def get_procedural_memories(self, user_id: uuid.UUID, page: int = 1, limit: int = 20, access_context: Optional[AccessContext] = None) -> List[Memory]:
        return await self.list_by_user(
            user_id=user_id,
            memory_system=MemorySystem.PROCEDURAL,
            page=page,
            limit=limit,
            access_context=access_context,
        )

    async def get_frequent_procedures(
        self,
        user_id: uuid.UUID,
        limit: int = 10,
        access_context: Optional[AccessContext] = None,
    ) -> List[Memory]:
        query = (
            select(MemoryTable)
            .join(MemoryStateTable, MemoryTable.id == MemoryStateTable.memory_id)
            .where(
                MemoryTable.memory_system == MemorySystem.PROCEDURAL.value,
            )
        )
        if access_context:
            spec = MemoryAuthorizationFilterSpec(access_context, datetime.now(timezone.utc))
            query = apply_memory_auth_filter(query, spec)
        else:
            query = query.where(MemoryTable.user_id == user_id)

        query = query.order_by(desc(MemoryStateTable.access_count)).limit(limit)
        result = await self.session.execute(query)
        return [_to_domain(r) for r in result.scalars().all()]

    async def retrieve_procedural(
        self,
        user_id: uuid.UUID,
        limit: int = 20,
        access_context: Optional[AccessContext] = None,
    ) -> List[Memory]:
        return await self.get_frequent_procedures(user_id=user_id, limit=limit, access_context=access_context)


class SQLWorkingMemoryRepository(SQLMemoryRepository, IWorkingMemoryRepository):
    """SQLAlchemy concrete implementation for Working memory system."""

    async def get_active_working_memories(self, user_id: uuid.UUID, access_context: Optional[AccessContext] = None) -> List[Memory]:
        now = datetime.now(timezone.utc)
        query = select(MemoryTable).where(
            MemoryTable.memory_system == MemorySystem.WORKING.value,
            MemoryTable.status == MemoryStatus.ACTIVE.value,
            (MemoryTable.expires_at == None) | (MemoryTable.expires_at > now),
        )
        if access_context:
            spec = MemoryAuthorizationFilterSpec(access_context, datetime.now(timezone.utc))
            query = apply_memory_auth_filter(query, spec)
        else:
            query = query.where(MemoryTable.user_id == user_id)
        result = await self.session.execute(query)
        return [_to_domain(r) for r in result.scalars().all()]

    async def list_active_session_context(self, conversation_id: uuid.UUID, access_context: Optional[AccessContext] = None) -> List[Memory]:
        now = datetime.now(timezone.utc)
        query = select(MemoryTable).where(
            MemoryTable.conversation_id == conversation_id,
            MemoryTable.memory_system == MemorySystem.WORKING.value,
            MemoryTable.status == MemoryStatus.ACTIVE.value,
            (MemoryTable.expires_at == None) | (MemoryTable.expires_at > now),
        )
        if access_context:
            spec = MemoryAuthorizationFilterSpec(access_context, datetime.now(timezone.utc))
            query = apply_memory_auth_filter(query, spec)
        result = await self.session.execute(query)
        return [_to_domain(r) for r in result.scalars().all()]

    async def retrieve_working(
        self,
        user_id: uuid.UUID,
        conversation_id: Optional[uuid.UUID] = None,
        access_context: Optional[AccessContext] = None,
    ) -> List[Memory]:
        if conversation_id:
            return await self.list_active_session_context(conversation_id=conversation_id, access_context=access_context)
        return await self.get_active_working_memories(user_id=user_id, access_context=access_context)


class SQLRepositoryFactory(IRepositoryFactory):
    """SQLAlchemy concrete implementation of IRepositoryFactory."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._repos = {
            MemorySystem.SEMANTIC: SQLSemanticMemoryRepository(session),
            MemorySystem.EPISODIC: SQLEpisodicMemoryRepository(session),
            MemorySystem.PROCEDURAL: SQLProceduralMemoryRepository(session),
            MemorySystem.WORKING: SQLWorkingMemoryRepository(session),
        }

    def get(self, memory_system: MemorySystem) -> IMemoryRepository:
        return self._repos[memory_system]


def _to_domain_embedding(table: MemoryEmbeddingTable) -> MemoryEmbedding:
    """Helper mapper translating SQLAlchemy MemoryEmbeddingTable model to pure domain MemoryEmbedding entity."""
    return MemoryEmbedding(
        id=table.id,
        memory_id=table.memory_id,
        embedding=table.embedding,
        provider=table.provider,
        model=table.model,
        dimension=table.dimension,
        created_at=table.created_at,
        updated_at=table.updated_at,
    )


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Computes cosine similarity between two float vectors."""
    dot = sum(x * y for x, y in zip(v1, v2))
    mag1 = sum(x * x for x in v1) ** 0.5
    mag2 = sum(x * x for x in v2) ** 0.5
    if mag1 == 0.0 or mag2 == 0.0:
        return 0.0
    return dot / (mag1 * mag2)


class SQLMemoryEmbeddingRepository(IMemoryEmbeddingRepository):
    """SQLAlchemy concrete implementation of the IMemoryEmbeddingRepository contract."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, embedding: MemoryEmbedding) -> None:
        result = await self.session.execute(
            select(MemoryEmbeddingTable).where(MemoryEmbeddingTable.memory_id == embedding.memory_id)
        )
        table = result.scalars().first()
        
        if table:
            table.embedding = embedding.embedding
            table.provider = embedding.provider
            table.model = embedding.model
            table.dimension = embedding.dimension
            table.updated_at = embedding.updated_at
        else:
            table = MemoryEmbeddingTable(
                id=embedding.id,
                memory_id=embedding.memory_id,
                embedding=embedding.embedding,
                provider=embedding.provider,
                model=embedding.model,
                dimension=embedding.dimension,
                created_at=embedding.created_at,
                updated_at=embedding.updated_at,
            )
            self.session.add(table)
        await self.session.flush()

    async def get_by_memory_id(self, memory_id: uuid.UUID) -> Optional[MemoryEmbedding]:
        result = await self.session.execute(
            select(MemoryEmbeddingTable).where(MemoryEmbeddingTable.memory_id == memory_id)
        )
        table = result.scalars().first()
        return _to_domain_embedding(table) if table else None

    async def delete_by_memory_id(self, memory_id: uuid.UUID) -> None:
        await self.session.execute(
            delete(MemoryEmbeddingTable).where(MemoryEmbeddingTable.memory_id == memory_id)
        )
        await self.session.flush()

    async def similarity_search(
        self,
        user_id: uuid.UUID,
        query_embedding: list[float],
        top_k: int = 5,
        memory_type: Optional[MemoryType] = None,
    ) -> list[tuple[uuid.UUID, float]]:
        if self.session.sync_session.get_bind().dialect.name == "sqlite":
            query = (
                select(MemoryEmbeddingTable)
                .join(MemoryTable, MemoryTable.id == MemoryEmbeddingTable.memory_id)
                .where(
                    MemoryTable.user_id == user_id,
                    MemoryTable.status == MemoryStatus.ACTIVE.value
                )
            )
            if memory_type:
                query = query.where(MemoryTable.memory_type == memory_type.value)
            
            result = await self.session.execute(query)
            tables = result.scalars().all()
            
            matches = []
            for t in tables:
                similarity = cosine_similarity(query_embedding, t.embedding)
                matches.append((t.memory_id, similarity))
            
            matches.sort(key=lambda x: x[1], reverse=True)
            return matches[:top_k]
        else:
            distance_expr = MemoryEmbeddingTable.embedding.cosine_distance(query_embedding)
            similarity_expr = (1.0 - distance_expr).label("similarity")
            
            query = (
                select(MemoryEmbeddingTable.memory_id, similarity_expr)
                .join(MemoryTable, MemoryTable.id == MemoryEmbeddingTable.memory_id)
                .where(
                    MemoryTable.user_id == user_id,
                    MemoryTable.status == MemoryStatus.ACTIVE.value
                )
            )
            if memory_type:
                query = query.where(MemoryTable.memory_type == memory_type.value)
            
            query = query.order_by(distance_expr).limit(top_k)
            result = await self.session.execute(query)
            rows = result.all()
            return [(row[0], float(row[1])) for row in rows]

    async def list_memories_missing_embeddings(
        self, user_id: Optional[uuid.UUID] = None, limit: int = 100
    ) -> list[uuid.UUID]:
        query = (
            select(MemoryTable.id)
            .outerjoin(MemoryEmbeddingTable, MemoryTable.id == MemoryEmbeddingTable.memory_id)
            .where(
                MemoryTable.status == MemoryStatus.ACTIVE.value,
                MemoryEmbeddingTable.id.is_(None)
            )
        )
        if user_id:
            query = query.where(MemoryTable.user_id == user_id)
            
        query = query.limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())


def _to_domain_state(table: MemoryStateTable) -> MemoryState:
    """Helper mapper translating SQLAlchemy MemoryStateTable model to pure domain MemoryState entity."""
    return MemoryState(
        memory_id=table.memory_id,
        access_count=table.access_count,
        retrieval_count=table.retrieval_count,
        reinforcement_count=table.reinforcement_count,
        last_accessed_at=table.last_accessed_at,
        last_reinforced_at=table.last_reinforced_at,
        decay_score=table.decay_score,
        confidence_score=table.confidence_score,
        importance_score=table.importance_score,
        source_type=MemorySourceType(table.source_type),
    )


class SQLMemoryStateRepository(IMemoryStateRepository):
    """SQLAlchemy concrete implementation of the IMemoryStateRepository contract."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_memory_id(self, memory_id: uuid.UUID) -> Optional[MemoryState]:
        result = await self.session.execute(
            select(MemoryStateTable).where(MemoryStateTable.memory_id == memory_id)
        )
        table = result.scalars().first()
        return _to_domain_state(table) if table else None

    async def get_by_memory_ids(self, memory_ids: list[uuid.UUID]) -> list[MemoryState]:
        if not memory_ids:
            return []
        result = await self.session.execute(
            select(MemoryStateTable).where(MemoryStateTable.memory_id.in_(memory_ids))
        )
        tables = result.scalars().all()
        return [_to_domain_state(t) for t in tables]

    async def create(
        self,
        memory_id: uuid.UUID,
        access_count: int,
        retrieval_count: int,
        reinforcement_count: int,
        last_accessed_at: datetime,
        last_reinforced_at: Optional[datetime],
        decay_score: float,
        confidence_score: float,
        importance_score: float,
        source_type: MemorySourceType,
    ) -> MemoryState:
        table = MemoryStateTable(
            memory_id=memory_id,
            access_count=access_count,
            retrieval_count=retrieval_count,
            reinforcement_count=reinforcement_count,
            last_accessed_at=last_accessed_at,
            last_reinforced_at=last_reinforced_at,
            decay_score=decay_score,
            confidence_score=confidence_score,
            importance_score=importance_score,
            source_type=source_type.value,
        )
        self.session.add(table)
        await self.session.flush()
        await self.session.refresh(table)
        return _to_domain_state(table)

    async def update(
        self,
        memory_id: uuid.UUID,
        access_count: Optional[int] = None,
        retrieval_count: Optional[int] = None,
        reinforcement_count: Optional[int] = None,
        last_accessed_at: Optional[datetime] = None,
        last_reinforced_at: Optional[datetime] = None,
        decay_score: Optional[float] = None,
        confidence_score: Optional[float] = None,
        importance_score: Optional[float] = None,
        source_type: Optional[MemorySourceType] = None,
    ) -> MemoryState:
        result = await self.session.execute(
            select(MemoryStateTable).where(MemoryStateTable.memory_id == memory_id)
        )
        table = result.scalars().first()
        if not table:
            raise KeyError("MemoryState not found")

        if access_count is not None:
            table.access_count = access_count
        if retrieval_count is not None:
            table.retrieval_count = retrieval_count
        if reinforcement_count is not None:
            table.reinforcement_count = reinforcement_count
        if last_accessed_at is not None:
            table.last_accessed_at = last_accessed_at
        if last_reinforced_at is not None:
            table.last_reinforced_at = last_reinforced_at
        if decay_score is not None:
            table.decay_score = decay_score
        if confidence_score is not None:
            table.confidence_score = confidence_score
        if importance_score is not None:
            table.importance_score = importance_score
        if source_type is not None:
            table.source_type = source_type.value

        await self.session.flush()
        await self.session.refresh(table)
        return _to_domain_state(table)

    async def increment_access_counters(
        self, memory_ids: list[uuid.UUID], is_retrieval: bool = True
    ) -> None:
        if not memory_ids:
            return
        from datetime import timezone
        now = datetime.now(timezone.utc)
        for memory_id in memory_ids:
            result = await self.session.execute(
                select(MemoryStateTable).where(MemoryStateTable.memory_id == memory_id)
            )
            table = result.scalars().first()
            if table:
                table.access_count += 1
                if is_retrieval:
                    table.retrieval_count += 1
                table.last_accessed_at = now
        await self.session.flush()

    async def apply_reinforcement(
        self, memory_ids: list[uuid.UUID], reinforcement_step: float = 0.02
    ) -> None:
        if not memory_ids:
            return
        from datetime import timezone
        now = datetime.now(timezone.utc)
        for memory_id in memory_ids:
            result = await self.session.execute(
                select(MemoryStateTable).where(MemoryStateTable.memory_id == memory_id)
            )
            table = result.scalars().first()
            if table:
                table.reinforcement_count += 1
                table.last_reinforced_at = now
                table.decay_score = 0.0
                table.importance_score = min(1.0, table.importance_score + reinforcement_step)
        await self.session.flush()

    async def update_decay_scores(self, decay_rate: float) -> int:
        from datetime import timezone
        import math
        now = datetime.now(timezone.utc)
        
        result = await self.session.execute(select(MemoryStateTable))
        tables = result.scalars().all()
        updated_count = 0
        for table in tables:
            last_activity = table.last_reinforced_at or table.last_accessed_at
            
            # handle timezone naive / aware datetimes carefully for SQLite/Postgres compatibility
            if last_activity.tzinfo is not None:
                last_naive = last_activity.astimezone(timezone.utc).replace(tzinfo=None)
                now_naive = now.replace(tzinfo=None)
            else:
                last_naive = last_activity
                now_naive = now.replace(tzinfo=None)

            idle_hours = max(0.0, (now_naive - last_naive).total_seconds() / 3600.0)
            new_decay = 1.0 - math.exp(-decay_rate * idle_hours)
            table.decay_score = max(0.0, min(1.0, new_decay))
            updated_count += 1
        await self.session.flush()
        return updated_count


class SQLMemoryAccessLogRepository(IMemoryAccessLogRepository):
    """SQLAlchemy concrete implementation of the IMemoryAccessLogRepository contract."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_access(
        self,
        memory_id: uuid.UUID,
        similarity_score: float,
        ranking_score: float,
        conversation_id: Optional[uuid.UUID] = None,
        retrieval_success: bool = True
    ) -> None:
        from datetime import timezone
        table = MemoryAccessLogTable(
            id=uuid.uuid4(),
            memory_id=memory_id,
            conversation_id=conversation_id,
            timestamp=datetime.now(timezone.utc),
            similarity_score=similarity_score,
            ranking_score=ranking_score,
            retrieval_success=retrieval_success,
        )
        self.session.add(table)
        await self.session.flush()

    async def list_logs_by_memory(self, memory_id: uuid.UUID, limit: int = 100) -> list[any]:
        result = await self.session.execute(
            select(MemoryAccessLogTable)
            .where(MemoryAccessLogTable.memory_id == memory_id)
            .order_by(desc(MemoryAccessLogTable.timestamp))
            .limit(limit)
        )
        return list(result.scalars().all())


def _to_domain_extraction(table: MemoryExtractionTable) -> MemoryExtraction:
    """Helper mapper translating SQLAlchemy MemoryExtractionTable model to pure domain MemoryExtraction entity."""
    return MemoryExtraction(
        id=table.id,
        conversation_id=table.conversation_id,
        message_id=table.message_id,
        extracted_at=table.extracted_at,
        status=ExtractionStatus(table.status),
        error_message=table.error_message,
    )


def _to_domain_candidate(table: MemoryExtractionCandidateTable) -> MemoryExtractionCandidate:
    """Helper mapper translating SQLAlchemy MemoryExtractionCandidateTable model to pure domain MemoryExtractionCandidate entity."""
    return MemoryExtractionCandidate(
        id=table.id,
        extraction_id=table.extraction_id,
        content=table.content,
        memory_type=MemoryType(table.memory_type),
        importance_score=table.importance_score,
        confidence_score=table.confidence_score,
        action_taken=ExtractionAction(table.action_taken),
        target_memory_id=table.target_memory_id,
    )


class SQLMemoryExtractionRepository(IMemoryExtractionRepository):
    """SQLAlchemy concrete implementation of the IMemoryExtractionRepository contract."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_extraction(
        self,
        conversation_id: uuid.UUID,
        message_id: Optional[uuid.UUID],
        status: ExtractionStatus,
        error_message: Optional[str] = None
    ) -> MemoryExtraction:
        table = MemoryExtractionTable(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            message_id=message_id,
            status=status.value,
            error_message=error_message,
        )
        self.session.add(table)
        await self.session.flush()
        await self.session.refresh(table)
        return _to_domain_extraction(table)

    async def add_candidate(
        self,
        extraction_id: uuid.UUID,
        content: str,
        memory_type: MemoryType,
        importance_score: float,
        confidence_score: float,
        action_taken: ExtractionAction,
        target_memory_id: Optional[uuid.UUID] = None
    ) -> MemoryExtractionCandidate:
        table = MemoryExtractionCandidateTable(
            id=uuid.uuid4(),
            extraction_id=extraction_id,
            content=content,
            memory_type=memory_type.value,
            importance_score=importance_score,
            confidence_score=confidence_score,
            action_taken=action_taken.value,
            target_memory_id=target_memory_id,
        )
        self.session.add(table)
        await self.session.flush()
        await self.session.refresh(table)
        return _to_domain_candidate(table)

    async def get_extraction_with_candidates(
        self, extraction_id: uuid.UUID
    ) -> Optional[tuple[MemoryExtraction, list[MemoryExtractionCandidate]]]:
        result = await self.session.execute(
            select(MemoryExtractionTable).where(MemoryExtractionTable.id == extraction_id)
        )
        extraction_table = result.scalars().first()
        if not extraction_table:
            return None

        candidates_result = await self.session.execute(
            select(MemoryExtractionCandidateTable)
            .where(MemoryExtractionCandidateTable.extraction_id == extraction_id)
        )
        candidate_tables = candidates_result.scalars().all()
        
        candidates = [_to_domain_candidate(t) for t in candidate_tables]
        return _to_domain_extraction(extraction_table), candidates

    async def list_extractions_by_conversation(
        self, conversation_id: uuid.UUID, page: int = 1, limit: int = 20
    ) -> list[MemoryExtraction]:
        offset = (page - 1) * limit
        result = await self.session.execute(
            select(MemoryExtractionTable)
            .where(MemoryExtractionTable.conversation_id == conversation_id)
            .order_by(desc(MemoryExtractionTable.extracted_at))
            .limit(limit)
            .offset(offset)
        )
        return [_to_domain_extraction(t) for t in result.scalars().all()]


def _to_domain_agent(table: AgentTable) -> Agent:
    """Helper mapper translating SQLAlchemy AgentTable model to pure domain Agent entity."""
    return Agent(
        id=table.id,
        tenant_id=table.tenant_id,
        name=table.name,
        description=table.description,
        status=AgentStatus(table.status),
        configuration=table.configuration,
        created_at=table.created_at,
        updated_at=table.updated_at,
    )

def _to_domain_credential(table: AgentCredentialTable) -> AgentCredential:
    """Helper mapper translating SQLAlchemy AgentCredentialTable model to pure domain AgentCredential entity."""
    return AgentCredential(
        id=table.id,
        agent_id=table.agent_id,
        credential_hash=table.credential_hash,
        description=table.description,
        created_at=table.created_at,
        expires_at=table.expires_at,
        revoked_at=table.revoked_at,
        last_used_at=table.last_used_at,
    )


class SQLAgentCredentialRepository(IAgentCredentialRepository):
    """SQLAlchemy concrete implementation of the IAgentCredentialRepository contract."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, credential_id: uuid.UUID) -> Optional[AgentCredential]:
        result = await self.session.execute(
            select(AgentCredentialTable).where(AgentCredentialTable.id == credential_id)
        )
        table = result.scalars().first()
        return _to_domain_credential(table) if table else None

    async def get_by_hash(self, credential_hash: str) -> Optional[AgentCredential]:
        result = await self.session.execute(
            select(AgentCredentialTable).where(AgentCredentialTable.credential_hash == credential_hash)
        )
        table = result.scalars().first()
        return _to_domain_credential(table) if table else None

    async def create(
        self,
        agent_id: uuid.UUID,
        credential_hash: str,
        description: Optional[str],
        expires_at: Optional[datetime],
    ) -> AgentCredential:
        table = AgentCredentialTable(
            agent_id=agent_id,
            credential_hash=credential_hash,
            description=description,
            expires_at=expires_at,
        )
        self.session.add(table)
        await self.session.flush()
        await self.session.refresh(table)
        return _to_domain_credential(table)

    async def revoke(self, credential_id: uuid.UUID) -> Optional[AgentCredential]:
        result = await self.session.execute(
            select(AgentCredentialTable).where(AgentCredentialTable.id == credential_id)
        )
        table = result.scalars().first()
        if not table:
            return None

        table.revoked_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(table)
        return _to_domain_credential(table)

    async def list_by_agent(self, agent_id: uuid.UUID) -> List[AgentCredential]:
        result = await self.session.execute(
            select(AgentCredentialTable)
            .where(AgentCredentialTable.agent_id == agent_id)
            .order_by(asc(AgentCredentialTable.created_at))
        )
        return [_to_domain_credential(t) for t in result.scalars().all()]

    async def update_last_used(self, credential_id: uuid.UUID, last_used_at: datetime) -> None:
        result = await self.session.execute(
            select(AgentCredentialTable).where(AgentCredentialTable.id == credential_id)
        )
        table = result.scalars().first()
        if table:
            if last_used_at.tzinfo is None:
                last_used_at = last_used_at.replace(tzinfo=timezone.utc)
            table.last_used_at = last_used_at
            await self.session.flush()


class SQLAgentRepository(IAgentRepository):
    """SQLAlchemy concrete implementation of the IAgentRepository contract.

    Notice: Responsibility is DATA ACCESS ONLY. Authorization logic belongs to application/domain layer.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, agent_id: uuid.UUID) -> Optional[Agent]:
        result = await self.session.execute(
            select(AgentTable).where(AgentTable.id == agent_id)
        )
        table = result.scalars().first()
        return _to_domain_agent(table) if table else None

    async def create(
        self,
        tenant_id: uuid.UUID,
        name: str,
        description: Optional[str],
        status: AgentStatus,
        configuration: dict,
    ) -> Agent:
        table = AgentTable(
            tenant_id=tenant_id,
            name=name,
            description=description,
            status=status.value,
            configuration=configuration,
        )
        self.session.add(table)
        await self.session.flush()  # Populate auto fields
        await self.session.refresh(table)
        return _to_domain_agent(table)

    async def update(
        self,
        agent_id: uuid.UUID,
        name: Optional[str],
        description: Optional[str],
        configuration: Optional[dict],
    ) -> Optional[Agent]:
        result = await self.session.execute(
            select(AgentTable).where(AgentTable.id == agent_id)
        )
        table = result.scalars().first()
        if not table:
            return None

        if name is not None:
            table.name = name
        if description is not None:
            table.description = description
        if configuration is not None:
            table.configuration = configuration

        await self.session.flush()
        await self.session.refresh(table)
        return _to_domain_agent(table)

    async def update_status(
        self,
        agent_id: uuid.UUID,
        status: AgentStatus,
    ) -> Optional[Agent]:
        result = await self.session.execute(
            select(AgentTable).where(AgentTable.id == agent_id)
        )
        table = result.scalars().first()
        if not table:
            return None

        table.status = status.value
        await self.session.flush()
        await self.session.refresh(table)
        return _to_domain_agent(table)

    async def list_by_tenant(self, tenant_id: uuid.UUID) -> List[Agent]:
        result = await self.session.execute(
            select(AgentTable)
            .where(AgentTable.tenant_id == tenant_id)
            .order_by(asc(AgentTable.created_at))
        )
        return [_to_domain_agent(t) for t in result.scalars().all()]


def _to_domain_grant(table: MemoryAccessGrantTable) -> MemoryAccessGrant:
    return MemoryAccessGrant(
        id=table.id,
        memory_id=table.memory_id,
        agent_id=table.agent_id,
        access_level=MemoryAccessLevel(table.access_level),
        granted_by_principal_type=PrincipalType(table.granted_by_principal_type),
        granted_by_user_id=table.granted_by_user_id,
        granted_by_agent_id=table.granted_by_agent_id,
        created_at=table.created_at,
        expires_at=table.expires_at,
        revoked_at=table.revoked_at,
    )


class SQLMemoryAccessGrantRepository(IMemoryAccessGrantRepository):
    """SQLAlchemy concrete implementation of the IMemoryAccessGrantRepository contract."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_memory_and_agent(self, memory_id: uuid.UUID, agent_id: uuid.UUID) -> Optional[MemoryAccessGrant]:
        result = await self.session.execute(
            select(MemoryAccessGrantTable)
            .where(MemoryAccessGrantTable.memory_id == memory_id)
            .where(MemoryAccessGrantTable.agent_id == agent_id)
        )
        table = result.scalars().first()
        return _to_domain_grant(table) if table else None

    async def save(self, grant: MemoryAccessGrant) -> MemoryAccessGrant:
        result = await self.session.execute(
            select(MemoryAccessGrantTable)
            .where(MemoryAccessGrantTable.memory_id == grant.memory_id)
            .where(MemoryAccessGrantTable.agent_id == grant.agent_id)
        )
        table = result.scalars().first()
        if table:
            # Update existing record for Upsert behavior
            table.access_level = grant.access_level.value
            table.granted_by_principal_type = grant.granted_by_principal_type.value
            table.granted_by_user_id = grant.granted_by_user_id
            table.granted_by_agent_id = grant.granted_by_agent_id
            table.expires_at = grant.expires_at
            table.revoked_at = grant.revoked_at
        else:
            table = MemoryAccessGrantTable(
                id=grant.id,
                memory_id=grant.memory_id,
                agent_id=grant.agent_id,
                access_level=grant.access_level.value,
                granted_by_principal_type=grant.granted_by_principal_type.value,
                granted_by_user_id=grant.granted_by_user_id,
                granted_by_agent_id=grant.granted_by_agent_id,
                expires_at=grant.expires_at,
                revoked_at=grant.revoked_at,
            )
            self.session.add(table)

        await self.session.flush()
        await self.session.refresh(table)
        return _to_domain_grant(table)

    async def list_active_by_memory(self, memory_id: uuid.UUID) -> List[MemoryAccessGrant]:
        result = await self.session.execute(
            select(MemoryAccessGrantTable)
            .where(MemoryAccessGrantTable.memory_id == memory_id)
            .where(MemoryAccessGrantTable.revoked_at.is_(None))
        )
        return [
            g for g in [_to_domain_grant(t) for t in result.scalars().all()]
            if g.is_active(datetime.now(timezone.utc))
        ]

    async def get_active_grant(self, memory_id: uuid.UUID, agent_id: uuid.UUID) -> Optional[MemoryAccessGrant]:
        result = await self.session.execute(
            select(MemoryAccessGrantTable)
            .where(MemoryAccessGrantTable.memory_id == memory_id)
            .where(MemoryAccessGrantTable.agent_id == agent_id)
            .where(MemoryAccessGrantTable.revoked_at.is_(None))
        )
        table = result.scalars().first()
        if not table:
            return None
        grant = _to_domain_grant(table)
        if grant.is_active(datetime.now(timezone.utc)):
            return grant
        return None






