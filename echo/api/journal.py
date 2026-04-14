from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from echo.database import get_db
from echo.models.user import User
from echo.models.journal import JournalEntry, EntryStatus
from echo.models.profile import EchoProfile

router = APIRouter()


class PublicAskRequest(BaseModel):
    question: str


def _get_user_by_username(username: str, db: Session) -> User:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/{username}")
async def get_journal(username: str, db: Session = Depends(get_db)):
    """Published journal entries for a user."""
    user = _get_user_by_username(username, db)
    entries = (
        db.query(JournalEntry)
        .filter(
            JournalEntry.user_id == user.id,
            JournalEntry.status == EntryStatus.published,
        )
        .order_by(JournalEntry.published_at.desc())
        .all()
    )
    return {
        "username": username,
        "display_name": user.display_name,
        "entries": [
            {
                "id": e.id,
                "title": e.title,
                "content": e.content,
                "topic_tags": e.topic_tags,
                "published_at": e.published_at,
            }
            for e in entries
        ],
    }


@router.get("/{username}/entry/{entry_id}")
async def get_entry(username: str, entry_id: str, db: Session = Depends(get_db)):
    """Single published journal entry."""
    user = _get_user_by_username(username, db)
    entry = (
        db.query(JournalEntry)
        .filter(
            JournalEntry.id == entry_id,
            JournalEntry.user_id == user.id,
            JournalEntry.status == EntryStatus.published,
        )
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {
        "id": entry.id,
        "title": entry.title,
        "content": entry.content,
        "topic_tags": entry.topic_tags,
        "published_at": entry.published_at,
        "generated_by": entry.generated_by,
    }


@router.get("/{username}/positions")
async def get_positions(username: str, db: Session = Depends(get_db)):
    """Public BeliefGraph summary."""
    user = _get_user_by_username(username, db)
    profile = db.query(EchoProfile).filter(EchoProfile.user_id == user.id).first()
    if not profile:
        return {"username": username, "positions": []}
    return {"username": username, "belief_graph": profile.belief_graph}


@router.get("/{username}/timeline")
async def get_timeline(username: str, db: Session = Depends(get_db)):
    """Career + topic timeline."""
    user = _get_user_by_username(username, db)
    profile = db.query(EchoProfile).filter(EchoProfile.user_id == user.id).first()
    knowledge = profile.knowledge_map if profile else {}
    return {"username": username, "knowledge_map": knowledge}


@router.post("/{username}/ask")
async def public_ask(
    username: str,
    request: PublicAskRequest,
    db: Session = Depends(get_db),
):
    """Public Ask endpoint — visitor asks, Echo responds."""
    user = _get_user_by_username(username, db)
    profile = db.query(EchoProfile).filter(EchoProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Echo not ready yet")

    # TODO: call engine.ask.respond
    return {
        "question": request.question,
        "response": "[response pending — engine not yet wired]",
        "confidence": 0.0,
    }
