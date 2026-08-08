import logging
import uuid
from typing import List, Optional

from app.domain.entities import Agent, AgentStatus
from app.domain.repositories import IAgentRepository

logger = logging.getLogger("ame_backend.application.agent_service")


class AgentService:
    """
    Application service managing Agent CRUD and lifecycle transitions.
    Enforces tenant boundaries and valid state machine transitions.
    """

    def __init__(self, agent_repo: IAgentRepository):
        self.agent_repo = agent_repo

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
