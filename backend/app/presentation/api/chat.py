import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, status, Query, Response, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_db
from app.presentation.api.auth import get_current_user
from app.infrastructure.db.models import UserTable
from app.infrastructure.repositories.sql_repos import (
    SQLConversationRepository,
    SQLMessageRepository,
)
from app.infrastructure.services.memory_service import MemoryService
from app.infrastructure.clients.llm_client import LLMService
from app.application.chat_service import ChatService
from app.presentation.api.schemas import (
    ConversationCreateRequest,
    ConversationResponse,
    MessageCreateRequest,
    MessageResponse,
    StandardErrorResponse,
)

logger = logging.getLogger("ame_backend.api.chat")

router = APIRouter(tags=["chat"])

# Instantiate singletons for infrastructure services
memory_service_impl = MemoryService()
llm_service_impl = LLMService()


def get_chat_service(db: AsyncSession = Depends(get_db)) -> ChatService:
    """Dependency helper instantiating ChatService with standard database repositories."""
    conversation_repo = SQLConversationRepository(db)
    message_repo = SQLMessageRepository(db)
    return ChatService(
        conversation_repo=conversation_repo,
        message_repo=message_repo,
        llm_service=llm_service_impl,
        memory_service=memory_service_impl,
    )


@router.get(
    "/conversations",
    response_model=List[ConversationResponse],
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Retrieved list of active conversations"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def list_conversations(
    page: int = Query(1, ge=1, description="Page number for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Number of conversations to return per page"),
    current_user: UserTable = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Retrieves a paginated list of conversations belonging to the authenticated user.
    """
    try:
        conversations = await chat_service.list_conversations(
            user_id=current_user.id, page=page, limit=limit
        )
        return [ConversationResponse.from_orm(c) for c in conversations]
    except Exception as e:
        logger.error(f"Error listing conversations: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve conversations."
        )


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Conversation canvas successfully created"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def create_conversation(
    payload: ConversationCreateRequest,
    current_user: UserTable = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Creates a new blank chat conversation canvas.
    """
    try:
        conversation = await chat_service.create_conversation(
            user_id=current_user.id,
            title=payload.title,
            system_prompt=payload.system_prompt,
        )
        return ConversationResponse.from_orm(conversation)
    except Exception as e:
        logger.error(f"Error creating conversation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create conversation."
        )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Conversation successfully deleted"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        403: {"model": StandardErrorResponse, "description": "Forbidden access to resource"},
        404: {"model": StandardErrorResponse, "description": "Conversation not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: UserTable = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Deletes an existing conversation session and all associated messages.
    """
    try:
        await chat_service.delete_conversation(
            user_id=current_user.id, conversation_id=conversation_id
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
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
        logger.error(f"Error deleting conversation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete conversation."
        )


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=List[MessageResponse],
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Retrieved messages history for the conversation"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        403: {"model": StandardErrorResponse, "description": "Forbidden access to resource"},
        404: {"model": StandardErrorResponse, "description": "Conversation not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def list_messages(
    conversation_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100, description="Maximum number of messages to fetch"),
    before_id: Optional[uuid.UUID] = Query(None, description="Cursor message ID to fetch messages prior to"),
    current_user: UserTable = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Fetches the message logs for a specific conversation using cursor-based pagination.
    """
    try:
        messages = await chat_service.list_messages(
            user_id=current_user.id,
            conversation_id=conversation_id,
            limit=limit,
            before_id=before_id,
        )
        return [MessageResponse.from_orm(m) for m in messages]
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
        logger.error(f"Error fetching message logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve messages."
        )


@router.post(
    "/conversations/{conversation_id}/messages",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Successfully accepted message; returning assistant response stream",
            "content": {"text/event-stream": {}}
        },
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        403: {"model": StandardErrorResponse, "description": "Forbidden access to resource"},
        404: {"model": StandardErrorResponse, "description": "Conversation not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def post_message(
    conversation_id: uuid.UUID,
    payload: MessageCreateRequest,
    current_user: UserTable = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Submits a user message and yields an SSE stream containing the assistant's reply.
    """
    try:
        stream_gen = chat_service.post_message_stream(
            user_id=current_user.id,
            conversation_id=conversation_id,
            content=payload.content,
        )
        return StreamingResponse(stream_gen, media_type="text/event-stream")
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
        logger.error(f"Error processing streaming message: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process and stream message response."
        )
