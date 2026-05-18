"""Tests for echo/api/auth_dep.py — auth dependency."""
import importlib
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt
from unittest.mock import patch, AsyncMock


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


@pytest.mark.asyncio
async def test_auth0_path_called_when_domain_set(monkeypatch):
    monkeypatch.setenv("AUTH0_DOMAIN", "hyperschool.us.auth0.com")
    monkeypatch.setenv("AUTH0_AUDIENCE", "https://api.hyperschool.ca")
    import echo.api.auth_dep
    importlib.reload(echo.api.auth_dep)
    from echo.api.auth_dep import get_authenticated_user as dep

    fake_claims = {"email": "good@example.com", "sub": "auth0|123"}
    with patch(
        "echo.api.auth_dep._verify_auth0",
        new=AsyncMock(return_value=fake_claims),
    ):
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="any-token")
        claims = await dep(credentials=creds)
        assert claims["sub"] == "auth0|123"


@pytest.mark.asyncio
async def test_auth0_namespaced_email_claim_extracted(monkeypatch):
    monkeypatch.setenv("AUTH0_DOMAIN", "hyperschool.us.auth0.com")
    monkeypatch.setenv("AUTH0_AUDIENCE", "https://api.hyperschool.ca")
    import echo.api.auth_dep
    importlib.reload(echo.api.auth_dep)
    from echo.api.auth_dep import get_authenticated_user as dep

    fake_claims = {"https://hyperschool.ca/email": "good@example.com", "sub": "auth0|123"}
    with patch(
        "echo.api.auth_dep._verify_auth0",
        new=AsyncMock(return_value=fake_claims),
    ):
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="any-token")
        claims = await dep(credentials=creds)
        assert claims["sub"] == "auth0|123"


@pytest.mark.asyncio
async def test_token_without_email_returns_401():
    """Valid HS256 token with no email claim → 401 (not 403)."""
    from echo.api.auth_dep import get_authenticated_user as dep
    token = jwt.encode({"sub": "no-email-user"}, "test-secret-do-not-use-in-prod", algorithm="HS256")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc:
        await dep(credentials=creds)
    assert exc.value.status_code == 401
    assert "email" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_403_detail_does_not_leak_email():
    """Rejected emails should not appear in the response body."""
    from echo.api.auth_dep import get_authenticated_user as dep
    token = _make_token("attacker@evil.example")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc:
        await dep(credentials=creds)
    assert exc.value.status_code == 403
    assert "attacker@evil.example" not in exc.value.detail


@pytest.mark.asyncio
async def test_empty_allowlist_permits_any_valid_token(monkeypatch):
    """If MYECHO_ALLOWED_EMAILS is empty, any valid token passes (dev mode)."""
    monkeypatch.setenv("MYECHO_ALLOWED_EMAILS", "")
    import echo.api.auth_dep
    importlib.reload(echo.api.auth_dep)
    from echo.api.auth_dep import get_authenticated_user as dep
    token = _make_token("anybody@example.com")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    claims = await dep(credentials=creds)
    assert claims["email"] == "anybody@example.com"


@pytest.mark.asyncio
async def test_expired_token_returns_401():
    """Expired HS256 token → 401."""
    import time
    from echo.api.auth_dep import get_authenticated_user as dep
    payload = {"email": "good@example.com", "exp": int(time.time()) - 60}
    token = jwt.encode(payload, "test-secret-do-not-use-in-prod", algorithm="HS256")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc:
        await dep(credentials=creds)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_non_string_email_claim_treated_as_missing():
    """Token where email claim is a non-string (None, dict) → 401, not 500."""
    from echo.api.auth_dep import get_authenticated_user as dep
    token = jwt.encode({"email": None, "sub": "weird"}, "test-secret-do-not-use-in-prod", algorithm="HS256")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc:
        await dep(credentials=creds)
    # Should be 401 (token unusable: no valid email claim), not 500 (crash)
    assert exc.value.status_code == 401


