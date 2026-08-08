import uuid
import logging
from typing import List
from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_db
from app.presentation.api.auth import get_current_user, get_access_context
from app.domain.entities import AccessContext
from app.infrastructure.db.models import UserTable
from app.infrastructure.repositories.sql_repos import SQLAgentRepository, SQLAgentCredentialRepository
from app.application.agent_service import AgentService
from app.presentation.api.schemas import (
    AgentCreateRequest,
    AgentUpdateRequest,
    AgentResponse,
    StandardErrorResponse,
    AgentCredentialCreateRequest,
    AgentCredentialResponse,
    AgentCredentialRevokeResponse,
)

logger = logging.getLogger("ame_backend.api.agents")

router = APIRouter(prefix="/agents", tags=["agents"])


def get_agent_service(db: AsyncSession = Depends(get_db)) -> AgentService:
    """Dependency helper instantiating AgentService with SQLAgentRepository and SQLAgentCredentialRepository."""
    repo = SQLAgentRepository(db)
    cred_repo = SQLAgentCredentialRepository(db)
    return AgentService(repo, cred_repo)


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


@router.post(
    "/{agent_id}/credentials",
    response_model=AgentCredentialResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Credential successfully issued"},
        400: {"model": StandardErrorResponse, "description": "Invalid parameters or constraints violated"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        403: {"model": StandardErrorResponse, "description": "Forbidden access to agent"},
        404: {"model": StandardErrorResponse, "description": "Agent not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def issue_agent_credential(
    agent_id: uuid.UUID,
    payload: AgentCredentialCreateRequest,
    current_user: UserTable = Depends(get_current_user),
    service: AgentService = Depends(get_agent_service),
):
    """
    Issues a new API key credential for an agent.
    The raw API key is returned exactly once in the response.
    """
    try:
        credential, raw_key = await service.create_credential(
            agent_id=agent_id,
            tenant_id=current_user.id,
            description=payload.description,
            expires_in_days=payload.expires_in_days,
        )
        response_data = AgentCredentialResponse.model_validate(credential)
        response_data.raw_key = raw_key
        return response_data
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
        logger.error(f"Error issuing agent credential: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to issue agent credential."
        )


@router.get(
    "/{agent_id}/credentials",
    response_model=List[AgentCredentialResponse],
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Agent credentials metadata list retrieved successfully"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        403: {"model": StandardErrorResponse, "description": "Forbidden access to agent"},
        404: {"model": StandardErrorResponse, "description": "Agent not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def list_agent_credentials(
    agent_id: uuid.UUID,
    current_user: UserTable = Depends(get_current_user),
    service: AgentService = Depends(get_agent_service),
):
    """
    Retrieves metadata for all credentials assigned to the agent.
    Raw keys and hashes are never returned.
    """
    try:
        credentials = await service.list_credentials(agent_id=agent_id, tenant_id=current_user.id)
        return [AgentCredentialResponse.model_validate(c) for c in credentials]
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
        logger.error(f"Error listing agent credentials: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list agent credentials."
        )


@router.post(
    "/{agent_id}/credentials/{credential_id}/revoke",
    response_model=AgentCredentialRevokeResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Agent credential successfully revoked"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        403: {"model": StandardErrorResponse, "description": "Forbidden access to agent or credential"},
        404: {"model": StandardErrorResponse, "description": "Agent or credential not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def revoke_agent_credential(
    agent_id: uuid.UUID,
    credential_id: uuid.UUID,
    current_user: UserTable = Depends(get_current_user),
    service: AgentService = Depends(get_agent_service),
):
    """
    Revokes a specific agent credential by ID.
    Once revoked, the credential becomes permanently unusable.
    """
    try:
        credential = await service.revoke_credential(
            agent_id=agent_id,
            credential_id=credential_id,
            tenant_id=current_user.id,
        )
        return AgentCredentialRevokeResponse(
            id=credential.id,
            revoked_at=credential.revoked_at
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
        logger.error(f"Error revoking agent credential: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke agent credential."
        )


@router.get(
    "/me/context",
    status_code=status.HTTP_200_OK,
)
async def get_my_context(
    context: AccessContext = Depends(get_access_context),
):
    """
    Returns the resolved AccessContext for testing/verification of credential authentication.
    """
    return {
        "tenant_id": str(context.tenant_id),
        "principal_type": context.principal_type.value,
        "user_id": str(context.user_id) if context.user_id else None,
        "agent_id": str(context.agent_id) if context.agent_id else None,
    }


