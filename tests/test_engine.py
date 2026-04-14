"""Tests for engine modules — drift detection (voice/journal/ask require LLM)."""

from echo.engine.drift import detect_drift


def test_detect_drift_no_change():
    beliefs = {
        "topics": [
            {"name": "ai", "positions": ["AI is useful", "Local models work"]},
        ]
    }
    events = detect_drift(beliefs, beliefs)
    assert len(events) == 0


def test_detect_drift_with_change():
    original = {
        "topics": [
            {"name": "ai", "positions": ["AI is useful", "Cloud models are best"]},
        ]
    }
    current = {
        "topics": [
            {"name": "ai", "positions": ["AI is useful", "Local models are best"]},
        ]
    }
    events = detect_drift(original, current)
    assert len(events) == 1
    assert events[0]["topic"] == "ai"
    assert events[0]["drift_score"] > 0


def test_detect_drift_new_topic():
    original = {"topics": [{"name": "ai", "positions": ["AI is useful"]}]}
    current = {
        "topics": [
            {"name": "ai", "positions": ["AI is useful"]},
            {"name": "construction", "positions": ["Safety first"]},
        ]
    }
    # New topics are not drift, just growth
    events = detect_drift(original, current)
    assert len(events) == 0
