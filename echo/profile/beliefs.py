"""BeliefGraph builder — what the user thinks."""

from echo.ingest.linkedin import MessageStats


def build_belief_graph(
    message_stats: MessageStats | None = None,
    declarations: list[str] | None = None,
) -> dict:
    """Build a BeliefGraph from message topic signals and voice declarations.

    Returns the JSON structure defined in CLAUDE.md:
    - topics[] with name, mention_count, confidence, positions, evidence_refs
    - meta with total_topics, last_updated, drift_alerts
    """
    topics = []

    if message_stats and message_stats.topic_signals:
        for topic_name, count in message_stats.topic_signals.items():
            # Recency weight: topics with higher counts in recent messages get higher weight
            # For Phase 0, we approximate — real implementation would use message timestamps
            recency_weight = min(1.0, count / max(message_stats.topic_signals.values()))

            topics.append({
                "name": topic_name,
                "mention_count": count,
                "recency_weight": round(recency_weight, 2),
                "confidence": round(min(0.95, count / (count + 20)), 2),
                "positions": [],  # Populated by LLM analysis in later phase
                "evidence_refs": [],
            })

    # Voice declarations become high-confidence manual positions
    if declarations:
        for i, declaration in enumerate(declarations):
            # Each declaration is a position on an implicit topic
            topics.append({
                "name": f"declaration_{i}",
                "mention_count": 1,
                "recency_weight": 1.0,
                "confidence": 0.95,
                "positions": [declaration],
                "evidence_refs": [f"declaration_{i}"],
            })

    # Sort by mention count descending
    topics.sort(key=lambda t: t["mention_count"], reverse=True)

    return {
        "topics": topics[:20],  # Cap at top 20 for Phase 0
        "meta": {
            "total_topics": len(topics),
            "last_updated": None,  # Set by caller
            "drift_alerts": [],
        },
    }
