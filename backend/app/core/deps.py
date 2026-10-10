"""FastAPI dependencies shared by every feature.

Use in a route:
    def list_things(user: CurrentUser, session: SessionDep): ...
    ... .where(Thing.workspace_id == user.workspace_id)   # invariant 8

The workspace always comes from the user row in the database, never from the request or the token.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from app.auth.models import User
from app.core.db import get_session
from app.core.security import read_access_token

SessionDep = Annotated[Session, Depends(get_session)]

# auto_error=False so we can return our own 401 message instead of FastAPI's default 403.
bearer_scheme = HTTPBearer(auto_error=False)

NOT_AUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None:
        raise NOT_AUTHENTICATED
    claims = read_access_token(credentials.credentials)
    if claims is None:
        raise NOT_AUTHENTICATED
    user_id, token_version = claims
    # The token can outlive the user (deleted account), so the user must still exist.
    user = session.get(User, user_id)
    if user is None:
        raise NOT_AUTHENTICATED
    # A password reset bumps user.token_version, so tokens issued before it are refused here (D-41).
    if token_version != user.token_version:
        raise NOT_AUTHENTICATED
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_owner(user: CurrentUser) -> User:
    """For owner-only actions (e.g. inviting members, later)."""
    if user.role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the workspace owner can do this")
    return user
