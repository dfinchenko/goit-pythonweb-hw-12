"""SQLAlchemy ORM models."""

import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base class for all models."""


class UserRole(str, enum.Enum):
    """Available user roles."""

    USER = "user"
    ADMIN = "admin"


class User(Base):
    """Application user.

    Attributes:
        id: Primary key.
        username: Unique login name.
        email: Unique e-mail address.
        hashed_password: bcrypt hash of the password.
        created_at: Registration timestamp.
        avatar: Avatar URL (Gravatar by default).
        confirmed: Whether the e-mail address has been confirmed.
        role: :class:`UserRole` of the user.
        refresh_token: The currently valid refresh token (``None`` after logout).
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    avatar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="userrole",
            values_callable=lambda roles: [r.value for r in roles],
        ),
        default=UserRole.USER,
        nullable=False,
    )
    refresh_token: Mapped[str | None] = mapped_column(String(512), nullable=True)

    contacts: Mapped[list["Contact"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Contact(Base):
    """Contact that belongs to a user.

    E-mail and phone must be unique inside one user's address book.
    """

    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("email", "user_id", name="uq_contact_email_user"),
        UniqueConstraint("phone", "user_id", name="uq_contact_phone_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    birthday: Mapped[date] = mapped_column(Date, nullable=False)
    additional_info: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    user: Mapped[User] = relationship(back_populates="contacts")
