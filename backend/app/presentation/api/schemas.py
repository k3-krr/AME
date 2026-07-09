import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


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
