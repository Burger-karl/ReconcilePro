"""Request and response bodies for /api/v1/auth. Table models are never returned directly,
so password_hash can never leak into a response."""

import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator

# One rule for every password the user chooses (register and reset).
# The upper limit stops someone sending a megabyte "password" to make argon2 work hard.
PASSWORD_MIN, PASSWORD_MAX = 8, 128


def _strip_email(value: str) -> str:
    # Users paste emails with spaces; strip before EmailStr validates.
    return value.strip() if isinstance(value, str) else value


def _workspace_name_not_blank(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Workspace name cannot be blank")
    return value


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)
    workspace_name: str = Field(min_length=1, max_length=200)

    _strip = field_validator("email", mode="before")(_strip_email)
    _not_blank = field_validator("workspace_name")(_workspace_name_not_blank)


class LoginRequest(BaseModel):
    # Plain str, not EmailStr: a typo should get "Incorrect email or password", not a 422.
    email: str = Field(max_length=320)
    password: str = Field(max_length=PASSWORD_MAX)


class GoogleLoginRequest(BaseModel):
    # The ID token from Google's sign-in button. Real ones are ~1-2 KB; the cap stops oversized junk.
    credential: str = Field(min_length=1, max_length=4096)


class GoogleRegisterRequest(GoogleLoginRequest):
    workspace_name: str = Field(min_length=1, max_length=200)

    _not_blank = field_validator("workspace_name")(_workspace_name_not_blank)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    _strip = field_validator("email", mode="before")(_strip_email)


class ResetPasswordRequest(BaseModel):
    # Real tokens are 43 characters; anything far longer is junk.
    token: str = Field(max_length=256)
    new_password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)


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


class MessageResponse(BaseModel):
    detail: str
