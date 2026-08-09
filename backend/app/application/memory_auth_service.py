import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from app.domain.entities import (
    Memory,
    MemoryAccessLevel,
    MemoryAccessGrant,
    PrincipalType,
    AccessContext,
    AgentStatus,
    MemoryStatus,
    MemoryAuthorizationFilterSpec,
)
from app.domain.repositories import (
    IMemoryRepository,
    IAgentRepository,
    IMemoryAccessGrantRepository,
)

logger = logging.getLogger("ame_backend.application.memory_auth_service")


class MemoryAuthorizationService:
    """
    Application service that enforces memory ownership boundaries,
    permission checks (READ/WRITE/MANAGE), and handles memory access grant lifecycles.
    """

    def __init__(
        self,
        memory_repo: IMemoryRepository,
        agent_repo: IAgentRepository,
        grant_repo: IMemoryAccessGrantRepository,
    ):
        self.memory_repo = memory_repo
        self.agent_repo = agent_repo
        self.grant_repo = grant_repo

    async def enforce_access(
        self,
        access_context: AccessContext,
        memory: Memory,
        required_level: MemoryAccessLevel,
    ) -> None:
        """
        Enforces access rights.
        - Denies cross-tenant requests by raising KeyError("Memory not found") to prevent resource discovery.
        - Allows human tenant owners (USER principal type) full MANAGE access.
        - Restricts suspended/revoked agents from accessing memories.
        - Grants automatic MANAGE permission to memory creator/owner agents.
        - Checks for active, unexpired MemoryAccessGrants for other agents.
        """
        # Strict tenant boundary check (cross-tenant isolation)
        spec = MemoryAuthorizationFilterSpec(access_context, datetime.now(timezone.utc))
        if memory.user_id != spec.tenant_id:
            logger.warning(
                f"Cross-tenant access attempted: context tenant {access_context.tenant_id} != memory tenant {memory.user_id}"
            )
            raise KeyError("Memory not found")

        if not spec.is_agent:
            # Human users have full MANAGE rights within their tenant
            return

        if spec.is_agent:
            # Soft-deleted memories are hidden from agent access to prevent discovery
            if memory.status == MemoryStatus.DELETED:
                raise KeyError("Memory not found")

            # Verify agent status
            agent = await self.agent_repo.get_by_id(spec.agent_id)
            if not agent or agent.status != AgentStatus.ACTIVE:
                raise PermissionError("Access denied: agent is not active")

            # Agent owner check (creator has automatic MANAGE level)
            if memory.agent_id == spec.agent_id:
                return

            # Lookup active grant
            grant = await self.grant_repo.get_active_grant(memory.id, spec.agent_id)
            if not grant:
                raise PermissionError("Access denied: no active grant found")

            # Validate using the domain specification
            if not spec.is_satisfied_by(memory, [grant]):
                raise PermissionError("Access denied: no active grant found")

            # Validate permission hierarchy
            allowed = False
            if required_level == MemoryAccessLevel.READ:
                allowed = grant.access_level in (
                    MemoryAccessLevel.READ,
                    MemoryAccessLevel.WRITE,
                    MemoryAccessLevel.MANAGE,
                )
            elif required_level == MemoryAccessLevel.WRITE:
                allowed = grant.access_level in (
                    MemoryAccessLevel.WRITE,
                    MemoryAccessLevel.MANAGE,
                )
            elif required_level == MemoryAccessLevel.MANAGE:
                allowed = grant.access_level == MemoryAccessLevel.MANAGE

            if not allowed:
                raise PermissionError(
                    f"Access denied: insufficient permission level. Required: {required_level.value}, Granted: {grant.access_level.value}"
                )
            return

        raise PermissionError("Access denied: invalid principal context")

    async def grant_access(
        self,
        access_context: AccessContext,
        memory_id: uuid.UUID,
        target_agent_id: uuid.UUID,
        level: MemoryAccessLevel,
        expires_at: Optional[datetime] = None,
    ) -> MemoryAccessGrant:
        """
        Creates or updates a memory access grant for a target agent.
        - Enforces that the granting principal has MANAGE access.
        - Enforces that the target agent exists and resides in the same tenant.
        - Performs an upsert (reactivates revoked/expired grants instead of creating duplicates).
        """
        memory = await self.memory_repo.get_by_id(memory_id)
        if not memory:
            raise KeyError("Memory not found")

        # Enforce grantor has MANAGE permissions (this also checks tenant boundaries)
        await self.enforce_access(access_context, memory, MemoryAccessLevel.MANAGE)

        # Enforce that the target agent belongs to the same tenant (reject cross-tenant grants safely)
        target_agent = await self.agent_repo.get_by_id(target_agent_id)
        if not target_agent or target_agent.tenant_id != access_context.tenant_id:
            logger.warning(
                f"Target agent {target_agent_id} not found or tenant mismatch with grantor tenant {access_context.tenant_id}"
            )
            raise KeyError("Agent not found")

        # Determine grant provenance
        if access_context.principal_type == PrincipalType.USER:
            granted_by_principal_type = PrincipalType.USER
            granted_by_user_id = access_context.user_id
            granted_by_agent_id = None
        else:
            granted_by_principal_type = PrincipalType.AGENT
            granted_by_user_id = None
            granted_by_agent_id = access_context.agent_id

        # Upsert grant
        existing = await self.grant_repo.get_by_memory_and_agent(memory_id, target_agent_id)
        if existing:
            existing.access_level = level
            existing.granted_by_principal_type = granted_by_principal_type
            existing.granted_by_user_id = granted_by_user_id
            existing.granted_by_agent_id = granted_by_agent_id
            existing.expires_at = expires_at
            existing.revoked_at = None
            return await self.grant_repo.save(existing)
        else:
            grant = MemoryAccessGrant(
                id=uuid.uuid4(),
                memory_id=memory_id,
                agent_id=target_agent_id,
                access_level=level,
                granted_by_principal_type=granted_by_principal_type,
                granted_by_user_id=granted_by_user_id,
                granted_by_agent_id=granted_by_agent_id,
                created_at=datetime.now(timezone.utc),
                expires_at=expires_at,
                revoked_at=None,
            )
            return await self.grant_repo.save(grant)

    async def list_active_grants(
        self,
        access_context: AccessContext,
        memory_id: uuid.UUID,
    ) -> List[MemoryAccessGrant]:
        """
        Lists all active, unexpired grants for a memory.
        Enforces grantor has MANAGE permissions.
        """
        memory = await self.memory_repo.get_by_id(memory_id)
        if not memory:
            raise KeyError("Memory not found")

        await self.enforce_access(access_context, memory, MemoryAccessLevel.MANAGE)
        return await self.grant_repo.list_active_by_memory(memory_id)

    async def revoke_access(
        self,
        access_context: AccessContext,
        memory_id: uuid.UUID,
        target_agent_id: uuid.UUID,
    ) -> MemoryAccessGrant:
        """
        Revokes a memory access grant by setting revoked_at to the current time.
        Enforces grantor has MANAGE permissions.
        """
        memory = await self.memory_repo.get_by_id(memory_id)
        if not memory:
            raise KeyError("Memory not found")

        await self.enforce_access(access_context, memory, MemoryAccessLevel.MANAGE)

        grant = await self.grant_repo.get_by_memory_and_agent(memory_id, target_agent_id)
        if not grant:
            raise KeyError("Grant not found")

        # Mark revoked
        grant.revoked_at = datetime.now(timezone.utc)
        return await self.grant_repo.save(grant)
