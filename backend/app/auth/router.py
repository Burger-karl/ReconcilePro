"""/api/auth routes. Thin: validate (schemas), call the service, shape the response."""

from fastapi import APIRouter, HTTPException, status

from app.auth import service
from app.auth.models import User, Workspace
from app.auth.schemas import LoginRequest, MeResponse, RegisterRequest, TokenResponse, UserRead, WorkspaceRead
from app.core.deps import CurrentUser, SessionDep
from app.core.security import create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


def token_response(user: User) -> TokenResponse:
    return TokenResponse(access_token=create_access_token(user.id), user=UserRead.model_validate(user, from_attributes=True))


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, session: SessionDep) -> TokenResponse:
    try:
        user = service.register(session, data)
    except service.EmailAlreadyRegistered:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")
    return token_response(user)


@router.post("/login")
def login(data: LoginRequest, session: SessionDep) -> TokenResponse:
    user = service.authenticate(session, data.email, data.password)
    if user is None:
        # Same message whether the email or the password is wrong.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    return token_response(user)


@router.get("/me")
def me(user: CurrentUser, session: SessionDep) -> MeResponse:
    workspace = session.get(Workspace, user.workspace_id)
    return MeResponse(
        user=UserRead.model_validate(user, from_attributes=True),
        workspace=WorkspaceRead.model_validate(workspace, from_attributes=True),
    )
