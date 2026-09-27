"""Application settings loaded from environment variables / ``.env`` file."""

from pydantic import EmailStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application configuration.

    Every value can be overridden with an environment variable of the same
    name or with a line in the ``.env`` file. The defaults are safe
    placeholders for local development only; real secrets must be provided
    through ``.env`` (which is never committed).

    Attributes:
        DB_URL: SQLAlchemy async database URL.
        JWT_SECRET: Secret key used to sign JWT tokens.
        JWT_ALGORITHM: JWT signing algorithm.
        ACCESS_TOKEN_EXPIRE_MINUTES: Lifetime of an access token.
        REFRESH_TOKEN_EXPIRE_DAYS: Lifetime of a refresh token.
        EMAIL_TOKEN_EXPIRE_HOURS: Lifetime of an e-mail confirmation token.
        RESET_TOKEN_EXPIRE_MINUTES: Lifetime of a password reset token.
        REDIS_URL: Redis connection URL used for caching.
        USER_CACHE_TTL: How long (seconds) the current user stays in cache.
        MAIL_*: SMTP settings for ``fastapi-mail``.
        CLOUDINARY_*: Cloudinary credentials for avatar uploads.
        RATE_LIMIT_ENABLED: Enables ``slowapi`` rate limiting.
    """

    DB_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/contacts_app"

    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    EMAIL_TOKEN_EXPIRE_HOURS: int = 24
    RESET_TOKEN_EXPIRE_MINUTES: int = 30

    REDIS_URL: str = "redis://localhost:6379/0"
    USER_CACHE_TTL: int = 900

    MAIL_USERNAME: str = "user@example.com"
    MAIL_PASSWORD: str = "change-me"
    MAIL_FROM: EmailStr = "user@example.com"
    MAIL_PORT: int = 465
    MAIL_SERVER: str = "smtp.example.com"
    MAIL_FROM_NAME: str = "Contacts API"
    MAIL_STARTTLS: bool = False
    MAIL_SSL_TLS: bool = True
    USE_CREDENTIALS: bool = True
    VALIDATE_CERTS: bool = True

    CLOUDINARY_NAME: str = "change-me"
    CLOUDINARY_API_KEY: str = "change-me"
    CLOUDINARY_API_SECRET: str = "change-me"

    RATE_LIMIT_ENABLED: bool = True

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
