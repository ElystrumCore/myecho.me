"""Redis cache for the public journal + Ask surface.

Two public methods used by `main.py`:
  - `journal_data(username)` / `set_journal_data(username, data, ttl)`:
    caches the template context (entries + stats + display_name) for
    `GET /echo/{username}` to avoid 4-query PG fanout on every page view.
  - `ask_response(username, question)` / `set_ask_response(...)`:
    caches the Claude-generated answer keyed by (username, sha256(question))
    to bound Claude API spend on repeated questions.

Graceful degradation: if `REDIS_URL` is unset or the client raises on
connect/get/set, all methods return None / no-op and the caller falls
through to PG / Claude as if the cache didn't exist.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any, Optional

try:
    import redis  # type: ignore
except ImportError:  # noqa: BLE001 — redis is optional for myecho tests
    redis = None  # type: ignore

logger = logging.getLogger(__name__)

# Cache TTLs (seconds). Conservative defaults — public journals don't update
# faster than the author writing them, and an Ask response can stay valid for
# an hour without confusing readers.
JOURNAL_TTL = int(os.getenv("ECHO_JOURNAL_CACHE_TTL", "300"))  # 5 min
ASK_TTL = int(os.getenv("ECHO_ASK_CACHE_TTL", "3600"))  # 1 hour

_PREFIX = "echo"
_REDIS_URL = os.getenv("REDIS_URL")
_CLIENT: Optional["redis.Redis"] = None
_DISABLED = False  # latched True after a connect failure to avoid retry storms


def _get_client() -> Optional["redis.Redis"]:
    """Lazily resolve a Redis client. Returns None if unavailable."""
    global _CLIENT, _DISABLED
    if _DISABLED or redis is None or not _REDIS_URL:
        return None
    if _CLIENT is not None:
        return _CLIENT
    try:
        _CLIENT = redis.from_url(
            _REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        # Probe — cheap PING; if Redis is down, latch _DISABLED and never retry
        # in this process.
        _CLIENT.ping()
        logger.info("Echo Redis cache connected (%s)", _REDIS_URL.split("@")[-1])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Echo Redis cache disabled (connect failed: %s)", exc)
        _DISABLED = True
        _CLIENT = None
    return _CLIENT


def _safe_get(key: str) -> Optional[Any]:
    client = _get_client()
    if client is None:
        return None
    try:
        raw = client.get(key)
        return json.loads(raw) if raw else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Echo cache GET %s failed: %s", key, exc)
        return None


def _safe_set(key: str, value: Any, ttl: int) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        client.setex(key, ttl, json.dumps(value, default=str))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Echo cache SET %s failed: %s", key, exc)


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def journal_data(username: str) -> Optional[dict]:
    """Return the cached template context for /echo/{username} or None."""
    return _safe_get(f"{_PREFIX}:journal:{username}")


def set_journal_data(username: str, data: dict) -> None:
    _safe_set(f"{_PREFIX}:journal:{username}", data, JOURNAL_TTL)


def invalidate_journal(username: str) -> None:
    """Call this on entry publish / profile rebuild so the next page load
    sees fresh data instead of waiting out the TTL."""
    client = _get_client()
    if client is None:
        return
    try:
        client.delete(f"{_PREFIX}:journal:{username}")
    except Exception:  # noqa: BLE001
        pass


def _question_hash(question: str) -> str:
    return hashlib.sha256(question.strip().lower().encode("utf-8")).hexdigest()[:16]


def ask_response(username: str, question: str) -> Optional[dict]:
    """Return cached Claude response for (username, question) or None."""
    if not question:
        return None
    return _safe_get(f"{_PREFIX}:ask:{username}:{_question_hash(question)}")


def set_ask_response(username: str, question: str, response: dict) -> None:
    if not question:
        return
    _safe_set(
        f"{_PREFIX}:ask:{username}:{_question_hash(question)}",
        response,
        ASK_TTL,
    )
