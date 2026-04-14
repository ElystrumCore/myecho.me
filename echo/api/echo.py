import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from echo.database import get_db
from echo.models.profile import EchoProfile
from echo.models.journal import (
    JournalEntry,
    JournalContent,
    EntryProp,
    EntryStatus,
)

router = APIRouter()


class GenerateRequest(BaseModel):
    topic: str | None = None


class AskRequest(BaseModel):
    question: str


class AssistRequest(BaseModel):
    text: str
    action: str = "rewrite"
    instruction: str | None = None


@router.post("/{user_id}/voice")
async def voice_to_text(
    user_id: uuid.UUID,
    file: UploadFile = File(...),
    polish: bool = True,
    db: Session = Depends(get_db),
):
    """Record → transcribe → polish → draft.

    Accepts audio (webm, mp3, wav, m4a), transcribes via Whisper,
    optionally polishes through the voice engine, and returns both
    the raw transcript and the polished version.

    The raw transcript also becomes ingest data — feeding the BeliefGraph
    with newly detected positions from spoken words.
    """
    from echo.engine.transcribe import transcribe_audio, polish_transcript

    audio_data = await file.read()
    transcript = await transcribe_audio(audio_data, filename=file.filename or "recording.webm")

    result = {
        "raw_transcript": transcript.text,
        "language": transcript.language,
        "duration_seconds": transcript.duration_seconds,
    }

    if polish:
        profile = db.query(EchoProfile).filter(EchoProfile.user_id == user_id).first()
        if profile and profile.voice_prompt:
            polished = polish_transcript(profile.voice_prompt, transcript.text)
            result["polished"] = polished

    return result


@router.post("/{user_id}/generate")
async def generate_post(
    user_id: uuid.UUID,
    request: GenerateRequest,
    db: Session = Depends(get_db),
):
    """Generate a journal post in the user's voice."""
    profile = db.query(EchoProfile).filter(EchoProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found — run ingest first")

    # TODO: call engine.journal.generate with profile + topic
    entry = JournalEntry(
        user_id=user_id,
        title=f"On {request.topic or 'things on my mind'}",
        status=EntryStatus.pending_review,
        generation_prompt=request.topic,
    )
    db.add(entry)
    db.flush()

    # Separate content table (LJ logtext2 pattern)
    content = JournalContent(
        entry_id=entry.id,
        body="[generation pending — engine not yet wired]",
    )
    db.add(content)

    # Topic tags via props system (LJ logprop2 pattern)
    if request.topic:
        prop = EntryProp(entry_id=entry.id, prop_key="topic_tags", prop_value=request.topic)
        db.add(prop)

    db.commit()
    db.refresh(entry)
    return {"entry_id": entry.id, "status": entry.status, "title": entry.title}


@router.post("/{user_id}/ask")
async def ask_echo(
    user_id: uuid.UUID,
    request: AskRequest,
    db: Session = Depends(get_db),
):
    """Ask the Echo a question, get a response in the user's voice."""
    profile = db.query(EchoProfile).filter(EchoProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # TODO: call engine.ask.respond with profile + question
    return {
        "question": request.question,
        "response": "[response pending — engine not yet wired]",
        "confidence": 0.0,
    }


@router.post("/{user_id}/assist")
async def assist_inline(
    user_id: uuid.UUID,
    request: AssistRequest,
    db: Session = Depends(get_db),
):
    """Inline editor AI assist — rewrites selected text in the user's voice.

    Used by the BlockNote editor's AI actions. Every action runs through the
    user's voice prompt so output matches their StyleFingerprint.

    Actions: rewrite, continue, more_direct, more_casual, more_formal,
    add_evidence, position, custom (requires instruction field).
    """
    profile = db.query(EchoProfile).filter(EchoProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found — run ingest first")
    if not profile.voice_prompt:
        raise HTTPException(status_code=400, detail="Voice prompt not compiled — rebuild profile")

    from echo.engine.assist import assist
    result = assist(
        voice_prompt=profile.voice_prompt,
        text=request.text,
        action=request.action,
        instruction=request.instruction,
    )
    return result


@router.get("/{user_id}/drafts")
async def list_drafts(user_id: uuid.UUID, db: Session = Depends(get_db)):
    """List pending drafts for review — metadata only, no body content."""
    drafts = (
        db.query(JournalEntry)
        .filter(
            JournalEntry.user_id == user_id,
            JournalEntry.status.in_([EntryStatus.draft, EntryStatus.pending_review]),
        )
        .order_by(JournalEntry.created_at.desc())
        .all()
    )
    return [
        {
            "id": d.id,
            "title": d.title,
            "status": d.status,
            "created_at": d.created_at,
        }
        for d in drafts
    ]


@router.put("/{user_id}/drafts/{entry_id}")
async def update_draft(
    user_id: uuid.UUID,
    entry_id: uuid.UUID,
    action: str,
    db: Session = Depends(get_db),
):
    """Approve, edit, or reject a draft. action: publish | archive"""
    entry = (
        db.query(JournalEntry)
        .filter(JournalEntry.id == entry_id, JournalEntry.user_id == user_id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Draft not found")

    if action == "publish":
        entry.status = EntryStatus.published
        now = datetime.utcnow()
        entry.published_at = now
        entry.pub_year = now.year
        entry.pub_month = now.month
        entry.pub_day = now.day
    elif action == "archive":
        entry.status = EntryStatus.archived
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    db.commit()
    return {"entry_id": entry.id, "status": entry.status}