# ----------------------------------------------------------------------------
# JWKS kid-miss refresh on Auth0 key rotation (follow-up #51)
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_jwks_refresh_on_kid_miss(monkeypatch):
    """When the cached JWKS doesn't contain the kid, refresh once and retry.

    Simulates Auth0 key rotation: cache has key A, token signed with key B.
    The first httpx fetch returns {keys:[A]} (stale), the second returns
    {keys:[A,B]} (post-rotation). _find_signing_key should hit the miss
    path, pop the cache, refresh, and return B.
    """
    import echo.api.auth_dep as ad
    importlib.reload(ad)
    ad._JWKS_CACHE.clear()
    ad._JWKS_REFRESH_COOLDOWN.clear()

    domain = "test.auth0.com"
    key_a = {"kid": "key-a", "kty": "RSA"}
    key_b = {"kid": "key-b", "kty": "RSA"}

    # Fake httpx so we count *network* calls, not cache reads. _fetch_jwks
    # honors _JWKS_CACHE itself, so this is the real cache + real fetch flow.
    fetch_calls = {"n": 0}

    class _FakeResponse:
        def __init__(self, payload):
            self._payload = payload
        def raise_for_status(self):
            return None
        def json(self):
            return self._payload

    class _FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None
        async def get(self, url):
            fetch_calls["n"] += 1
            if fetch_calls["n"] == 1:
                return _FakeResponse({"keys": [key_a]})
            return _FakeResponse({"keys": [key_a, key_b]})

    monkeypatch.setattr(ad.httpx, "AsyncClient", _FakeClient)

    found = await ad._find_signing_key(domain, "key-b")
    assert found == key_b
    assert fetch_calls["n"] == 2  # 1 stale fetch + 1 refresh


@pytest.mark.asyncio
async def test_jwks_no_refresh_when_kid_already_present(monkeypatch):
    """Cache hit should NOT trigger a refresh."""
    import echo.api.auth_dep as ad
    importlib.reload(ad)
    ad._JWKS_CACHE.clear()
    ad._JWKS_REFRESH_COOLDOWN.clear()

    domain = "test.auth0.com"
    key_a = {"kid": "key-a", "kty": "RSA"}
    fetch_calls = {"n": 0}

    class _FakeResponse:
        def raise_for_status(self): return None
        def json(self): return {"keys": [key_a]}

    class _FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None
        async def get(self, url):
            fetch_calls["n"] += 1
            return _FakeResponse()

    monkeypatch.setattr(ad.httpx, "AsyncClient", _FakeClient)

    found = await ad._find_signing_key(domain, "key-a")
    assert found == key_a
    assert fetch_calls["n"] == 1  # first call only; cache served the lookup


@pytest.mark.asyncio
async def test_jwks_cooldown_blocks_repeat_refresh(monkeypatch):
    """Within cooldown, a second kid-miss must NOT trigger another network fetch.

    Protects the JWKS endpoint from being hammered by malformed-kid tokens.
    """
    import echo.api.auth_dep as ad
    importlib.reload(ad)
    ad._JWKS_CACHE.clear()
    ad._JWKS_REFRESH_COOLDOWN.clear()

    domain = "test.auth0.com"
    key_a = {"kid": "key-a", "kty": "RSA"}
    fetch_calls = {"n": 0}

    class _FakeResponse:
        def raise_for_status(self): return None
        def json(self): return {"keys": [key_a]}

    class _FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None
        async def get(self, url):
            fetch_calls["n"] += 1
            return _FakeResponse()

    monkeypatch.setattr(ad.httpx, "AsyncClient", _FakeClient)

    # First miss → 1 stale fetch + 1 refresh = 2 network calls.
    first = await ad._find_signing_key(domain, "key-missing")
    assert first is None
    assert fetch_calls["n"] == 2

    # Second miss within cooldown → cache serves the first read, cooldown
    # blocks the refresh → still 2 network calls.
    second = await ad._find_signing_key(domain, "key-also-missing")
    assert second is None
    assert fetch_calls["n"] == 2


@pytest.mark.asyncio
async def test_jwks_cooldown_expires_allows_refresh(monkeypatch):
    """After cooldown elapses, a kid-miss should refresh again."""
    import echo.api.auth_dep as ad
    importlib.reload(ad)
    ad._JWKS_CACHE.clear()
    ad._JWKS_REFRESH_COOLDOWN.clear()

    domain = "test.auth0.com"
    key_a = {"kid": "key-a", "kty": "RSA"}
    fetch_calls = {"n": 0}

    class _FakeResponse:
        def raise_for_status(self): return None
        def json(self): return {"keys": [key_a]}

    class _FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None
        async def get(self, url):
            fetch_calls["n"] += 1
            return _FakeResponse()

    monkeypatch.setattr(ad.httpx, "AsyncClient", _FakeClient)

    # Fake clock so we can jump past the cooldown.
    fake_now = {"t": 1_000_000.0}
    monkeypatch.setattr(ad.time, "time", lambda: fake_now["t"])

    await ad._find_signing_key(domain, "missing")
    assert fetch_calls["n"] == 2  # 1 stale + 1 refresh

    # Jump time past cooldown window.
    fake_now["t"] += ad._JWKS_COOLDOWN_SECONDS + 1
    await ad._find_signing_key(domain, "missing-again")
    # Cache serves the first read (0 network) + cooldown elapsed → 1 refresh.
    assert fetch_calls["n"] == 3
