"""Authentication endpoints: sign-up, login, token refresh, e-mail
confirmation and password reset."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.db import get_db
from src.schemas import (
    MessageResponse,
    RefreshTokenRequest,
    RequestEmail,
    ResetPasswordConfirm,
    TokenPair,
    UserCreate,
    UserResponse,
)
from src.services.auth import (
    EMAIL_VERIFY,
    PASSWORD_RESET,
    REFRESH,
    Hash,
    create_access_token,
    create_refresh_token,
    create_reset_token,
    decode_token,
    password_fingerprint,
)
from src.services.email import send_confirm_email, send_reset_password_email
from src.services.users import UserService

router = APIRouter(prefix="/auth", tags=["auth"])

RESET_EMAIL_SENT = "If this e-mail is registered, a password reset link has been sent"


async def _issue_tokens(service: UserService, user) -> dict:
    access_token = create_access_token(user.username)
    refresh_token = create_refresh_token(user.username)
    await service.set_refresh_token(user, refresh_token)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    body: UserCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user (role ``user``) and send a confirmation e-mail.

    Raises:
        HTTPException: 409 if the e-mail or username is taken.
    """
    service = UserService(db)
    if await service.get_user_by_email(body.email):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered")
    if await service.get_user_by_username(body.username):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Username already taken")
    user = await service.create_user(body)
    background_tasks.add_task(
        send_confirm_email, user.email, user.username, str(request.base_url)
    )
    return user


@router.post("/login", response_model=TokenPair)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Log in with username and password and receive an access/refresh token pair.

    Raises:
        HTTPException: 401 on wrong credentials or unconfirmed e-mail.
    """
    service = UserService(db)
    user = await service.get_user_by_username(form_data.username)
    if user is None or not Hash.verify_password(
        form_data.password, user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.confirmed:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Email not confirmed")
    return await _issue_tokens(service, user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """Exchange a valid refresh token for a new token pair (rotation).

    The used refresh token is revoked, so each one works only once.

    Raises:
        HTTPException: 401 if the token is invalid, expired or revoked.
    """
    username = decode_token(body.refresh_token, REFRESH)["sub"]
    service = UserService(db)
    user = await service.get_user_by_username(username)
    if user is None or user.refresh_token != body.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await _issue_tokens(service, user)


@router.post("/logout", response_model=MessageResponse)
async def logout(body: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """Revoke the refresh token."""
    username = decode_token(body.refresh_token, REFRESH)["sub"]
    service = UserService(db)
    user = await service.get_user_by_username(username)
    if user is not None and user.refresh_token == body.refresh_token:
        await service.set_refresh_token(user, None)
    return {"message": "Logged out"}


@router.get("/confirmed_email/{token}", response_model=MessageResponse)
async def confirmed_email(token: str, db: AsyncSession = Depends(get_db)):
    """Confirm the e-mail address using the link from the letter.

    Raises:
        HTTPException: 401 for an invalid token, 400 if the user does not exist.
    """
    email = decode_token(token, EMAIL_VERIFY)["sub"]
    service = UserService(db)
    user = await service.get_user_by_email(email)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Verification error")
    if user.confirmed:
        return {"message": "Email already confirmed"}
    await service.confirm_email(user)
    return {"message": "Email confirmed"}


@router.post("/request_email", response_model=MessageResponse)
async def request_email(
    body: RequestEmail,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Re-send the confirmation e-mail."""
    user = await UserService(db).get_user_by_email(body.email)
    if user and user.confirmed:
        return {"message": "Email already confirmed"}
    if user:
        background_tasks.add_task(
            send_confirm_email, user.email, user.username, str(request.base_url)
        )
    return {"message": "Check your email for confirmation"}


@router.post("/forgot_password", response_model=MessageResponse)
async def forgot_password(
    body: RequestEmail,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Start a password reset: e-mail a one-time reset link.

    The response is the same whether the e-mail exists or not, so the endpoint
    cannot be used to discover registered addresses.
    """
    user = await UserService(db).get_user_by_email(body.email)
    if user is not None:
        background_tasks.add_task(
            send_reset_password_email,
            user.email,
            user.username,
            str(request.base_url),
            create_reset_token(user),
        )
    return {"message": RESET_EMAIL_SENT}


@router.get("/reset_password/{token}", response_class=HTMLResponse)
async def reset_password_form(token: str):
    """Minimal HTML page (opened from the e-mail) for entering a new password."""
    decode_token(token, PASSWORD_RESET)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Reset password</title></head>
<body style="font-family:Arial,sans-serif;max-width:360px;margin:40px auto">
<h2>Set a new password</h2>
<input id="pwd" type="password" minlength="6" maxlength="72" placeholder="New password"
 style="width:100%;padding:8px">
<button id="btn" style="margin-top:12px;padding:8px 16px">Save</button>
<p id="msg"></p>
<script>
document.getElementById('btn').onclick = async () => {{
  const r = await fetch('/api/auth/reset_password', {{
    method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{token: '{token}', new_password: document.getElementById('pwd').value}})
  }});
  const d = await r.json();
  document.getElementById('msg').textContent = d.message || JSON.stringify(d.detail);
}};
</script></body></html>"""


@router.post("/reset_password", response_model=MessageResponse)
async def reset_password(body: ResetPasswordConfirm, db: AsyncSession = Depends(get_db)):
    """Set a new password using the token from the reset e-mail.

    The token is valid for ``RESET_TOKEN_EXPIRE_MINUTES`` and only once: it
    carries a fingerprint of the old password hash, which no longer matches
    after the password changes. Existing refresh tokens are revoked.

    Raises:
        HTTPException: 400 if the token is invalid, expired or already used.
    """
    invalid = HTTPException(
        status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token"
    )
    try:
        payload = decode_token(body.token, PASSWORD_RESET)
    except HTTPException:
        raise invalid
    service = UserService(db)
    user = await service.get_user_by_email(payload["sub"])
    if user is None or payload.get("pwd") != password_fingerprint(
        user.hashed_password
    ):
        raise invalid
    await service.reset_password(user, body.new_password)
    return {"message": "Password has been reset"}
