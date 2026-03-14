"""
Authentication API routes.

Reference: 08_API仕様 Section 3-1, 11_セキュリティ Section 2, 8, 9
"""

from __future__ import annotations

from pydantic import BaseModel

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.services.auth.password import hash_password, verify_password, validate_password_strength
from app.services.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    decode_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from app.api.response import ok

from app.config import settings

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "refresh_token"
# Secure flag: only True when HTTPS is available
_COOKIE_SECURE = settings.COOKIE_SECURE
REFRESH_COOKIE_MAX_AGE = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60  # seconds


def _set_refresh_cookie(response: Response, token: str) -> None:
    """Set refresh token as HttpOnly cookie. Reference: 11_セキュリティ §2-1"""
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="lax",
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Clear refresh token cookie on logout."""
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="lax",
        path="/api/v1/auth",
    )


# --- Request/Response schemas ---


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    accessToken: str
    expiresIn: int


class RefreshRequest(BaseModel):
    refreshToken: str | None = None


class RefreshResponse(BaseModel):
    accessToken: str
    expiresIn: int


class RegisterRequest(BaseModel):
    email: str
    password: str
    displayName: str | None = None


class RegisterResponse(BaseModel):
    userId: int
    email: str


# --- Endpoints ---


@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate user and issue JWT tokens.
    refreshToken is set as HttpOnly cookie (11_セキュリティ §2-1).

    Reference: 08_API仕様 POST /api/v1/auth/login
    """
    result = await db.execute(
        select(User).where(User.email == body.email, User.is_active == True)
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    response_data = ok(LoginResponse(
        accessToken=access_token,
        expiresIn=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    ))

    response = Response(
        content=__import__("json").dumps(response_data),
        media_type="application/json",
    )
    _set_refresh_cookie(response, refresh_token)
    return response


@router.post("/refresh")
@limiter.limit("10/minute")
async def refresh(
    request: Request,
    body: RefreshRequest | None = None,
    refresh_token: str | None = Cookie(None, alias=REFRESH_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh access token using refresh token from HttpOnly cookie or request body (legacy).

    Reference: 08_API仕様 POST /api/v1/auth/refresh, 11_セキュリティ §2-1
    """
    # Prefer cookie, fall back to body for backward compatibility
    token = refresh_token or (body.refreshToken if body else None)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided",
        )

    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = int(payload["sub"])
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    access_token = create_access_token(user.id)

    return ok(RefreshResponse(
        accessToken=access_token,
        expiresIn=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    ))


@router.post("/logout")
async def logout():
    """
    Logout: clear refresh token cookie.

    Reference: 08_API仕様 POST /api/v1/auth/logout, 11_セキュリティ §2-1
    """
    response = Response(
        content=__import__("json").dumps({"status": "ok"}),
        media_type="application/json",
    )
    _clear_refresh_cookie(response)
    return response


@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("3/hour")
async def register(request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Register a new user account.
    """
    is_valid, error_msg = validate_password_strength(body.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )

    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.displayName,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    return ok(RegisterResponse(userId=user.id, email=user.email))
