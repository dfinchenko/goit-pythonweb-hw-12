"""Password hashing, JWT tokens and authentication dependencies."""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.conf.config import settings
from src.database.db import get_db
from src.database.models import User, UserRole
from src.repository.users import UserRepository
from src.services.cache import cache_user, get_cached_user

ACCESS = "access"
REFRESH = "refresh"
EMAIL_VERIFY = "email_verify"
PASSWORD_RESET = "password_reset"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class Hash:
    """bcrypt password hashing helper."""

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash a plain password with a random salt."""
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Check a plain password against a bcrypt hash."""
        try:
            return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
        except ValueError:
            return False


def _create_token(subject: str, token_type: str, expires: timedelta, **extra) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires,
        "jti": uuid.uuid4().hex,
    }
    payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(username: str) -> str:
    """Create a short-lived access token for ``username``."""
    return _create_token(
        username, ACCESS, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )


def create_refresh_token(username: str) -> str:
    """Create a long-lived refresh token for ``username``."""
    return _create_token(
        username, REFRESH, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )


def create_email_token(email: str) -> str:
    """Create a token that confirms ownership of ``email``."""
    return _create_token(
        email, EMAIL_VERIFY, timedelta(hours=settings.EMAIL_TOKEN_EXPIRE_HOURS)
    )


def password_fingerprint(hashed_password: str) -> str:
    """Short digest of the current password hash.

    Embedded in reset tokens so that a token stops working as soon as the
    password is changed (one-time use).
    """
    return hashlib.sha256(hashed_password.encode()).hexdigest()[:16]


def create_reset_token(user: User) -> str:
    """Create a one-time password reset token for ``user``."""
    return _create_token(
        user.email,
        PASSWORD_RESET,
        timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES),
        pwd=password_fingerprint(user.hashed_password),
    )


def decode_token(token: str, expected_type: str) -> dict:
    """Decode and validate a JWT of a given type.

    Args:
        token: Encoded JWT.
        expected_type: Required value of the ``type`` claim.

    Returns:
        dict: The token payload.

    Raises:
        HTTPException: 401 if the token is invalid, expired or of another type.
    """
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.PyJWTError:
        payload = None
    if not payload or payload.get("type") != expected_type or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User:
    """Return the user authenticated by the bearer access token.

    The user is taken from the Redis cache; the database is queried only on a
    cache miss, after which the user is cached.

    Raises:
        HTTPException: 401 if the token is invalid or the user does not exist.
    """
    username = decode_token(token, ACCESS)["sub"]
    user = await get_cached_user(username)
    if user is None:
        user = await UserRepository(db).get_user_by_username(username)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        await cache_user(user)
    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """Allow the request only for users with the ``admin`` role.

    Raises:
        HTTPException: 403 for non-admin users.
    """
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )
    return user
