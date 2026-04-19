"""
Resonance retrieval — finds holder positions that resonate with incoming content.

Uses MetaMiner's toroidal encoding to find BeliefGraph topics and Cyclone
documents that are harmonically close to an incoming question or letter,
rather than keyword-matching. This makes Ghost composition more coherent
across topics that share deep structure but different vocabulary.

Example: a question about "workforce availability" resonates with positions
about "inspector bottleneck" and "contractor ecosystem" even though they
share no keywords — because the underlying belief structure is the same.
"""
from __future__ import annotations

import logging
import math
import sys
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Monorepo path for MetaMiner access
_MONOREPO_ROOT = Path(__file__).parent.parent.parent.parent / "aethercore-monorepo"

_initialized = False
_encoder = None
_projector = None
_codebook = None


def _init():
    global _initialized, _encoder, _projector, _codebook
    if _initialized:
        return _encoder is not None

    try:
        monorepo = str(_MONOREPO_ROOT)
        if monorepo not in sys.path:
            sys.path.insert(0, monorepo)

        from packages.core.substrate.metaminer import HarmonicEncoder, ToroidalProjector
        from packages.core.substrate.core import ToroidalCoordinate
        from packages.core.usl.codebook import Codebook

        _codebook = Codebook()
        _encoder = HarmonicEncoder(_codebook)
        _projector = ToroidalProjector()
        _initialized = True
        logger.info("Echo resonance engine initialized (MetaMiner)")
        return True
    except Exception as e:
        _initialized = True  # Don't retry
        logger.warning("MetaMiner not available for resonance: %s", e)
        return False


def find_resonant_positions(
    question: str,
    belief_graph: dict[str, Any],
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """Find BeliefGraph topics that resonate with an incoming question.

    Encodes the question through MetaMiner, then encodes each topic,
    and ranks by toroidal resonance (semantic proximity regardless of
    temporal distance).

    Args:
        question: The incoming question or letter text.
        belief_graph: The holder's BeliefGraph from their profile.
        top_k: Maximum number of resonant topics to return.

    Returns:
        List of topic dicts with added 'resonance' score, sorted by resonance.
    """
    if not _init():
        # Fallback: keyword matching
        return _keyword_fallback(question, belief_graph, top_k)

    from packages.core.substrate.metaminer import MetadataSchema
    from packages.core.substrate.core import ToroidalCoordinate

    # Encode the question
    question_meta = MetadataSchema(
        context_tags=question.lower().split()[:10],
        retrieval_heads=["incoming_question"],
        source_trust_score=0.5,
    )
    question_sig = _encoder.encode(question_meta)
    question_features = _encoder._extractor.extract(question_meta)
    question_coord = _projector.project(question_sig, temporal_angle=question_features.temporal_angle)

    topics = belief_graph.get("topics", [])
    if not topics:
        return []

    scored = []
    for topic in topics:
        # Encode the topic
        topic_meta = MetadataSchema(
            context_tags=topic.get("name", "").lower().replace("/", " ").split(),
            retrieval_heads=[topic.get("name", "")],
            source_trust_score=topic.get("confidence", 0.5),
        )
        topic_sig = _encoder.encode(topic_meta)
        topic_features = _encoder._extractor.extract(topic_meta)
        topic_coord = _projector.project(topic_sig, temporal_angle=topic_features.temporal_angle)

        # Resonance on T² — semantic proximity
        resonance = question_coord.resonance(topic_coord)

        scored.append({
            **topic,
            "resonance": resonance,
        })

    scored.sort(key=lambda x: x["resonance"], reverse=True)
    return scored[:top_k]


def build_resonant_context(
    question: str,
    belief_graph: dict[str, Any],
    max_topics: int = 3,
) -> str:
    """Build a context string from resonant positions for injection into the prompt.

    This is what gets prepended to the question when Ghost or Ask compose
    a response — the holder's most relevant positions on topics that
    resonate with what's being asked.

    Args:
        question: The incoming question/letter.
        belief_graph: Holder's BeliefGraph.
        max_topics: How many topics to include.

    Returns:
        Context string, or empty string if no resonant topics found.
    """
    resonant = find_resonant_positions(question, belief_graph, top_k=max_topics)
    if not resonant:
        return ""

    lines = ["Your most relevant positions on this topic:"]
    for topic in resonant:
        name = topic.get("name", "Unknown")
        mentions = topic.get("mention_count", 0)
        confidence = topic.get("confidence", 0)
        resonance = topic.get("resonance", 0)
        lines.append(
            f"- {name} ({mentions} mentions, confidence {confidence:.0%}, "
            f"resonance {resonance:.3f})"
        )
        # Include sample messages if available
        samples = topic.get("sample_messages", [])
        for sample in samples[:2]:
            lines.append(f'  > "{sample[:150]}"')

    return "\n".join(lines)


def _keyword_fallback(
    question: str,
    belief_graph: dict[str, Any],
    top_k: int,
) -> list[dict[str, Any]]:
    """Simple keyword matching fallback when MetaMiner isn't available."""
    question_words = set(question.lower().split())
    topics = belief_graph.get("topics", [])
    scored = []
    for topic in topics:
        name_words = set(topic.get("name", "").lower().replace("/", " ").split())
        overlap = len(question_words & name_words)
        if overlap > 0:
            scored.append({**topic, "resonance": overlap / max(len(name_words), 1)})
    scored.sort(key=lambda x: x["resonance"], reverse=True)
    return scored[:top_k]
