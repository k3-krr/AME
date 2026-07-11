import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field

from app.domain.entities import MemoryType, MemoryStatus



# --- Request Schemas ---

class UserRegisterRequest(BaseModel):
    """Schema representing a registration request."""
    email: EmailStr = Field(..., description="User's unique email address")
    password: str = Field(..., min_length=8, max_length=128, description="User's secure password")


class UserLoginRequest(BaseModel):
    """Schema representing a login request."""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")


class ConversationCreateRequest(BaseModel):
    """Schema for creating a new conversation canvas."""
    title: Optional[str] = Field(None, max_length=100, description="Optional title for the conversation")
    system_prompt: Optional[str] = Field(None, description="Optional custom system instructions")


class MessageCreateRequest(BaseModel):
    """Schema for submitting a new message."""
    content: str = Field(..., min_length=1, max_length=10000, description="The message content")


# --- Response Schemas ---

class UserResponse(BaseModel):
    """Schema representing basic user metadata response."""
    id: uuid.UUID
    email: EmailStr
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    """Schema representing a conversation record response."""
    id: uuid.UUID
    title: str
    system_prompt: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """Schema representing a message record response."""
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_role: str
    content: str
    memory_status: str
    created_at: datetime

    class Config:
        from_attributes = True


class StandardErrorResponse(BaseModel):
    """Unified API error format specification."""
    error_code: str
    message: str
    details: Optional[dict] = None


# --- Memory Schemas ---

class MemoryCreateRequest(BaseModel):
    """Schema representing a request to create a new memory."""
    conversation_id: Optional[uuid.UUID] = Field(None, description="Optional conversation context link")
    content: str = Field(..., min_length=1, max_length=10000, description="The memory content payload")
    memory_type: MemoryType = Field(..., description="The type classification of the memory")
    importance: float = Field(..., ge=0.0, le=1.0, description="Importance weight score between 0.0 and 1.0")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence/reliability score between 0.0 and 1.0")
    metadata: Optional[dict] = Field(None, description="Custom metadata key-value storage object")


class MemoryUpdateRequest(BaseModel):
    """Schema representing a request to update an existing memory."""
    content: Optional[str] = Field(None, min_length=1, max_length=10000, description="Optional updated memory content payload")
    memory_type: Optional[MemoryType] = Field(None, description="Optional updated type classification")
    importance: Optional[float] = Field(None, ge=0.0, le=1.0, description="Optional updated importance score")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Optional updated confidence score")
    status: Optional[MemoryStatus] = Field(None, description="Optional updated status state")
    metadata: Optional[dict] = Field(None, description="Optional updated custom metadata key-value object")


class MemoryResponse(BaseModel):
    """Schema representing a memory entity record response."""
    id: uuid.UUID
    user_id: uuid.UUID
    conversation_id: Optional[uuid.UUID]
    content: str
    memory_type: MemoryType
    importance: float
    confidence: float
    status: MemoryStatus
    created_at: datetime
    updated_at: datetime
    last_accessed_at: datetime
    version: int
    metadata: dict = Field(..., alias="metadata")  # Alias or direct mapping

    class Config:
        from_attributes = True
        populate_by_name = True


class MemorySearchResponse(BaseModel):
    """Schema representing a semantic search result matching memory."""
    memory: MemoryResponse
    similarity: float


class ReindexResponse(BaseModel):
    """Schema representing the result of manual reindexing operations."""
    reindexed_count: int

