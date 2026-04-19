"""The Exchange — correspondence surface for Echo."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from echo.database import get_db
from echo.models.exchange import (
    GhostDraft,
    GhostDraftStatus,
    GhostMode,
    GhostSettings,
    GuestbookEntry,
    Letter,
    LetterTransport,
)
from echo.models.profile import EchoProfile
from echo.models.user import User

router = APIRouter()


# --- Request/Response Models ---

class SendLetterRequest(BaseModel):
    to_username: str
    subject: Optional[str] = None
    body: str = Field(..., min_length=1, max_length=10000)
    from_name: str = Field(default="Anonymous", max_length=256)
    from_email: Optional[str] = None


class LetterResponse(BaseModel):
    id: str
    from_address: str
    to_address: str
    subject: Optional[str]
    body: str
    transport: str
    ghost_metadata: Optional[dict] = None
    created_at: str
    read_at: Optional[str] = None


class GhostDraftResponse(BaseModel):
    id: str
    incoming_letter_id: str
    draft_body: str
    status: str
    created_at: str


class GhostSettingsRequest(BaseModel):
    mode: str = Field(default="off", pattern="^(off|draft|auto)$")


class GuestbookRequest(BaseModel):
    from_name: str = Field(..., min_length=1, max_length=128)
    body: str = Field(..., min_length=1, max_length=280)
    from_mood: Optional[str] = None


# --- Helpers ---

def _get_user_by_username(username: str, db: Session) -> User:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _letter_to_response(letter: Letter) -> dict:
    return {
        "id": str(letter.id),
        "from_address": letter.from_address,
        "to_address": letter.to_address,
        "subject": letter.subject,
        "body": letter.body,
        "transport": letter.transport.value if letter.transport else "web",
        "ghost_metadata": letter.ghost_metadata,
        "created_at": letter.created_at.isoformat() if letter.created_at else "",
        "read_at": letter.read_at.isoformat() if letter.read_at else None,
    }


# --- Letters ---

@router.post("/letters")
async def send_letter(req: SendLetterRequest, db: Session = Depends(get_db)):
    """Send a Letter to an Echo holder."""
    recipient = _get_user_by_username(req.to_username, db)

    # Build sender address (anonymous visitor for now)
    from_address = f"visitor:{req.from_name}"
    if req.from_email:
        from_address = f"email:{req.from_email}"

    letter = Letter(
        from_address=from_address,
        to_address=recipient.echo_address or f"echo://{recipient.username}@myecho.me",
        subject=req.subject,
        body=req.body,
        transport=LetterTransport.web,
        delivered_at=datetime.now(timezone.utc),
    )
    db.add(letter)
    db.flush()

    # Check Ghost settings — should we draft a reply?
    ghost_settings = db.query(GhostSettings).filter(
        GhostSettings.user_id == recipient.id
    ).first()

    ghost_draft = None
    if ghost_settings and ghost_settings.mode in (GhostMode.draft, GhostMode.auto):
        # Ghost drafts a reply
        profile = db.query(EchoProfile).filter(
            EchoProfile.user_id == recipient.id
        ).first()

        if profile and profile.voice_prompt:
            from echo.engine.ask import respond
            result = respond(
                profile.voice_prompt,
                f"You received a letter:\n\nSubject: {req.subject or '(none)'}\n\n{req.body}\n\n"
                "Write a reply as yourself — warm, personal, in your voice.",
                belief_graph=profile.belief_graph,
            )

            envelope = {
                "schema_version": "0.5",
                "composed_by": "ghost",
                "mode": "draft_approved" if ghost_settings.mode == GhostMode.draft else "auto_sent",
                "style_fingerprint_version": str(profile.version),
                "belief_graph_refs": [],
            }

            ghost_draft = GhostDraft(
                incoming_letter_id=letter.id,
                user_id=recipient.id,
                draft_body=result["response"],
                generated_envelope=envelope,
                status=GhostDraftStatus.pending,
            )
            db.add(ghost_draft)

    db.commit()

    response = _letter_to_response(letter)
    if ghost_draft:
        response["ghost_draft_id"] = str(ghost_draft.id)
        response["ghost_status"] = "draft_pending"

    return response


@router.get("/letters")
async def list_letters(
    username: str,
    unread: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """List letters in a holder's mailbox."""
    user = _get_user_by_username(username, db)
    address = user.echo_address or f"echo://{user.username}@myecho.me"

    query = db.query(Letter).filter(Letter.to_address == address)
    if unread:
        query = query.filter(Letter.read_at.is_(None))

    letters = query.order_by(Letter.created_at.desc()).limit(50).all()
    return [_letter_to_response(l) for l in letters]


