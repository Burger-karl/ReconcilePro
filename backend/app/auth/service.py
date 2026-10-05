"""Registration and login logic. Routes call these; no HTTP here."""

from psycopg.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.auth.models import User, Workspace
from app.auth.schemas import RegisterRequest
from app.core.security import hash_password, verify_password


class EmailAlreadyRegistered(Exception):
    pass


def normalise_email(email: str) -> str:
    return email.strip().lower()


def register(session: Session, data: RegisterRequest) -> User:
    """Create a workspace and its owner in ONE transaction.

    If anything fails (e.g. the email is taken), nothing is committed, so we never leave
    a workspace with no owner behind.
    """
    email = normalise_email(data.email)
    if session.exec(select(User).where(User.email == email)).first() is not None:
        raise EmailAlreadyRegistered

    workspace = Workspace(name=data.workspace_name)
    session.add(workspace)
    # Flush = send the INSERT now, inside the still-open transaction. Without it SQLAlchemy may insert
    # the user first (we declare no relationship() for it to order by) and the foreign key fails.
    session.flush()

    user = User(workspace_id=workspace.id, email=email, password_hash=hash_password(data.password), role="owner")
    session.add(user)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        # Two sign-ups with the same email at the same moment: both pass the check above, and the
        # unique constraint on users.email (the only unique one on the table) stops the second here.
        # Any other integrity error is a bug, so it is re-raised, not disguised as "email taken".
        if isinstance(error.orig, UniqueViolation):
            raise EmailAlreadyRegistered from None
        raise
    session.refresh(user)
    return user


# A real argon2 hash of a random string. Used when the email is unknown so that a failed login
# takes the same time either way; otherwise response time would reveal which emails have accounts.
_DUMMY_HASH = hash_password("reconcile-dummy-password")


def authenticate(session: Session, email: str, password: str) -> User | None:
    """The user if the email and password match, else None."""
    user = session.exec(select(User).where(User.email == normalise_email(email))).first()
    if user is None:
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
