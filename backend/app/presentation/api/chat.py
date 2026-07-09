import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, status, Query, Response
from fastapi.responses import StreamingResponse

from app.presentation.api.schemas import (
    ConversationCreateRequest,
    ConversationResponse,
    MessageCreateRequest,
    MessageResponse,
    StandardErrorResponse,
)

router = APIRouter(tags=["chat"])


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
):
    """
    Retrieves a paginated list of conversations belonging to the authenticated user.
    """
    # Stub response matching ConversationResponse schema structure
    return [
        ConversationResponse(
            id=uuid.uuid4(),
            title="Sample Conversation",
            system_prompt="You are a helpful assistant.",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
    ]


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
async def create_conversation(payload: ConversationCreateRequest):
    """
    Creates a new blank chat conversation canvas.
    """
    return ConversationResponse(
        id=uuid.uuid4(),
        title=payload.title or "New Conversation",
        system_prompt=payload.system_prompt,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Conversation successfully deleted"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        404: {"model": StandardErrorResponse, "description": "Conversation not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def delete_conversation(conversation_id: uuid.UUID):
    """
    Deletes an existing conversation session and all associated messages.
    """
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=List[MessageResponse],
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Retrieved messages history for the conversation"},
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        404: {"model": StandardErrorResponse, "description": "Conversation not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def list_messages(
    conversation_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100, description="Maximum number of messages to fetch"),
    before_id: Optional[uuid.UUID] = Query(None, description="Cursor message ID to fetch messages prior to"),
):
    """
    Fetches the message logs for a specific conversation using cursor-based pagination.
    """
    return [
        MessageResponse(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            sender_role="user",
            content="Hello!",
            memory_status="pending",
            created_at=datetime.now(timezone.utc)
        ),
        MessageResponse(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            sender_role="assistant",
            content="Hello! How can I help you today?",
            memory_status="pending",
            created_at=datetime.now(timezone.utc)
        )
    ]


@router.post(
    "/conversations/{conversation_id}/messages",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Successfully accepted message; returning assistant response stream",
            "content": {"text/event-stream": {}}
        },
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        404: {"model": StandardErrorResponse, "description": "Conversation not found"},
        500: {"model": StandardErrorResponse, "description": "Internal server error"},
    }
)
async def post_message(
    conversation_id: uuid.UUID,
    payload: MessageCreateRequest,
):
    """
    Submits a user message and yields an SSE stream containing the assistant's reply.
    """
    async def mock_sse_stream():
        # Step 1: Send message_id event
        assistant_msg_id = str(uuid.uuid4())
        yield f"event: message_id\ndata: {assistant_msg_id}\n\n"
        
        # Step 2: Stream content delta events
        sample_response = "This is a placeholder reply streaming from AME backend. In Milestone 2, we will integrate the LLM client here."
        for word in sample_response.split():
            yield f"event: delta\ndata: {word} \n\n"
            
        # Step 3: Send done event
        yield "event: done\ndata: [DONE]\n\n"

    return StreamingResponse(mock_sse_stream(), media_type="text/event-stream")
