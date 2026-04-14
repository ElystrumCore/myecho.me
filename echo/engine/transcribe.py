"""Voice-to-text transcription — Whisper API for Phase 0, swappable backend.

The flow:
1. Owner records audio in the dashboard
2. Audio hits POST /api/echo/{user_id}/voice
3. This module transcribes it via Whisper API
4. Raw transcript is returned (and optionally saved as ingest data)
5. Caller can then run the transcript through the voice engine to polish it

The raw transcript also feeds the BeliefGraph — new positions detected in
spoken words get extracted and added to the profile over time.
"""

import io
from dataclasses import dataclass

import httpx

from echo.config import settings


@dataclass
class TranscriptResult:
    text: str
    language: str
    duration_seconds: float


async def transcribe_audio(
    audio_data: bytes,
    filename: str = "recording.webm",
    language: str | None = None,
) -> TranscriptResult:
    """Transcribe audio using the OpenAI Whisper API.

    Phase 0 uses the hosted API at $0.006/minute. The interface is designed
    so swapping in self-hosted Whisper Turbo or Distil-Whisper later only
    requires changing this function.

    Args:
        audio_data: Raw audio bytes (webm, mp3, wav, m4a, etc.)
        filename: Original filename with extension (used for content-type).
        language: Optional ISO language code to improve accuracy.

    Returns:
        TranscriptResult with text, detected language, and duration.
    """
    # Whisper API endpoint — compatible with OpenAI's /v1/audio/transcriptions
    api_url = settings.whisper_api_url
    api_key = settings.whisper_api_key

    form_data = {"model": settings.whisper_model}
    if language:
        form_data["language"] = language
    # Request word-level timestamps for future WhisperX-style features
    form_data["response_format"] = "verbose_json"

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            api_url,
            headers={"Authorization": f"Bearer {api_key}"},
            data=form_data,
            files={"file": (filename, io.BytesIO(audio_data))},
        )
        response.raise_for_status()

    result = response.json()

    return TranscriptResult(
        text=result.get("text", ""),
        language=result.get("language", "en"),
        duration_seconds=result.get("duration", 0.0),
    )


def polish_transcript(voice_prompt: str, raw_text: str) -> str:
    """Run a raw voice transcript through the Echo voice engine to polish it.

    Takes the messy spoken-word transcript and rewrites it as a clean journal
    entry in the user's written voice. Preserves the ideas and positions,
    cleans up the ums and restarts, and matches the StyleFingerprint.
    """
    from echo.engine.voice import generate_text

    instruction = (
        "Below is a raw voice transcript — something you said out loud. "
        "Clean it up into a journal post in your written voice. "
        "Keep all the ideas, positions, and specifics. "
        "Remove the verbal filler, false starts, and repetition. "
        "Make it read like something you'd publish on your journal — "
        "structured, clear, but still you. Include a title.\n\n"
        f"Raw transcript:\n\n{raw_text}"
    )

    return generate_text(voice_prompt, instruction)
