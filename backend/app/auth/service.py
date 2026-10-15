"""Registration, login (password or Google) and password reset. Routes call these; no HTTP here."""

from datetime import timedelta

from psycopg.errors import UniqueViolation
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from app.audit.service import record
from app.auth.google import GoogleIdentity
from app.auth.models import PasswordResetToken, User, Workspace
from app.auth.schemas import RegisterRequest
from app.core.config import settings
from app.core.security import hash_password, hash_reset_token, new_reset_token, verify_password
from app.core.time import utc_now
from app.email import service as email_service


MAX_RESET_EMAILS_PER_HOUR = 3


class EmailAlreadyRegistered(Exception):
    pass


class NoAccountForGoogleUser(Exception):
    pass


class InvalidResetToken(Exception):
    pass


def normalise_email(email: str) -> str:
    return email.strip().lower()


def _create_workspace_and_owner(
    session: Session, *, email: str, workspace_name: str, password_hash: str | None, google_sub: str | None
) -> User:
    """Create a workspace and its owner in ONE transaction.

    If anything fails (e.g. the email is taken), nothing is committed, so we never leave
    a workspace with no owner behind.
    """
    workspace = Workspace(name=workspace_name)
    session.add(workspace)
    # Flush = send the INSERT now, inside the still-open transaction. Without it SQLAlchemy may insert
    # the user first (we declare no relationship() for it to order by) and the foreign key fails.
    session.flush()

    user = User(
        workspace_id=workspace.id, email=email, password_hash=password_hash, google_sub=google_sub, role="owner"
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        # Two sign-ups with the same email (or Google account) at the same moment: both pass the
        # caller's check, and the unique constraint on users.email / users.google_sub stops the second.
        # Any other integrity error is a bug, so it is re-raised, not disguised as "already registered".
        if isinstance(error.orig, UniqueViolation):
            raise EmailAlreadyRegistered from None
        raise
    session.refresh(user)
    return user


def register(session: Session, data: RegisterRequest) -> User:
    email = normalise_email(data.email)
    if session.exec(select(User).where(User.email == email)).first() is not None:
        raise EmailAlreadyRegistered
    return _create_workspace_and_owner(
        session,
        email=email,
        workspace_name=data.workspace_name,
        password_hash=hash_password(data.password),
        google_sub=None,
    )


# A real argon2 hash of a random string. Used when the email is unknown so that a failed login
# takes the same time either way; otherwise response time would reveal which emails have accounts.
_DUMMY_HASH = hash_password("reconcile-dummy-password")


def authenticate(session: Session, email: str, password: str) -> User | None:
    """The user if the email and password match, else None."""
    user = session.exec(select(User).where(User.email == normalise_email(email))).first()
    # A Google-only user has no password: treated exactly like an unknown email (same time, same answer).
    if user is None or user.password_hash is None:
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


# --- Google (D-37, D-38) ------------------------------------------------------------------------


def register_with_google(session: Session, identity: GoogleIdentity, workspace_name: str) -> User:
    """New workspace + owner from a verified Google identity. No password is set."""
    taken = session.exec(
        select(User).where((User.google_sub == identity.sub) | (User.email == identity.email))
    ).first()
    if taken is not None:
        raise EmailAlreadyRegistered
    return _create_workspace_and_owner(
        session, email=identity.email, workspace_name=workspace_name, password_hash=None, google_sub=identity.sub
    )


def login_with_google(session: Session, identity: GoogleIdentity) -> User:
    """The user for this Google account.

    1. Found by google_sub: the normal case. Not by email, because the email on a Google account can change.
    2. Otherwise, a user who registered with a password and the same email is linked to this Google
       account, but ONLY if Google owns that address (Gmail or Google Workspace). Otherwise anyone who
       could add a verified "ada@company.ng" to a personal Google account could take over Ada's account.
    """
    user = session.exec(select(User).where(User.google_sub == identity.sub)).first()
    if user is not None:
        return user

    if not identity.google_is_authoritative:
        raise NoAccountForGoogleUser
    # FOR UPDATE: two simultaneous first Google logins can't both decide to link.
    user = session.exec(select(User).where(User.email == identity.email).with_for_update()).first()
    # Already linked to a DIFFERENT Google account: never silently switch it.
    if user is None or user.google_sub is not None:
        raise NoAccountForGoogleUser

    user.google_sub = identity.sub
    # Password sign-up never proved who owns the inbox; Google just did. Someone could have registered
    # this address first, hoping the owner would later sign in with Google and land in their account
    # ("pre-account hijacking"). So the old password and every session made with it stop working.
    # The real owner can set a password again with forgot password, which emails this same inbox (D-46).
    had_password = user.password_hash is not None
    user.password_hash = None
    user.token_version += 1
    session.add(user)
    record(
        session,
        workspace_id=user.workspace_id,
        actor_user_id=user.id,
        action="user.google_linked",
        entity_type="user",
        entity_id=user.id,
        data={"password_removed": had_password},
    )
    try:
        session.commit()
    except IntegrityError as error:
        # This Google account was linked to another user in the meantime (unique google_sub).
        session.rollback()
        if isinstance(error.orig, UniqueViolation):
            raise NoAccountForGoogleUser from None
        raise
    session.refresh(user)
    return user


# --- forgot / reset password (D-39, D-40, D-41) -------------------------------------------------


def request_password_reset(session: Session, email: str) -> tuple[User, str] | None:
    """Create a single-use reset token. Returns (user, raw token) to email, or None for an unknown email.

    The router answers the same thing either way, so this result never reaches the caller.
    """
    user = session.exec(select(User).where(User.email == normalise_email(email))).first()
    if user is None:
        return None

    now = utc_now()
    # Stop anyone using this endpoint to flood a person's inbox: at most a few links per hour.
    # Counted from the table we already have, so no extra state is needed. Over the limit, nothing is
    # sent, and the caller still gets the usual answer (D-42).
    sent_last_hour = session.exec(
        select(func.count())
        .select_from(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.created_at > now - timedelta(hours=1))
    ).one()
    if sent_last_hour >= MAX_RESET_EMAILS_PER_HOUR:
        return None

    # Only the newest link works: any older unused one is marked used.
    session.exec(
        update(PasswordResetToken)
        .where(col(PasswordResetToken.user_id) == user.id, col(PasswordResetToken.used_at).is_(None))
        .values(used_at=now)
    )
    raw = new_reset_token()
    session.add(
        PasswordResetToken(
            workspace_id=user.workspace_id,
            user_id=user.id,
            token_hash=hash_reset_token(raw),
            expires_at=now + timedelta(minutes=settings.password_reset_minutes),
        )
    )
    # Actor is None: whoever asked hasn't proved they are this user yet.
    record(
        session,
        workspace_id=user.workspace_id,
        actor_user_id=None,
        action="user.password_reset_requested",
        entity_type="user",
        entity_id=user.id,
    )
    session.commit()
    return user, raw


def reset_link(raw_token: str) -> str:
    # The token goes in the fragment (after #). Browsers never send the fragment to any server, so it
    # can't end up in access logs or a Referer header (D-40). The reset page reads it with JavaScript.
    return f"{settings.frontend_url}/reset-password#token={raw_token}"


def send_password_reset_email(to: str, raw_token: str) -> None:
    """Run as a background task by the router."""
    minutes = settings.password_reset_minutes
    email_service.send_email(
        to=to,
        subject="Reset your Reconcile password",
        text=(
            "Someone asked to reset the password for your Reconcile account.\n\n"
            f"Choose a new password here (the link works once, for {minutes} minutes):\n"
            f"{reset_link(raw_token)}\n\n"
            "If it wasn't you, ignore this email; your password has not changed."
        ),
    )


def reset_password(session: Session, raw_token: str, new_password: str) -> User:
    """Set a new password from a valid reset token, and log out every existing session."""
    # FOR UPDATE: two requests with the same link can't both pass the "not used yet" check.
    token = session.exec(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == hash_reset_token(raw_token))
        .with_for_update()
    ).first()
    # One error for unknown, used and expired: the caller learns nothing about which it was.
    if token is None or token.used_at is not None or token.expires_at <= utc_now():
        raise InvalidResetToken

    user = session.get(User, token.user_id, with_for_update=True)
    if user is None:
        raise InvalidResetToken

    user.password_hash = hash_password(new_password)
    # Every login token issued before now carries the old version and is refused from now on.
    user.token_version += 1
    token.used_at = utc_now()
    session.add_all([user, token])
    record(
        session,
        workspace_id=user.workspace_id,
        actor_user_id=user.id,
        action="user.password_reset",
        entity_type="user",
        entity_id=user.id,
    )
    session.commit()
    session.refresh(user)
    return user


def logout_everywhere(session: Session, user: User) -> None:
    """Sign this user out on every device (D-67).

    A JWT can't be deleted on the server, so we bump token_version instead: every token issued so far
    carries the old version and get_current_user refuses it (D-41). One integer, no list of tokens. The
    cost: it also ends the user's sessions on their other devices, which is what you want if a token
    was stolen.
    """
    user.token_version += 1
    session.add(user)
    record(
        session,
        workspace_id=user.workspace_id,
        actor_user_id=user.id,
        action="user.logged_out",
        entity_type="user",
        entity_id=user.id,
    )
    session.commit()
