import uuid
import logging
from typing import List
from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_db
from app.presentation.api.auth import get_current_user
from app.infrastructure.db.models import UserTable
from app.infrastructure.repositories.sql_repos import SQLAgentRepository
from app.application.agent_service import AgentService
from app.presentation.api.schemas import (
    AgentCreateRequest,
    AgentUpdateRequest,
    AgentResponse,
    StandardErrorResponse,
)

logger = logging.getLogger("ame_backend.api.agents")

router = APIRouter(prefix="/agents", tags=["agents"])


def get_agent_service(db: AsyncSession = Depends(get_db)) -> AgentService:
    """Dependency helper instantiating AgentService with SQLAgentRepository."""
    repo = SQLAgentRepository(db)
    return AgentService(repo)


@router.post(
    "",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Agent successfully created"},
        400: {"model": StandardErrorResponse, "description": "Invalid input or constraints violated"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def create_agent(
    payload: AgentCreateRequest,
    current_user: UserTable = Depends(get_current_user),
    service: AgentService = Depends(get_agent_service),
):
    """
    Creates a new agent owned by the authenticated tenant/user.
    """
    try:
        return await service.create_agent(
            tenant_id=current_user.id,
            name=payload.name,
            description=payload.description,
            configuration=payload.configuration,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create agent."
        )


@router.get(
    "",
    response_model=List[AgentResponse],
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Retrieved list of agents for the authenticated tenant"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def list_agents(
    current_user: UserTable = Depends(get_current_user),
    service: AgentService = Depends(get_agent_service),
):
    """
    Lists all agents scoped to the current tenant/user.
    """
    try:
        return await service.list_agents(tenant_id=current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error listing agents: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list agents."
        )


@router.get(
    "/{agent_id}",
    response_model=AgentResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Agent successfully retrieved"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        403: {"model": StandardErrorResponse, "description": "Forbidden (tenant boundary violation)"},
        404: {"model": StandardErrorResponse, "description": "Agent not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def get_agent(
    agent_id: uuid.UUID,
    current_user: UserTable = Depends(get_current_user),
    service: AgentService = Depends(get_agent_service),
):
    """
    Retrieves a specific agent after verifying tenant boundary access.
    """
    try:
        return await service.get_agent_by_id(agent_id=agent_id, tenant_id=current_user.id)
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error fetching agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve agent."
        )


@router.patch(
    "/{agent_id}",
    response_model=AgentResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Agent successfully updated"},
        400: {"model": StandardErrorResponse, "description": "Invalid input or update rejected"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        403: {"model": StandardErrorResponse, "description": "Forbidden (tenant boundary violation)"},
        404: {"model": StandardErrorResponse, "description": "Agent not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def update_agent(
    agent_id: uuid.UUID,
    payload: AgentUpdateRequest,
    current_user: UserTable = Depends(get_current_user),
    service: AgentService = Depends(get_agent_service),
):
    """
    Updates an agent's attributes (excluding state) under tenant boundary checks.
    """
    try:
        return await service.update_agent(
            agent_id=agent_id,
            tenant_id=current_user.id,
            name=payload.name,
            description=payload.description,
            configuration=payload.configuration,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update agent."
        )


@router.post(
    "/{agent_id}/suspend",
    response_model=AgentResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Agent successfully suspended"},
        400: {"model": StandardErrorResponse, "description": "Invalid transition or revoked agent"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        403: {"model": StandardErrorResponse, "description": "Forbidden"},
        404: {"model": StandardErrorResponse, "description": "Agent not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def suspend_agent(
    agent_id: uuid.UUID,
    current_user: UserTable = Depends(get_current_user),
    service: AgentService = Depends(get_agent_service),
):
    """
    Suspends an active agent.
    """
    try:
        return await service.suspend_agent(agent_id=agent_id, tenant_id=current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error suspending agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to suspend agent."
        )


@router.post(
    "/{agent_id}/reactivate",
    response_model=AgentResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Agent successfully reactivated"},
        400: {"model": StandardErrorResponse, "description": "Invalid transition or revoked agent"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        403: {"model": StandardErrorResponse, "description": "Forbidden"},
        404: {"model": StandardErrorResponse, "description": "Agent not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def reactivate_agent(
    agent_id: uuid.UUID,
    current_user: UserTable = Depends(get_current_user),
    service: AgentService = Depends(get_agent_service),
):
    """
    Reactivates a suspended agent.
    """
    try:
        return await service.reactivate_agent(agent_id=agent_id, tenant_id=current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error reactivating agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reactivate agent."
        )


@router.post(
    "/{agent_id}/revoke",
    response_model=AgentResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Agent successfully revoked"},
        400: {"model": StandardErrorResponse, "description": "Invalid operation"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        403: {"model": StandardErrorResponse, "description": "Forbidden"},
        404: {"model": StandardErrorResponse, "description": "Agent not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def revoke_agent(
    agent_id: uuid.UUID,
    current_user: UserTable = Depends(get_current_user),
    service: AgentService = Depends(get_agent_service),
):
    """
    Revokes an agent. This state is terminal.
    """
    try:
        return await service.revoke_agent(agent_id=agent_id, tenant_id=current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error revoking agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke agent."
        )
