"""Registration and authentication — multi-tenant user management."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from echo.database import get_db
from echo.models.profile import EchoProfile
from echo.models.user import User

router = APIRouter()

# Monotonic UIN counter — in production, use a DB sequence
_UIN_SEQUENCE_SQL = "SELECT COALESCE(MAX(uin), 0) + 1 FROM users"


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-z0-9_-]+$")
    display_name: str = Field(..., min_length=1, max_length=256)
    email: str = Field(..., min_length=3, max_length=320)


class RegisterResponse(BaseModel):
    user_id: str
    username: str
    uin: int
    echo_address: str
    display_name: str


@router.post("/register", response_model=RegisterResponse)
async def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Create a new Echo account with UIN and ed25519 keypair."""
    # Check username uniqueness
    existing = db.query(User).filter(User.username == req.username).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Username '{req.username}' is taken")

    existing_email = db.query(User).filter(User.email == req.email).first()
    if existing_email:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Assign UIN (monotonic)
    from sqlalchemy import text
    result = db.execute(text(_UIN_SEQUENCE_SQL))
    uin = result.scalar() or 1

    # Generate ed25519 keypair
    private_key = Ed25519PrivateKey.generate()
    pubkey_bytes = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    privkey_bytes = private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())

    echo_address = f"echo://{uin}@myecho.me"

    user = User(
        username=req.username,
        display_name=req.display_name,
        email=req.email,
        uin=uin,
        echo_address=echo_address,
        pubkey=pubkey_bytes,
        privkey_encrypted=privkey_bytes,  # TODO: encrypt with server KEK in production
    )
    db.add(user)
    db.flush()

    # Create empty profile
    profile = EchoProfile(
        user_id=user.id,
        style_fingerprint={},
        belief_graph={},
        knowledge_map={},
        voice_prompt="",
    )
    db.add(profile)
    db.commit()

    return RegisterResponse(
        user_id=str(user.id),
        username=user.username,
        uin=uin,
        echo_address=echo_address,
        display_name=user.display_name,
    )


@router.get("/user/{username}")
async def get_user(username: str, db: Session = Depends(get_db)):
    """Look up a user by username."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user_id": str(user.id),
        "username": user.username,
        "display_name": user.display_name,
        "uin": user.uin,
        "echo_address": user.echo_address,
        "created_at": user.created_at,
    }
