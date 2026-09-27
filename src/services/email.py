"""Sending e-mails (address confirmation and password reset)."""

import logging
from pathlib import Path

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from fastapi_mail.errors import ConnectionErrors

from src.conf.config import settings
from src.services.auth import create_email_token

logger = logging.getLogger(__name__)

conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
    MAIL_STARTTLS=settings.MAIL_STARTTLS,
    MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
    USE_CREDENTIALS=settings.USE_CREDENTIALS,
    VALIDATE_CERTS=settings.VALIDATE_CERTS,
    TEMPLATE_FOLDER=Path(__file__).parent / "templates",
)


async def _send(subject: str, email: str, body: dict, template: str) -> None:
    message = MessageSchema(
        subject=subject,
        recipients=[email],
        template_body=body,
        subtype=MessageType.html,
    )
    try:
        await FastMail(conf).send_message(message, template_name=template)
    except ConnectionErrors as err:
        logger.error("Failed to send e-mail to %s: %s", email, err)


async def send_confirm_email(email: str, username: str, host: str) -> None:
    """Send a message with an e-mail confirmation link.

    Args:
        email: Recipient address.
        username: Recipient's username.
        host: Base URL of the API (``request.base_url``).
    """
    await _send(
        "Confirm your email",
        email,
        {"host": str(host), "username": username, "token": create_email_token(email)},
        "verify_email.html",
    )


async def send_reset_password_email(
    email: str, username: str, host: str, token: str
) -> None:
    """Send a message with a password reset link.

    Args:
        email: Recipient address.
        username: Recipient's username.
        host: Base URL of the API (``request.base_url``).
        token: One-time password reset token.
    """
    await _send(
        "Password reset",
        email,
        {"host": str(host), "username": username, "token": token},
        "reset_password.html",
    )
