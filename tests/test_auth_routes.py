"""Integration tests for auth-gated routes.

Each task (Deploy-T4 through Deploy-T7) adds tests for the routes it gates.
"""
import importlib
import os

# echo.config instantiates Settings() at import time, which requires
# ECHO_DATABASE_URL. Set it before any echo.* import. SQLite is fine because
# these tests exercise auth gating, not DB I/O — the routes that pass auth
# will hit downstream failures (no profile, no model), which the tests treat
# as "auth-passed" by asserting status NOT in (401, 403).
os.environ["ECHO_DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from jose import jwt


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-do-not-use-in-prod")
    monkeypatch.setenv("MYECHO_ALLOWED_EMAILS", "good@example.com")
    monkeypatch.setenv("AUTH0_DOMAIN", "")
    monkeypatch.setenv("AUTH0_AUDIENCE", "")
    monkeypatch.setenv("ECHO_DEBUG", "false")
    import echo.api.auth_dep
    importlib.reload(echo.api.auth_dep)


@pytest.fixture
def client():
    """TestClient against the full FastAPI app."""
    from echo.main import app
    return TestClient(app)


@pytest.fixture
def good_token():
    return jwt.encode(
        {"email": "good@example.com", "sub": "test"},
        "test-secret-do-not-use-in-prod",
        algorithm="HS256",
    )


# ============================================================================
# Deploy-T4: /voice/* gating
# ============================================================================

def test_voice_generate_without_auth_returns_401(client):
    resp = client.post("/voice/generate", json={"topic": "test"})
    assert resp.status_code == 401


def test_voice_generate_with_bad_token_returns_401(client):
    resp = client.post(
        "/voice/generate",
        json={"topic": "test"},
        headers={"Authorization": "Bearer not-a-valid-token"},
    )
    assert resp.status_code == 401


def test_voice_generate_with_good_token_passes_auth(client, good_token):
    # We only care that auth passes; downstream may 5xx due to no profile data
    # in test DB. So we check status is NOT 401/403.
    resp = client.post(
        "/voice/generate",
        json={"topic": "test"},
        headers={"Authorization": f"Bearer {good_token}"},
    )
    assert resp.status_code not in (401, 403)


def test_voice_feedback_without_auth_returns_401(client):
    resp = client.post("/voice/feedback", json={})
    assert resp.status_code == 401
