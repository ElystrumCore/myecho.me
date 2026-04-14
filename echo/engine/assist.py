"""Inline editor AI assist — the bridge between BlockNote and Echo's voice engine.

When the owner selects text in the editor and triggers an AI action,
this module handles the request. Every action runs through the user's
voice prompt so the output matches their StyleFingerprint.
"""

from echo.engine.voice import generate_text

# Available assist actions and their prompt templates.
# The editor UI maps each action to one of these keys.
ASSIST_ACTIONS = {
    "rewrite": (
        "Rewrite the following text in your voice. Keep the meaning, change the style "
        "to match how you naturally write:\n\n{text}"
    ),
    "continue": (
        "Continue this thought naturally. Write the next 1-2 paragraphs as you would, "
        "staying on topic and in your voice:\n\n{text}"
    ),
    "more_direct": (
        "Rewrite this to be more direct and concise — less hedging, shorter sentences, "
        "get to the point faster. Stay in your voice:\n\n{text}"
    ),
    "more_casual": (
        "Rewrite this more casually — how you'd say it in a message to a colleague, "
        "not a formal document. Stay in your voice:\n\n{text}"
    ),
    "more_formal": (
        "Rewrite this more formally — suitable for a professional audience, while "
        "still sounding like you, not like a press release:\n\n{text}"
    ),
    "add_evidence": (
        "Expand this with supporting details from your experience and expertise. "
        "Add specific examples, numbers, or references where relevant. "
        "Stay in your voice:\n\n{text}"
    ),
    "position": (
        "Write a paragraph about this topic based on your positions and experience. "
        "Be substantive and specific — what do you actually think, and why?\n\n"
        "Topic: {text}"
    ),
    "custom": (
        "{instruction}\n\nText to work with:\n\n{text}"
    ),
}


def assist(
    voice_prompt: str,
    text: str,
    action: str = "rewrite",
    instruction: str | None = None,
) -> dict:
    """Run an inline AI assist action on selected text.

    Args:
        voice_prompt: The compiled system prompt from the user's profile.
        text: The selected text from the editor.
        action: One of the ASSIST_ACTIONS keys, or "custom" for free-form.
        instruction: Custom instruction (required when action="custom").

    Returns:
        dict with 'result' (the generated text) and 'action' used.
    """
    if action not in ASSIST_ACTIONS:
        action = "rewrite"

    template = ASSIST_ACTIONS[action]

    if action == "custom" and instruction:
        user_message = template.format(text=text, instruction=instruction)
    else:
        user_message = template.format(text=text)

    result = generate_text(voice_prompt, user_message, max_tokens=2048)

    return {
        "result": result,
        "action": action,
    }
