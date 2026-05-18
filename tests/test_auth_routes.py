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
    """TestClient against the full FastAPI app.

    Uses the real sqlite in-memory engine. echo.database._make_engine
    configures sqlite with check_same_thread=False + StaticPool so
    TestClient's worker-thread dispatches share the same DB the fixture
    creates tables on. These tests only check auth gating; route handlers
    that pass auth then hit "not found" because the DB is empty — which
    is exactly what the "not 401/403" assertions expect.
    """
    # Importing echo.models.* ensures every Base subclass is registered
    # before create_all. Without this, only models that happen to have
    # been imported elsewhere get tables.
    from echo import models  # noqa: F401
    from echo.database import Base, engine
    from echo.main import app

    Base.metadata.create_all(bind=engine)
    try:
        yield TestClient(app)
    finally:
        Base.metadata.drop_all(bind=engine)


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


# ============================================================================
# Deploy-T5: /api/echo/* gating
# ============================================================================

def test_echo_generate_without_auth_returns_401(client):
    resp = client.post("/api/echo/00000000-0000-0000-0000-000000000000/generate", json={})
    assert resp.status_code == 401


def test_echo_assist_without_auth_returns_401(client):
    resp = client.post("/api/echo/00000000-0000-0000-0000-000000000000/assist", json={})
    assert resp.status_code == 401


def test_echo_drafts_without_auth_returns_401(client):
    resp = client.get("/api/echo/00000000-0000-0000-0000-000000000000/drafts")
    assert resp.status_code == 401


def test_echo_voice_upload_without_auth_returns_401(client):
    resp = client.post("/api/echo/00000000-0000-0000-0000-000000000000/voice", json={})
    assert resp.status_code == 401


def test_echo_ask_without_auth_returns_401(client):
    resp = client.post("/api/echo/00000000-0000-0000-0000-000000000000/ask", json={})
    assert resp.status_code == 401


def test_echo_update_draft_without_auth_returns_401(client):
    resp = client.put(
        "/api/echo/00000000-0000-0000-0000-000000000000/drafts/"
        "00000000-0000-0000-0000-000000000000?action=publish"
    )
    assert resp.status_code == 401


# ============================================================================
# Deploy-T6: /api/profile mutations + /api/ingest/* gating
# ============================================================================

def test_profile_beliefs_put_without_auth_returns_401(client):
    resp = client.put(
        "/api/profile/00000000-0000-0000-0000-000000000000/beliefs",
        json={},
    )
    assert resp.status_code == 401


def test_profile_ingest_conversations_without_auth_returns_401(client):
    resp = client.post(
        "/api/profile/00000000-0000-0000-0000-000000000000/ingest/conversations"
        "?source_type=claude",
    )
    assert resp.status_code == 401


def test_profile_rebuild_without_auth_returns_401(client):
    resp = client.post(
        "/api/profile/00000000-0000-0000-0000-000000000000/rebuild",
    )
    assert resp.status_code == 401


def test_profile_get_remains_public(client):
    """Profile GETs are visitor-facing — must NOT be gated."""
    resp = client.get("/api/profile/00000000-0000-0000-0000-000000000000")
    # Not found is fine; 401 means we wrongly gated it.
    assert resp.status_code != 401


def test_profile_fingerprint_get_remains_public(client):
    resp = client.get(
        "/api/profile/00000000-0000-0000-0000-000000000000/fingerprint"
    )
    assert resp.status_code != 401


def test_profile_beliefs_get_remains_public(client):
    resp = client.get(
        "/api/profile/00000000-0000-0000-0000-000000000000/beliefs"
    )
    assert resp.status_code != 401


def test_profile_knowledge_get_remains_public(client):
    resp = client.get(
        "/api/profile/00000000-0000-0000-0000-000000000000/knowledge"
    )
    assert resp.status_code != 401


def test_ingest_linkedin_messages_without_auth_returns_401(client):
    resp = client.post("/api/ingest/linkedin/messages")
    assert resp.status_code == 401


def test_ingest_linkedin_endorsements_without_auth_returns_401(client):
    resp = client.post("/api/ingest/linkedin/endorsements")
    assert resp.status_code == 401


def test_ingest_linkedin_connections_without_auth_returns_401(client):
    resp = client.post("/api/ingest/linkedin/connections")
    assert resp.status_code == 401


def test_ingest_career_without_auth_returns_401(client):
    resp = client.post("/api/ingest/career", json={})
    assert resp.status_code == 401


def test_ingest_writing_without_auth_returns_401(client):
    resp = client.post("/api/ingest/writing")
    assert resp.status_code == 401


def test_ingest_declaration_without_auth_returns_401(client):
    resp = client.post("/api/ingest/declaration")
    assert resp.status_code == 401


def test_ingest_status_without_auth_returns_401(client):
    resp = client.get(
        "/api/ingest/status/00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 401


# ============================================================================
# Deploy-T7: /api/dashboard/* gating
# ============================================================================

def test_dashboard_overview_without_auth_returns_401(client):
    resp = client.get("/api/dashboard/00000000-0000-0000-0000-000000000000/overview")
    assert resp.status_code == 401


def test_dashboard_drift_without_auth_returns_401(client):
    resp = client.get("/api/dashboard/00000000-0000-0000-0000-000000000000/drift")
    assert resp.status_code == 401


def test_dashboard_drift_acknowledge_without_auth_returns_401(client):
    resp = client.put(
        "/api/dashboard/00000000-0000-0000-0000-000000000000/drift/"
        "00000000-0000-0000-0000-000000000000/acknowledge",
        json={},
    )
    assert resp.status_code == 401


# ============================================================================
# Deploy-T8 cleanup: gate comments.moderate_comment (was missed in T7)
#
# Comments router is mounted at /api/journal (see echo/main.py). The
# moderate route is PUT /{user_id}/comments/{comment_id}/moderate with
# body {"action": "hide"|"delete"} — see echo/api/comments.py.
# ============================================================================

def test_comment_moderate_without_auth_returns_401(client):
    resp = client.put(
        "/api/journal/00000000-0000-0000-0000-000000000000/comments/"
        "00000000-0000-0000-0000-000000000000/moderate",
        json={"action": "hide"},
    )
    assert resp.status_code == 401
