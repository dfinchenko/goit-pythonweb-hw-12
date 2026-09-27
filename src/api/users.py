"""Current user profile, avatar and role management."""

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.conf.config import settings
from src.database.db import get_db
from src.database.models import User
from src.schemas import RoleUpdate, UserResponse
from src.services.auth import get_current_admin, get_current_user
from src.services.limiter import limiter
from src.services.upload_file import UploadFileService
from src.services.users import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me", response_model=UserResponse, description="No more than 10 requests per minute"
)
@limiter.limit("10/minute")
async def me(request: Request, user: User = Depends(get_current_user)):
    """Return the current user (served from the Redis cache)."""
    return user


@router.patch("/avatar", response_model=UserResponse)
async def update_avatar(
    file: UploadFile = File(),
    user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Upload a new avatar. Only admins may replace their default avatar.

    Raises:
        HTTPException: 403 for non-admin users.
    """
    avatar_url = UploadFileService(
        settings.CLOUDINARY_NAME,
        settings.CLOUDINARY_API_KEY,
        settings.CLOUDINARY_API_SECRET,
    ).upload_file(file, user.username)
    return await UserService(db).update_avatar(user.id, avatar_url)


@router.patch("/{user_id}/role", response_model=UserResponse)
async def change_role(
    user_id: int,
    body: RoleUpdate,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Change another user's role (admin only).

    Raises:
        HTTPException: 404 if the user does not exist, 400 when an admin tries
            to change their own role.
    """
    if user_id == admin.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="You cannot change your own role"
        )
    service = UserService(db)
    user = await service.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    return await service.change_role(user, body.role)
