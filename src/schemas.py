"""Pydantic request / response schemas."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.database.models import UserRole


class ContactBase(BaseModel):
    """Fields shared by contact create / update requests."""

    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    email: EmailStr = Field(max_length=150)
    phone: str = Field(min_length=5, max_length=20, pattern=r"^\+?[0-9 ()\-]+$")
    birthday: date
    additional_info: str | None = Field(default=None, max_length=500)


class ContactCreate(ContactBase):
    """Body for creating a contact."""


class ContactUpdate(BaseModel):
    """Body for a partial contact update — every field is optional."""

    first_name: str | None = Field(default=None, min_length=1, max_length=50)
    last_name: str | None = Field(default=None, min_length=1, max_length=50)
    email: EmailStr | None = Field(default=None, max_length=150)
    phone: str | None = Field(
        default=None, min_length=5, max_length=20, pattern=r"^\+?[0-9 ()\-]+$"
    )
    birthday: date | None = None
    additional_info: str | None = Field(default=None, max_length=500)


class ContactResponse(ContactBase):
    """Contact returned by the API."""

    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    """Registration body. The role is always ``user`` on sign-up."""

    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)


class UserResponse(BaseModel):
    """Public user representation."""

    id: int
    username: str
    email: EmailStr
    avatar: str | None = None
    role: UserRole
    confirmed: bool

    model_config = ConfigDict(from_attributes=True)


class RoleUpdate(BaseModel):
    """Body for changing a user's role (admin only)."""

    role: UserRole


class TokenPair(BaseModel):
    """Access + refresh token pair returned on login / refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Body with a refresh token."""

    refresh_token: str


class RequestEmail(BaseModel):
    """Body with an e-mail address (confirmation resend / password reset)."""

    email: EmailStr


class ResetPasswordConfirm(BaseModel):
    """Body for setting a new password using a reset token."""

    token: str
    new_password: str = Field(min_length=6, max_length=72)


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str
