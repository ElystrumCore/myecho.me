"""Auth dependency for myecho.

Two issuers accepted:
1. Auth0 (RS256, verified via JWKS) — user logins from React dashboard
2. HS256 service tokens (signed with JWT_SECRET_KEY) — for PGE celery

Both must satisfy MYECHO_ALLOWED_EMAILS.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

logger = logging.getLogger(__name__)

_security = HTTPBearer(auto_error=False)

_AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "").strip()
_AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE", "").strip()
_JWT_SECRET = os.getenv("JWT_SECRET_KEY", "")
_ALLOWED = {
    e.strip().lower()
    for e in os.getenv("MYECHO_ALLOWED_EMAILS", "").split(",")
    if e.strip()
}

# Per-domain JWKS cache. Auth0 rotates signing keys rarely; refetching on
# cache miss is fine. Process-local — restart clears it.
_JWKS_CACHE: dict[str, dict] = {}

# Cooldown so a flood of malformed-kid tokens can't DoS the JWKS endpoint.
# When a kid is not in the cached JWKS we refresh once, then suppress further
# refreshes for this domain until the cooldown elapses.
_JWKS_REFRESH_COOLDOWN: dict[str, float] = {}
_JWKS_COOLDOWN_SECONDS = 60


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
    except JWTError as e:
        logger.debug("HS256 verify failed: %s", e)
        return None


async def _fetch_jwks(domain: str) -> dict:
    """Fetch + cache JWKS for the Auth0 domain."""
    if domain in _JWKS_CACHE:
        return _JWKS_CACHE[domain]
    url = f"https://{domain}/.well-known/jwks.json"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    jwks = resp.json()
    _JWKS_CACHE[domain] = jwks
    return jwks


async def _find_signing_key(domain: str, kid: str) -> Optional[dict]:
    """Find JWK matching kid. On miss, refresh JWKS once (cooldown-gated).

    Auth0 rotates signing keys (annually by default). Without a refresh, all
    requests signed with the new key 401 until the process restarts because
    the cached JWKS has no matching kid. We refresh on miss, but only once
    per _JWKS_COOLDOWN_SECONDS per domain so a flood of malformed-kid
    tokens can't be turned into a JWKS-endpoint DoS.
    """
    jwks = await _fetch_jwks(domain)
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key

    # Miss — possibly a key rotation. Refresh once if cooldown allows.
    now = time.time()
    last_refresh = _JWKS_REFRESH_COOLDOWN.get(domain, 0.0)
    if now - last_refresh < _JWKS_COOLDOWN_SECONDS:
        return None
    _JWKS_REFRESH_COOLDOWN[domain] = now
    _JWKS_CACHE.pop(domain, None)
    jwks = await _fetch_jwks(domain)
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    return None


async def _verify_auth0(token: str) -> Optional[dict]:
    """Verify Auth0 RS256 token via JWKS. Returns claims or None."""
    if not _AUTH0_DOMAIN or not _AUTH0_AUDIENCE:
        return None
    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if not kid:
            return None
        signing_key = await _find_signing_key(_AUTH0_DOMAIN, kid)
        if not signing_key:
            return None
        return jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=_AUTH0_AUDIENCE,
            issuer=f"https://{_AUTH0_DOMAIN}/",
        )
    except (JWTError, httpx.HTTPError) as e:
        logger.debug("Auth0 verify failed: %s", e)
        return None


def _extract_email(claims: dict) -> str:
    """Pull email from claims, supporting Auth0 namespaced claim format."""
    email = (
        claims.get("email")
        or claims.get("https://hyperschool.ca/email")
        or ""
    )
    if not isinstance(email, str):
        return ""
    return email.lower()


async def get_authenticated_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> dict:
    """FastAPI dependency. Returns verified claims dict.

    Raises:
        401 — missing token, invalid token, or token has no usable email claim
        403 — token has an email claim that's not in the allowlist
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = credentials.credentials
    claims = await _verify_auth0(token) or _verify_hs256(token)
    if not claims:
        raise HTTPException(status_code=401, detail="Invalid token")
    email = _extract_email(claims)
    if _ALLOWED:
        if not email:
            raise HTTPException(status_code=401, detail="Token missing email claim")
        if email not in _ALLOWED:
            logger.info("Rejected token with email %s", email)
            raise HTTPException(status_code=403, detail="Email not in allowlist")
    return claims
