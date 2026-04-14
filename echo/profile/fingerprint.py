"""StyleFingerprint builder — how the user writes."""

from echo.ingest.linkedin import MessageStats
from echo.ingest.writing import WritingSample


def build_fingerprint(
    message_stats: MessageStats | None = None,
    writing_samples: list[WritingSample] | None = None,
) -> dict:
    """Build a StyleFingerprint from message data and writing samples.

    Returns the JSON structure defined in CLAUDE.md:
    - vocabulary (openers, closers, signature_phrases, filler_markers)
    - structure (median_length, short/medium/long pct, question_rate)
    - tone (formality_range, warmth, directness, humor_frequency)
    """
    fingerprint = {
        "vocabulary": {
            "openers": {},
            "closers": {},
            "signature_phrases": {},
            "filler_markers": {},
        },
        "structure": {
            "median_length": 0,
            "short_pct": 0.0,
            "medium_pct": 0.0,
            "long_pct": 0.0,
            "question_rate": 0.0,
        },
        "tone": {
            "formality_range": [0.3, 0.7],
            "warmth": 0.5,
            "directness": 0.5,
            "humor_frequency": 0.0,
        },
    }

    if message_stats and message_stats.user_messages > 0:
        fingerprint["vocabulary"]["openers"] = message_stats.openers
        fingerprint["vocabulary"]["closers"] = message_stats.closers
        fingerprint["vocabulary"]["signature_phrases"] = message_stats.signature_phrases
        fingerprint["vocabulary"]["filler_markers"] = message_stats.filler_markers

        fingerprint["structure"]["median_length"] = message_stats.median_length
        fingerprint["structure"]["question_rate"] = message_stats.question_rate
        fingerprint["structure"].update(message_stats.length_distribution)

        # Tone heuristics from message data
        humor_markers = sum(message_stats.filler_markers.get(m, 0) for m in ["haha", "lol", "lmao"])
        if message_stats.user_messages > 0:
            fingerprint["tone"]["humor_frequency"] = round(
                humor_markers / message_stats.user_messages, 3
            )

        # Directness: low question rate + short messages = high directness
        fingerprint["tone"]["directness"] = round(
            min(1.0, 1.0 - message_stats.question_rate + 0.1), 2
        )

        # Warmth: presence of fillers like "man", greetings, "thanks" closers
        warmth_signals = sum(message_stats.filler_markers.values()) + sum(
            message_stats.openers.get(o, 0) for o in ["hey", "hi", "hello"]
        )
        if message_stats.user_messages > 0:
            fingerprint["tone"]["warmth"] = round(
                min(1.0, warmth_signals / message_stats.user_messages * 3), 2
            )

        # Formality: short messages with fillers = informal
        informal_ratio = fingerprint["structure"].get("short_pct", 50) / 100
        fingerprint["tone"]["formality_range"] = [
            round(max(0.1, 0.5 - informal_ratio * 0.4), 2),
            round(min(0.9, 0.5 + (1 - informal_ratio) * 0.3), 2),
        ]

    # Enrich with writing samples if available
    if writing_samples:
        avg_richness = sum(s.vocabulary_richness for s in writing_samples) / len(writing_samples)
        # Higher vocabulary richness in long-form writing suggests wider formality range
        if avg_richness > 0.6:
            low, high = fingerprint["tone"]["formality_range"]
            fingerprint["tone"]["formality_range"] = [low, min(0.9, high + 0.1)]

    return fingerprint
