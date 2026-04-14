"""Tests for profile builders — fingerprint, beliefs, knowledge, compiler."""

from echo.ingest.linkedin import MessageStats, EndorsementStats, ConnectionStats
from echo.ingest.career import CareerHistory, CareerPosition
from echo.profile.fingerprint import build_fingerprint
from echo.profile.beliefs import build_belief_graph
from echo.profile.knowledge import build_knowledge_map
from echo.profile.compiler import compile_voice_prompt


def _sample_message_stats() -> MessageStats:
    return MessageStats(
        total_messages=100,
        user_messages=60,
        median_length=69,
        openers={"hey": 20, "yeah": 15, "sounds good": 10},
        closers={"thanks": 30},
        signature_phrases={"for sure": 12, "definitely": 8},
        filler_markers={"man": 15, "haha": 5},
        topic_signals={"ai": 30, "pipeline": 10, "business": 5},
        question_rate=0.165,
        length_distribution={"short_pct": 62.7, "medium_pct": 34.9, "long_pct": 2.4},
        raw_messages=["Hey man for sure", "Yeah definitely"],
    )


def test_build_fingerprint():
    stats = _sample_message_stats()
    fp = build_fingerprint(message_stats=stats)
    assert fp["vocabulary"]["openers"]["hey"] == 20
    assert fp["structure"]["median_length"] == 69
    assert fp["tone"]["directness"] > 0.5
    assert fp["tone"]["warmth"] > 0


def test_build_fingerprint_empty():
    fp = build_fingerprint()
    assert fp["structure"]["median_length"] == 0


def test_build_belief_graph():
    stats = _sample_message_stats()
    bg = build_belief_graph(message_stats=stats)
    assert len(bg["topics"]) > 0
    assert bg["topics"][0]["name"] == "ai"  # highest mention count
    assert bg["meta"]["total_topics"] == 3


def test_build_belief_graph_with_declarations():
    bg = build_belief_graph(declarations=["Local models are viable for production"])
    assert len(bg["topics"]) == 1
    assert bg["topics"][0]["confidence"] == 0.95


def test_build_knowledge_map():
    career = CareerHistory(
        positions=[
            CareerPosition("Pipefitter", "Co A", 2005, 2010, "Oil & Gas"),
            CareerPosition("SVP", "Co C", 2020, None, "Oil & Gas"),
        ],
        total_years=21,
        industries=["Oil & Gas"],
        trajectory=["Pipefitter", "SVP"],
    )
    endorsements = EndorsementStats(
        total_endorsements=100,
        unique_endorsers=50,
        skills={"Piping": 75, "Gas": 74},
    )
    connections = ConnectionStats(total_connections=19000, companies={"Cenovus": 200})
    km = build_knowledge_map(endorsements=endorsements, connections=connections, career=career)
    assert len(km["domains"]) > 0
    assert km["network"]["total_connections"] == 19000


def test_compile_voice_prompt():
    fp = build_fingerprint(message_stats=_sample_message_stats())
    bg = build_belief_graph(message_stats=_sample_message_stats())
    km = build_knowledge_map()
    prompt = compile_voice_prompt("CJ", fp, bg, km)
    assert "CJ" in prompt
    assert "Echo" in prompt
    assert "hey" in prompt.lower() or "vocabulary" in prompt.lower()
