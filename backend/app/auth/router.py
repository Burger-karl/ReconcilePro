"""/api/v1/auth routes. Thin: validate (schemas), call the service, shape the response."""

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, status

from app.auth import google, service
from app.auth.models import User, Workspace
from app.auth.schemas import (
    ForgotPasswordRequest,
    GoogleLoginRequest,
    GoogleRegisterRequest,
    LoginRequest,
    MeResponse,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserRead,
    WorkspaceRead,
)
from app.core.deps import CurrentUser, SessionDep
from app.core.limits import login_attempts
from app.core.security import create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])

ALREADY_REGISTERED = "An account with this email already exists"


def token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id, token_version=user.token_version),
        user=UserRead.model_validate(user, from_attributes=True),
    )


def verified_google_identity(credential: str) -> google.GoogleIdentity:
    """Check the Google ID token, turning each failure into the right HTTP status."""
    try:
        return google.verify_google_credential(credential)
    except google.GoogleNotConfigured:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google sign-in is not configured")
    except google.GoogleUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google sign-in is unavailable, try again"
        )
    except google.InvalidGoogleCredential:
        # One message for every reason (expired, wrong app, forged...): no hints for an attacker.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google sign-in failed")


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, session: SessionDep) -> TokenResponse:
    try:
        user = service.register(session, data)
    except service.EmailAlreadyRegistered:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=ALREADY_REGISTERED)
    return token_response(user)


@router.post("/login")
def login(data: LoginRequest, session: SessionDep) -> TokenResponse:
    email = service.normalise_email(data.email)
    # Checked BEFORE the password, so while blocked even the right password gets no answer:
    # an attacker can't keep guessing and spot the one attempt that differs (D-42).
    if login_attempts.is_blocked(email):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed sign-in attempts. Try again in 15 minutes, or reset your password.",
        )
    user = service.authenticate(session, email, data.password)
    if user is None:
        login_attempts.record_failure(email)
        # Same message whether the email or the password is wrong.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    login_attempts.clear(email)
    return token_response(user)


@router.post("/google/register", status_code=status.HTTP_201_CREATED)
def google_register(data: GoogleRegisterRequest, session: SessionDep) -> TokenResponse:
    identity = verified_google_identity(data.credential)
    try:
        user = service.register_with_google(session, identity, data.workspace_name)
    except service.EmailAlreadyRegistered:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=ALREADY_REGISTERED)
    return token_response(user)


@router.post("/google/login")
def google_login(data: GoogleLoginRequest, session: SessionDep) -> TokenResponse:
    identity = verified_google_identity(data.credential)
    try:
        user = service.login_with_google(session, identity)
    except service.NoAccountForGoogleUser:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No account is linked to this Google account. Register, or sign in with your password.",
        )
    return token_response(user)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(data: ForgotPasswordRequest, session: SessionDep, background: BackgroundTasks) -> MessageResponse:
    result = service.request_password_reset(session, data.email)
    if result is not None:
        user, raw_token = result
        # Sent after the response, so a known email doesn't answer slower than an unknown one (D-39).
        background.add_task(service.send_password_reset_email, user.email, raw_token)
    # Identical answer either way: this endpoint must not reveal which emails have accounts.
    return MessageResponse(detail="If that email has an account, a reset link is on its way.")


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(data: ResetPasswordRequest, session: SessionDep) -> Response:
    try:
        service.reset_password(session, data.token, data.new_password)
    except service.InvalidResetToken:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This reset link is invalid or has expired")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me")
def me(user: CurrentUser, session: SessionDep) -> MeResponse:
    workspace = session.get(Workspace, user.workspace_id)
    return MeResponse(
        user=UserRead.model_validate(user, from_attributes=True),
        workspace=WorkspaceRead.model_validate(workspace, from_attributes=True),
    )
