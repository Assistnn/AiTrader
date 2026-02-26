"""
Authentication API routes.

Reference: 08_API仕様 Section 3-1, 11_セキュリティ Section 2
"""

from __future__ import annotations

from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, status
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
)
from app.api.response import ok

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# --- Request/Response schemas ---


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    accessToken: str
    refreshToken: str
    expiresIn: int


class RefreshRequest(BaseModel):
    refreshToken: str


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
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate user and issue JWT tokens.

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

    return ok(LoginResponse(
        accessToken=access_token,
        refreshToken=refresh_token,
        expiresIn=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    ))


@router.post("/refresh")
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """
    Refresh access token using a valid refresh token.

    Reference: 08_API仕様 POST /api/v1/auth/refresh
    """
    payload = decode_token(body.refreshToken)
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
    Logout (client-side token discard).

    Reference: 08_API仕様 POST /api/v1/auth/logout
    """
    return {"status": "ok"}


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
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
