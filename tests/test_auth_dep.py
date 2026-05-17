"""Tests for echo/api/auth_dep.py — auth dependency."""
import importlib
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-do-not-use-in-prod")
    monkeypatch.setenv("MYECHO_ALLOWED_EMAILS", "good@example.com,pge-svc@hyperschool.internal")
    # Force Auth0 path off for these tests
    monkeypatch.setenv("AUTH0_DOMAIN", "")
    monkeypatch.setenv("AUTH0_AUDIENCE", "")
    # Module reads env at import time; reload to pick up monkeypatch.
    import echo.api.auth_dep
    importlib.reload(echo.api.auth_dep)
    yield


def _make_token(email: str, secret: str = "test-secret-do-not-use-in-prod") -> str:
    return jwt.encode({"email": email, "sub": "test-sub"}, secret, algorithm="HS256")


@pytest.mark.asyncio
async def test_hs256_allowed_email_returns_claims():
    from echo.api.auth_dep import get_authenticated_user as dep
    token = _make_token("good@example.com")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    claims = await dep(credentials=creds)
    assert claims["email"] == "good@example.com"


@pytest.mark.asyncio
async def test_hs256_disallowed_email_returns_403():
    from echo.api.auth_dep import get_authenticated_user as dep
    token = _make_token("bad@example.com")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc:
        await dep(credentials=creds)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_hs256_bad_signature_returns_401():
    from echo.api.auth_dep import get_authenticated_user as dep
    token = _make_token("good@example.com", secret="wrong-secret")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc:
        await dep(credentials=creds)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_missing_token_returns_401():
    from echo.api.auth_dep import get_authenticated_user as dep
    with pytest.raises(HTTPException) as exc:
        await dep(credentials=None)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_service_account_email_allowed():
    from echo.api.auth_dep import get_authenticated_user as dep
    token = _make_token("pge-svc@hyperschool.internal")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    claims = await dep(credentials=creds)
    assert claims["email"] == "pge-svc@hyperschool.internal"
