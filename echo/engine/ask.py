"""Ask response generation — Echo answers questions in the user's voice."""

import logging
from typing import Optional

from echo.engine.voice import generate_text

logger = logging.getLogger(__name__)


def respond(
    voice_prompt: str,
    question: str,
    belief_graph: Optional[dict] = None,
) -> dict:
    """Generate a response to a visitor's question in the user's voice.

    If a belief_graph is provided, uses MetaMiner resonance to find the
    holder's most relevant positions and injects them as context. This
    makes responses draw from harmonically resonant positions rather than
    keyword-matched ones.

    Args:
        voice_prompt: Compiled system prompt from user profile.
        question: The visitor's question.
        belief_graph: Optional BeliefGraph for resonance retrieval.

    Returns:
        dict with 'response', 'confidence', and optionally 'resonant_topics' keys.
    """
    # Find resonant positions if belief_graph available
    resonant_context = ""
    resonant_topics = []
    if belief_graph:
        try:
            from echo.engine.resonance import build_resonant_context, find_resonant_positions
            resonant_context = build_resonant_context(question, belief_graph)
            resonant_topics = [
                {"name": t["name"], "resonance": round(t["resonance"], 3)}
                for t in find_resonant_positions(question, belief_graph)
            ]
            if resonant_context:
                logger.info(
                    "Resonance retrieval: %d topics for '%s...'",
                    len(resonant_topics), question[:50],
                )
        except Exception as e:
            logger.debug("Resonance retrieval skipped: %s", e)

    # Build instruction with resonant context
    context_block = f"\n\n{resonant_context}\n\n" if resonant_context else "\n\n"

    instruction = (
        f"Someone is asking you a question on your public journal page:\n\n"
        f'"{question}"'
        f"{context_block}"
        "Answer as yourself — in your natural voice, from your knowledge and positions. "
        "If you don't know something or it's outside your expertise, say so honestly. "
        "If you're extrapolating a position you haven't explicitly stated before, "
        'flag it with something like "I think..." or "My sense is...". '
        "Keep the response conversational but substantive."
    )

    response_text = generate_text(voice_prompt, instruction, max_tokens=1024)

    # Confidence heuristic
    hedges = ["i think", "i'm not sure", "not certain", "my sense is", "probably", "might be"]
    hedge_count = sum(1 for h in hedges if h in response_text.lower())
    confidence = max(0.3, 1.0 - hedge_count * 0.15)

    result = {
        "response": response_text,
        "confidence": round(confidence, 2),
    }
    if resonant_topics:
        result["resonant_topics"] = resonant_topics

    return result
