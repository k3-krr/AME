import logging
import uuid
from typing import List, Optional

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from app.domain.entities import Agent, AgentStatus, AgentCredential
from app.domain.repositories import IAgentRepository, IAgentCredentialRepository

logger = logging.getLogger("ame_backend.application.agent_service")


class AgentService:
    """
    Application service managing Agent CRUD and lifecycle transitions.
    Enforces tenant boundaries and valid state machine transitions.
    """

    def __init__(self, agent_repo: IAgentRepository, credential_repo: IAgentCredentialRepository):
        self.agent_repo = agent_repo
        self.credential_repo = credential_repo

    async def create_agent(
        self,
        tenant_id: uuid.UUID,
        name: str,
        description: Optional[str] = None,
        configuration: Optional[dict] = None,
    ) -> Agent:
        """
        Creates and persists a new Agent under the given tenant boundary.
        """
        if not tenant_id:
            raise ValueError("tenant_id is required")

        if not name or not name.strip():
            raise ValueError("Agent name cannot be empty")

        config = configuration if configuration is not None else {}

        # Default initial status for a new agent is ACTIVE
        status = AgentStatus.ACTIVE

        agent = await self.agent_repo.create(
            tenant_id=tenant_id,
            name=name.strip(),
            description=description,
            status=status,
            configuration=config,
        )
        logger.info(f"Successfully created Agent: {name} (ID: {agent.id}) for tenant: {tenant_id}")
        return agent

    async def get_agent_by_id(self, agent_id: uuid.UUID, tenant_id: uuid.UUID) -> Agent:
        """
        Retrieves an Agent by ID, enforcing tenant ownership boundaries.
        """
        agent = await self.agent_repo.get_by_id(agent_id)
        if not agent:
            raise KeyError("Agent not found")

        if agent.tenant_id != tenant_id:
            logger.warning(f"Tenant {tenant_id} attempted unauthorized access to Agent {agent_id} owned by {agent.tenant_id}")
            raise PermissionError("Access denied: Tenant boundary violation")

        return agent

    async def update_agent(
        self,
        agent_id: uuid.UUID,
        tenant_id: uuid.UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        configuration: Optional[dict] = None,
    ) -> Agent:
        """
        Updates an existing Agent's mutable attributes after validating tenant boundaries
        and ensuring the agent has not been revoked.
        """
        agent = await self.get_agent_by_id(agent_id, tenant_id)

        if agent.status == AgentStatus.REVOKED:
            raise ValueError("Cannot update a revoked agent")

        if name is not None:
            if not name or not name.strip():
                raise ValueError("Agent name cannot be empty")
            name = name.strip()

        updated_agent = await self.agent_repo.update(
            agent_id=agent_id,
            name=name,
            description=description,
            configuration=configuration,
        )
        if not updated_agent:
            raise KeyError("Agent not found during update")

        logger.info(f"Successfully updated Agent: {agent_id} for tenant: {tenant_id}")
        return updated_agent

    async def list_agents(self, tenant_id: uuid.UUID) -> List[Agent]:
        """
        Lists all agents belonging to the specified tenant.
        """
        if not tenant_id:
            raise ValueError("tenant_id is required")
        return await self.agent_repo.list_by_tenant(tenant_id)

    async def suspend_agent(self, agent_id: uuid.UUID, tenant_id: uuid.UUID) -> Agent:
        """
        Transitions an Agent's status from ACTIVE to SUSPENDED.
        """
        agent = await self.get_agent_by_id(agent_id, tenant_id)

        if agent.status == AgentStatus.REVOKED:
            raise ValueError("Revoked agent status is terminal and cannot be changed")

        if agent.status == AgentStatus.SUSPENDED:
            # Already suspended, no-op
            return agent

        # Transition ACTIVE -> SUSPENDED
        updated = await self.agent_repo.update_status(agent_id, AgentStatus.SUSPENDED)
        if not updated:
            raise KeyError("Agent not found during status update")

        logger.info(f"Agent {agent_id} suspended by tenant {tenant_id}")
        return updated

    async def reactivate_agent(self, agent_id: uuid.UUID, tenant_id: uuid.UUID) -> Agent:
        """
        Transitions an Agent's status from SUSPENDED back to ACTIVE.
        """
        agent = await self.get_agent_by_id(agent_id, tenant_id)

        if agent.status == AgentStatus.REVOKED:
            raise ValueError("Revoked agent status is terminal and cannot be changed")

        if agent.status == AgentStatus.ACTIVE:
            # Already active, no-op
            return agent

        # Transition SUSPENDED -> ACTIVE
        updated = await self.agent_repo.update_status(agent_id, AgentStatus.ACTIVE)
        if not updated:
            raise KeyError("Agent not found during status update")

        logger.info(f"Agent {agent_id} reactivated by tenant {tenant_id}")
        return updated

    async def revoke_agent(self, agent_id: uuid.UUID, tenant_id: uuid.UUID) -> Agent:
        """
        Transitions an Agent's status to REVOKED. This state is terminal.
        """
        agent = await self.get_agent_by_id(agent_id, tenant_id)

        if agent.status == AgentStatus.REVOKED:
            # Already revoked, no-op
            return agent

        # Transition ACTIVE/SUSPENDED -> REVOKED
        updated = await self.agent_repo.update_status(agent_id, AgentStatus.REVOKED)
        if not updated:
            raise KeyError("Agent not found during status update")

        logger.info(f"Agent {agent_id} revoked by tenant {tenant_id}")
        return updated

    async def create_credential(
        self,
        agent_id: uuid.UUID,
        tenant_id: uuid.UUID,
        description: Optional[str] = None,
        expires_in_days: Optional[int] = None,
    ) -> tuple[AgentCredential, str]:
        """
        Creates a new high-entropy credential for the given Agent, enforcing ownership.
        """
        agent = await self.get_agent_by_id(agent_id, tenant_id)
        if agent.status == AgentStatus.REVOKED:
            raise ValueError("Cannot create credentials for a revoked agent")

        # Generate a high-entropy 256-bit API key (64 hex characters)
        raw_key = f"ame_agent_{secrets.token_hex(32)}"
        credential_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

        expires_at = None
        if expires_in_days is not None:
            if expires_in_days <= 0:
                raise ValueError("Expiration days must be positive")
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        credential = await self.credential_repo.create(
            agent_id=agent_id,
            credential_hash=credential_hash,
            description=description,
            expires_at=expires_at,
        )
        logger.info(f"Created new credential for Agent {agent_id} (Tenant: {tenant_id})")
        return credential, raw_key

    async def list_credentials(
        self,
        agent_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> List[AgentCredential]:
        """
        Lists metadata for all credentials belonging to the given Agent, enforcing ownership.
        """
        # Validate owner and exists
        await self.get_agent_by_id(agent_id, tenant_id)
        return await self.credential_repo.list_by_agent(agent_id)

    async def revoke_credential(
        self,
        agent_id: uuid.UUID,
        credential_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> AgentCredential:
        """
        Revokes an agent's credential by ID, enforcing ownership.
        """
        await self.get_agent_by_id(agent_id, tenant_id)
        
        credential = await self.credential_repo.get_by_id(credential_id)
        if not credential or credential.agent_id != agent_id:
            raise KeyError("Credential not found")

        if credential.revoked_at is not None:
            return credential  # Already revoked, no-op

        revoked = await self.credential_repo.revoke(credential_id)
        if not revoked:
            raise KeyError("Credential not found during revocation")
        logger.info(f"Credential {credential_id} revoked for Agent {agent_id}")
        return revoked

    async def authenticate_agent_by_key(self, raw_key: str) -> Agent:
        """
        Authenticates an agent using their raw credential API key.
        Rejects invalid, expired, revoked credentials, or suspended/revoked agents.
        Updates last_used_at on successful authentication.
        """
        if not raw_key or not raw_key.startswith("ame_agent_"):
            raise ValueError("Invalid credential format")

        credential_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        credential = await self.credential_repo.get_by_hash(credential_hash)
        if not credential:
            raise ValueError("Invalid credentials")

        agent = await self.agent_repo.get_by_id(credential.agent_id)
        if not agent:
            raise ValueError("Linked agent not found")

        # Validate credential active status
        current_time = datetime.now(timezone.utc)
        if not credential.is_active(current_time, agent.status):
            raise ValueError("Credentials are inactive or agent is suspended/revoked")

        # Track usage
        await self.credential_repo.update_last_used(credential.id, current_time)
        return agent

