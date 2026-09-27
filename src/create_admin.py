"""CLI: create an admin or promote an existing user to admin.

Usage::

    python -m src.create_admin <username> <email> <password>

If a user with this username already exists, it is promoted to ``admin``
(and confirmed); otherwise a new confirmed admin is created.
"""

import asyncio
import sys

from src.database.db import sessionmanager
from src.database.models import UserRole
from src.repository.users import UserRepository
from src.schemas import UserCreate
from src.services.auth import Hash


async def create_admin(username: str, email: str, password: str, session) -> str:
    """Create or promote an admin user.

    Returns:
        str: ``"created"`` or ``"promoted"``.
    """
    repo = UserRepository(session)
    user = await repo.get_user_by_username(username)
    if user is not None:
        await repo.update_role(user, UserRole.ADMIN)
        await repo.confirm_email(user)
        return "promoted"
    body = UserCreate(username=username, email=email, password=password)
    user = await repo.create_user(
        body, Hash.get_password_hash(password), role=UserRole.ADMIN
    )
    await repo.confirm_email(user)
    return "created"


async def _main(args: list[str]) -> None:  # pragma: no cover
    async with sessionmanager.session() as session:
        print(f"Admin {args[0]}: {await create_admin(*args, session=session)}")


if __name__ == "__main__":  # pragma: no cover
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    asyncio.run(_main(sys.argv[1:]))