@router.get("/letters/{letter_id}")
async def get_letter(letter_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get a single letter."""
    letter = db.query(Letter).filter(Letter.id == letter_id).first()
    if not letter:
        raise HTTPException(status_code=404, detail="Letter not found")
    return _letter_to_response(letter)


@router.post("/letters/{letter_id}/read")
async def mark_read(letter_id: uuid.UUID, db: Session = Depends(get_db)):
    """Mark a letter as read."""
    letter = db.query(Letter).filter(Letter.id == letter_id).first()
    if not letter:
        raise HTTPException(status_code=404, detail="Letter not found")
    letter.read_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "read", "read_at": letter.read_at.isoformat()}


# --- Ghost Drafts ---

@router.get("/ghost/drafts")
async def list_ghost_drafts(
    username: str,
    db: Session = Depends(get_db),
):
    """List pending Ghost drafts for holder review."""
    user = _get_user_by_username(username, db)
    drafts = (
        db.query(GhostDraft)
        .filter(GhostDraft.user_id == user.id, GhostDraft.status == GhostDraftStatus.pending)
        .order_by(GhostDraft.created_at.desc())
        .all()
    )
    return [
        {
            "id": str(d.id),
            "incoming_letter_id": str(d.incoming_letter_id),
            "draft_body": d.draft_body,
            "status": d.status.value,
            "created_at": d.created_at.isoformat() if d.created_at else "",
        }
        for d in drafts
    ]


@router.post("/ghost/drafts/{draft_id}/approve")
async def approve_draft(draft_id: uuid.UUID, db: Session = Depends(get_db)):
    """Approve a Ghost draft — send as-is."""
    draft = db.query(GhostDraft).filter(GhostDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    draft.status = GhostDraftStatus.approved
    draft.holder_decision_at = datetime.now(timezone.utc)

    # Create the reply letter
    incoming = db.query(Letter).filter(Letter.id == draft.incoming_letter_id).first()
    if incoming:
        user = db.query(User).filter(User.id == draft.user_id).first()
        reply = Letter(
            from_address=user.echo_address or f"echo://{user.username}@myecho.me",
            to_address=incoming.from_address,
            subject=f"Re: {incoming.subject}" if incoming.subject else None,
            body=draft.draft_body,
            transport=LetterTransport.web,
            ghost_metadata=draft.generated_envelope,
            in_reply_to_id=incoming.id,
            delivered_at=datetime.now(timezone.utc),
        )
        db.add(reply)

    # Update Ghost stats
    settings = db.query(GhostSettings).filter(GhostSettings.user_id == draft.user_id).first()
    if settings:
        settings.total_drafts_approved += 1
        settings.send_as_written_count += 1

    db.commit()
    return {"status": "approved", "draft_id": str(draft_id)}


@router.post("/ghost/drafts/{draft_id}/edit-and-send")
async def edit_and_send_draft(
    draft_id: uuid.UUID,
    body: str,
    db: Session = Depends(get_db),
):
    """Edit a Ghost draft and send the edited version."""
    draft = db.query(GhostDraft).filter(GhostDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    draft.status = GhostDraftStatus.edited_and_sent
    draft.holder_decision_at = datetime.now(timezone.utc)
    draft.edit_diff = {"original": draft.draft_body, "edited": body}

    incoming = db.query(Letter).filter(Letter.id == draft.incoming_letter_id).first()
    if incoming:
        user = db.query(User).filter(User.id == draft.user_id).first()
        envelope = dict(draft.generated_envelope)
        envelope["composed_by"] = "holder"  # edited by holder
        reply = Letter(
            from_address=user.echo_address or f"echo://{user.username}@myecho.me",
            to_address=incoming.from_address,
            subject=f"Re: {incoming.subject}" if incoming.subject else None,
            body=body,  # edited version
            transport=LetterTransport.web,
            ghost_metadata=envelope,
            in_reply_to_id=incoming.id,
            delivered_at=datetime.now(timezone.utc),
        )
        db.add(reply)

    settings = db.query(GhostSettings).filter(GhostSettings.user_id == draft.user_id).first()
    if settings:
        settings.total_drafts_approved += 1
        # NOT send_as_written — holder edited

    db.commit()
    return {"status": "edited_and_sent", "draft_id": str(draft_id)}


@router.post("/ghost/drafts/{draft_id}/reject")
async def reject_draft(draft_id: uuid.UUID, db: Session = Depends(get_db)):
    """Reject a Ghost draft — feedback signal for StyleFingerprint."""
    draft = db.query(GhostDraft).filter(GhostDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    draft.status = GhostDraftStatus.rejected
    draft.holder_decision_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "rejected", "draft_id": str(draft_id)}


# --- Ghost Settings ---

@router.get("/ghost/settings/{username}")
async def get_ghost_settings(username: str, db: Session = Depends(get_db)):
    """Get Ghost Writer settings for a user."""
    user = _get_user_by_username(username, db)
    settings = db.query(GhostSettings).filter(GhostSettings.user_id == user.id).first()
    if not settings:
        return {"mode": "off", "total_drafts_approved": 0, "send_as_written_count": 0}
    return {
        "mode": settings.mode.value,
        "total_drafts_approved": settings.total_drafts_approved,
        "send_as_written_count": settings.send_as_written_count,
        "auto_eligible": (
            settings.total_drafts_approved >= 30
            and settings.send_as_written_count / max(settings.total_drafts_approved, 1) >= 0.9
        ),
    }


@router.put("/ghost/settings/{username}")
async def update_ghost_settings(
    username: str,
    req: GhostSettingsRequest,
    db: Session = Depends(get_db),
):
    """Update Ghost Writer mode."""
    user = _get_user_by_username(username, db)
    settings = db.query(GhostSettings).filter(GhostSettings.user_id == user.id).first()
    if not settings:
        settings = GhostSettings(user_id=user.id)
        db.add(settings)

    new_mode = GhostMode(req.mode)

    # Auto mode requires eligibility
    if new_mode == GhostMode.auto:
        if settings.total_drafts_approved < 30:
            raise HTTPException(status_code=403, detail="Auto mode requires 30+ approved drafts")
        rate = settings.send_as_written_count / max(settings.total_drafts_approved, 1)
        if rate < 0.9:
            raise HTTPException(status_code=403, detail="Auto mode requires 90%+ send-as-written rate")

    settings.mode = new_mode
    db.commit()
    return {"mode": settings.mode.value}


# --- Guestbook ---

@router.post("/guestbook/{username}")
async def sign_guestbook(
    username: str,
    req: GuestbookRequest,
    db: Session = Depends(get_db),
):
    """Sign someone's guestbook. No Ghost. Human only."""
    user = _get_user_by_username(username, db)
    entry = GuestbookEntry(
        echo_address=user.echo_address or f"echo://{user.username}@myecho.me",
        from_address=f"visitor:{req.from_name}",
        from_name=req.from_name,
        body=req.body,
        from_mood=req.from_mood,
    )
    db.add(entry)
    db.commit()
    return {
        "id": str(entry.id),
        "from_name": entry.from_name,
        "body": entry.body,
        "created_at": entry.created_at.isoformat() if entry.created_at else "",
    }


@router.get("/guestbook/{username}")
async def read_guestbook(username: str, db: Session = Depends(get_db)):
    """Read a user's guestbook. Public."""
    user = _get_user_by_username(username, db)
    address = user.echo_address or f"echo://{user.username}@myecho.me"
    entries = (
        db.query(GuestbookEntry)
        .filter(GuestbookEntry.echo_address == address)
        .order_by(GuestbookEntry.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": str(e.id),
            "from_name": e.from_name,
            "body": e.body,
            "from_mood": e.from_mood,
            "created_at": e.created_at.isoformat() if e.created_at else "",
        }
        for e in entries
    ]
