"""Journal post generation — Echo writes blog posts in the user's voice."""

from echo.engine.voice import generate_text


def generate_post(voice_prompt: str, topic: str | None = None) -> dict:
    """Generate a journal post in the user's voice.

    Args:
        voice_prompt: Compiled system prompt from user profile.
        topic: Optional topic to write about. If None, Echo chooses based on profile.

    Returns:
        dict with 'title' and 'content' keys.
    """
    if topic:
        instruction = (
            f"Write a journal post about: {topic}\n\n"
            "Write naturally in first person. This is for your personal journal/blog — "
            "not a LinkedIn post, not SEO content, not engagement bait. "
            "Write what you actually think about this topic, in your natural voice. "
            "Keep it honest and substantive. Include a title."
        )
    else:
        instruction = (
            "Write a journal post about something on your mind right now. "
            "Pick a topic from your areas of expertise or something you've been thinking about. "
            "Write naturally in first person for your personal journal/blog. "
            "Keep it honest and substantive. Include a title."
        )

    raw = generate_text(voice_prompt, instruction)

    # Parse title from first line if present
    lines = raw.strip().split("\n", 1)
    title = lines[0].lstrip("#").strip() if lines else "Untitled"
    content = lines[1].strip() if len(lines) > 1 else raw

    return {"title": title, "content": content}
