"""Data access layer for users."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import User, UserRole
from src.schemas import UserCreate


class UserRepository:
    """CRUD operations for :class:`~src.database.models.User`.

    Args:
        session: An open async database session.
    """

    def __init__(self, session: AsyncSession):
        self.db = session

    async def get_user_by_id(self, user_id: int) -> User | None:
        """Return a user by id, or ``None``."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> User | None:
        """Return a user by username, or ``None``."""
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> User | None:
        """Return a user by e-mail, or ``None``."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create_user(
        self,
        body: UserCreate,
        hashed_password: str,
        avatar: str | None = None,
        role: UserRole = UserRole.USER,
    ) -> User:
        """Create a new user.

        Args:
            body: Registration data (the plain password is ignored).
            hashed_password: bcrypt hash of the password.
            avatar: Optional avatar URL.
            role: Role of the new user, ``user`` by default.

        Returns:
            User: The created user.
        """
        user = User(
            username=body.username,
            email=body.email,
            hashed_password=hashed_password,
            avatar=avatar,
            role=role,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def _save(self, user: User) -> User:
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def confirm_email(self, user: User) -> User:
        """Mark the user's e-mail as confirmed."""
        user.confirmed = True
        return await self._save(user)

    async def update_avatar(self, user: User, url: str) -> User:
        """Set a new avatar URL for the user."""
        user.avatar = url
        return await self._save(user)

    async def update_password(self, user: User, hashed_password: str) -> User:
        """Replace the password hash and revoke the refresh token."""
        user.hashed_password = hashed_password
        user.refresh_token = None
        return await self._save(user)

    async def update_refresh_token(self, user: User, token: str | None) -> User:
        """Store (or clear with ``None``) the user's refresh token."""
        user.refresh_token = token
        return await self._save(user)

    async def update_role(self, user: User, role: UserRole) -> User:
        """Change the user's role."""
        user.role = role
        return await self._save(user)
