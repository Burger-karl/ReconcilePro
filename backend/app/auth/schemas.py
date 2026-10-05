"""Request and response bodies for /api/auth. Table models are never returned directly,
so password_hash can never leak into a response."""

import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    workspace_name: str = Field(min_length=1, max_length=200)

    @field_validator("email", mode="before")
    @classmethod
    def strip_email(cls, value: str) -> str:
        # Users paste emails with spaces; strip before EmailStr validates.
        return value.strip() if isinstance(value, str) else value

    @field_validator("workspace_name")
    @classmethod
    def workspace_name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Workspace name cannot be blank")
        return value


class LoginRequest(BaseModel):
    # Plain str, not EmailStr: a typo should get "Incorrect email or password", not a 422.
    email: str
    password: str


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    workspace_id: uuid.UUID


class WorkspaceRead(BaseModel):
    id: uuid.UUID
    name: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class MeResponse(BaseModel):
    user: UserRead
    workspace: WorkspaceRead
