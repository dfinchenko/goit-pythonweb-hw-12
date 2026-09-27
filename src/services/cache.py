"""Redis cache for the authenticated user.

``get_current_user`` reads the user from here first, so an authenticated
request normally does not touch the database. Only non-sensitive fields are
cached (never the password hash or refresh token), entries expire after
``USER_CACHE_TTL`` seconds, and every change of the user (avatar, password,
role, e-mail confirmation, logout) invalidates the entry. If Redis is
unavailable the application falls back to the database.
"""

import json
import logging
from datetime import datetime

from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.conf.config import settings
from src.database.models import User, UserRole

logger = logging.getLogger(__name__)

_redis: Redis | None = None


def get_redis() -> Redis:
    """Return a lazily created shared Redis client."""
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


def set_redis(client: Redis | None) -> None:
    """Replace the Redis client (used by tests)."""
    global _redis
    _redis = client


def _key(username: str) -> str:
    return f"user:{username}"


def serialize_user(user: User) -> str:
    """Serialize the public fields of a user to JSON."""
    return json.dumps(
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "avatar": user.avatar,
            "confirmed": user.confirmed,
            "role": UserRole(user.role).value,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
    )


def deserialize_user(raw: str) -> User:
    """Build a detached :class:`User` from cached JSON."""
    data = json.loads(raw)
    data["role"] = UserRole(data["role"])
    if data.get("created_at"):
        data["created_at"] = datetime.fromisoformat(data["created_at"])
    return User(**data)


async def get_cached_user(username: str) -> User | None:
    """Return the cached user or ``None`` on a miss / Redis error."""
    try:
        raw = await get_redis().get(_key(username))
    except RedisError as exc:
        logger.warning("Redis unavailable, cache read skipped: %s", exc)
        return None
    return deserialize_user(raw) if raw else None


async def cache_user(user: User) -> None:
    """Put the user into the cache with ``USER_CACHE_TTL``."""
    try:
        await get_redis().set(
            _key(user.username), serialize_user(user), ex=settings.USER_CACHE_TTL
        )
    except RedisError as exc:
        logger.warning("Redis unavailable, cache write skipped: %s", exc)


async def invalidate_user(username: str) -> None:
    """Remove the user from the cache so fresh data is loaded next time."""
    try:
        await get_redis().delete(_key(username))
    except RedisError as exc:
        logger.warning("Redis unavailable, cache invalidation skipped: %s", exc)
