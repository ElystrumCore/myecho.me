"""Drift detection — tracks how Echo's model of the user shifts over time."""


def detect_drift(
    original_beliefs: dict,
    current_beliefs: dict,
) -> list[dict]:
    """Compare two versions of a BeliefGraph and identify drift.

    Args:
        original_beliefs: The previously confirmed BeliefGraph.
        current_beliefs: The newly generated BeliefGraph.

    Returns:
        List of drift events with topic, original_position, current_position, drift_score.
    """
    drift_events = []

    original_topics = {t["name"]: t for t in original_beliefs.get("topics", [])}
    current_topics = {t["name"]: t for t in current_beliefs.get("topics", [])}

    for topic_name, current_topic in current_topics.items():
        if topic_name not in original_topics:
            # New topic — not drift, just growth
            continue

        original_topic = original_topics[topic_name]
        original_positions = set(original_topic.get("positions", []))
        current_positions = set(current_topic.get("positions", []))

        if not original_positions or not current_positions:
            continue

        # Simple set-based drift score: how much has changed?
        if original_positions == current_positions:
            continue

        overlap = original_positions & current_positions
        total = original_positions | current_positions
        drift_score = 1.0 - (len(overlap) / len(total)) if total else 0.0

        if drift_score > 0.1:  # Only flag meaningful drift
            drift_events.append({
                "topic": topic_name,
                "original_position": "; ".join(sorted(original_positions)),
                "current_position": "; ".join(sorted(current_positions)),
                "drift_score": round(drift_score, 3),
            })

    return drift_events
