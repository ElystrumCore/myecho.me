"""Auth dependency for myecho.

Two issuers accepted:
1. Auth0 (RS256, verified via JWKS) — user logins from React dashboard
   (stub here; real implementation in Deploy-T3)
2. HS256 service tokens (signed with JWT_SECRET_KEY) — for PGE celery

Both must satisfy MYECHO_ALLOWED_EMAILS.
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

_security = HTTPBearer(auto_error=False)

_AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "").strip()
_AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE", "").strip()
_JWT_SECRET = os.getenv("JWT_SECRET_KEY", "")
_ALLOWED = {
    e.strip().lower()
    for e in os.getenv("MYECHO_ALLOWED_EMAILS", "").split(",")
    if e.strip()
}


def _verify_hs256(token: str) -> Optional[dict]:
    """Verify HS256 token signed with JWT_SECRET_KEY. Returns claims or None."""
    if not _JWT_SECRET:
        return None
    try:
        return jwt.decode(
            token,
            _JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except JWTError:
        return None


async def _verify_auth0(token: str) -> Optional[dict]:
    """Verify Auth0 RS256 token via JWKS. Returns claims or None.

    Stub for Deploy-T2; real implementation lands in Deploy-T3.
    """
    return None


def _extract_email(claims: dict) -> str:
    """Pull email from claims, supporting Auth0 namespaced claim format."""
    email = (
        claims.get("email")
        or claims.get("https://hyperschool.ca/email")
        or ""
    )
    return email.lower()


async def get_authenticated_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> dict:
    """FastAPI dependency. Returns verified claims dict.

    Raises 401 on missing/invalid token, 403 if email not in allowlist.
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = credentials.credentials
    claims = await _verify_auth0(token) or _verify_hs256(token)
    if not claims:
        raise HTTPException(status_code=401, detail="Invalid token")
    email = _extract_email(claims)
    if _ALLOWED and email not in _ALLOWED:
        raise HTTPException(status_code=403, detail=f"Email not allowed: {email}")
    return claims
