"""Voice generation — LLM wrapper that speaks in the user's voice."""

from echo.config import settings


def generate_text(
    voice_prompt: str,
    user_message: str,
    max_tokens: int | None = None,
) -> str:
    """Generate text using the voice prompt as system context.

    Args:
        voice_prompt: The compiled system prompt from the user's profile.
        user_message: The instruction or question to respond to.
        max_tokens: Override for max response tokens.

    Returns:
        Generated text in the user's voice.
    """
    try:
        import anthropic
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The anthropic SDK is required to generate text. Install project dependencies "
            "before using the voice engine."
        ) from exc

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    message = client.messages.create(
        model=settings.llm_model,
        max_tokens=max_tokens or settings.llm_max_tokens,
        system=voice_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    return message.content[0].text
