"""
Auth Router — Registration, Login, and Google OAuth.

Endpoints:
  POST /api/auth/register  — create account with email/password
  POST /api/auth/login     — get JWT token
  POST /api/auth/google    — exchange Google ID token for JWT
  GET  /api/auth/me        — get current user (protected)
"""
import logging
import os
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.services.auth_service import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── Request/Response Schemas ─────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str

class LoginRequest(BaseModel):
    email: str
    password: str

class GoogleAuthRequest(BaseModel):
    id_token: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


# ── Endpoints ────────────────────────────────────

@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Create a new user with email and password."""
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = User(
        email=req.email,
        name=req.name,
        hashed_password=hash_password(req.password),
        auth_provider="local",
    )
    db.add(user)
    await db.flush()  # Populate user.id

    token = create_access_token(user.id, user.email)

    return AuthResponse(
        access_token=token,
        user={"id": user.id, "email": user.email, "name": user.name},
    )


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate with email and password, returns JWT."""
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(user.id, user.email)

    return AuthResponse(
        access_token=token,
        user={"id": user.id, "email": user.email, "name": user.name},
    )


@router.post("/google", response_model=AuthResponse)
async def google_auth(req: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    """
    Exchange a Google ID token for a JWT.
    Verifies the token with Google's tokeninfo endpoint,
    then creates or updates the user.
    """
    # Verify the Google ID token with Google.
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={req.id_token}"
            )
    except httpx.HTTPError:
        logger.exception("Google token verification request failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google authentication service unavailable",
        )

    if resp.status_code != 200:
        logger.warning("Google token verification rejected token: status=%s", resp.status_code)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
        )

    try:
        google_info = resp.json()
    except ValueError:
        logger.warning("Google token verification returned non-JSON payload")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
        )

    google_id = google_info.get("sub")
    email = google_info.get("email")
    name = google_info.get("name", email.split("@")[0] if email else "User")
    audience = google_info.get("aud")

    if not email or not google_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not get user info from Google",
        )

    expected_client_id = os.getenv("GOOGLE_CLIENT_ID") or os.getenv("VITE_GOOGLE_CLIENT_ID")
    if expected_client_id and audience != expected_client_id:
        logger.warning(
            "Google token audience mismatch: got=%s expected=%s",
            audience,
            expected_client_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token audience",
        )

    # Try to find existing user by google_id or email
    result = await db.execute(
        select(User).where((User.google_id == google_id) | (User.email == email))
    )
    user = result.scalar_one_or_none()

    if user:
        # Link Google ID if not already linked
        if not user.google_id:
            user.google_id = google_id
            user.auth_provider = "google"
    else:
        # Create new user
        user = User(
            email=email,
            name=name,
            auth_provider="google",
            google_id=google_id,
        )
        db.add(user)
        await db.flush()

    token = create_access_token(user.id, user.email)

    return AuthResponse(
        access_token=token,
        user={"id": user.id, "email": user.email, "name": user.name},
    )


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    """Get the currently authenticated user."""
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "auth_provider": user.auth_provider,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
