import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from echo.database import get_db
from echo.models.journal import JournalEntry, AskInteraction, DriftEvent, EntryStatus

router = APIRouter()


@router.get("/{user_id}/overview")
async def dashboard_overview(user_id: uuid.UUID, db: Session = Depends(get_db)):
    """Stats, pending items, drift alerts."""
    pending_count = (
        db.query(JournalEntry)
        .filter(
            JournalEntry.user_id == user_id,
            JournalEntry.status == EntryStatus.pending_review,
        )
        .count()
    )
    published_count = (
        db.query(JournalEntry)
        .filter(
            JournalEntry.user_id == user_id,
            JournalEntry.status == EntryStatus.published,
        )
        .count()
    )
    ask_count = (
        db.query(AskInteraction).filter(AskInteraction.user_id == user_id).count()
    )
    unacknowledged_drift = (
        db.query(DriftEvent)
        .filter(DriftEvent.user_id == user_id, DriftEvent.acknowledged == False)
        .count()
    )
    return {
        "user_id": user_id,
        "pending_drafts": pending_count,
        "published_entries": published_count,
        "total_asks": ask_count,
        "unacknowledged_drift_events": unacknowledged_drift,
    }


@router.get("/{user_id}/drift")
async def list_drift(user_id: uuid.UUID, db: Session = Depends(get_db)):
    """Drift events for a user."""
    events = (
        db.query(DriftEvent)
        .filter(DriftEvent.user_id == user_id)
        .order_by(DriftEvent.created_at.desc())
        .all()
    )
    return [
        {
            "id": e.id,
            "topic": e.topic,
            "original_position": e.original_position,
            "current_position": e.current_position,
            "drift_score": e.drift_score,
            "acknowledged": e.acknowledged,
            "created_at": e.created_at,
        }
        for e in events
    ]


@router.put("/{user_id}/drift/{event_id}/acknowledge")
async def acknowledge_drift(
    user_id: uuid.UUID, event_id: uuid.UUID, db: Session = Depends(get_db)
):
    """Acknowledge a drift event."""
    event = (
        db.query(DriftEvent)
        .filter(DriftEvent.id == event_id, DriftEvent.user_id == user_id)
        .first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="Drift event not found")
    event.acknowledged = True
    db.commit()
    return {"event_id": event.id, "acknowledged": True}
