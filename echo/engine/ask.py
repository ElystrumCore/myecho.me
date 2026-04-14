"""Ask response generation — Echo answers questions in the user's voice."""

from echo.engine.voice import generate_text


def respond(voice_prompt: str, question: str) -> dict:
    """Generate a response to a visitor's question in the user's voice.

    Args:
        voice_prompt: Compiled system prompt from user profile.
        question: The visitor's question.

    Returns:
        dict with 'response' and 'confidence' keys.
    """
    instruction = (
        f"Someone is asking you a question on your public journal page:\n\n"
        f'"{question}"\n\n'
        "Answer as yourself — in your natural voice, from your knowledge and positions. "
        "If you don't know something or it's outside your expertise, say so honestly. "
        "If you're extrapolating a position you haven't explicitly stated before, "
        'flag it with something like "I think..." or "My sense is...". '
        "Keep the response conversational but substantive."
    )

    response_text = generate_text(voice_prompt, instruction, max_tokens=1024)

    # Rough confidence heuristic based on hedging language
    hedges = ["i think", "i'm not sure", "not certain", "my sense is", "probably", "might be"]
    hedge_count = sum(1 for h in hedges if h in response_text.lower())
    confidence = max(0.3, 1.0 - hedge_count * 0.15)

    return {
        "response": response_text,
        "confidence": round(confidence, 2),
    }
