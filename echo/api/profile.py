import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from echo.database import get_db
from echo.models.profile import EchoProfile

router = APIRouter()


@router.get("/{user_id}")
async def get_profile(user_id: uuid.UUID, db: Session = Depends(get_db)):
    """Full EchoProfile for a user."""
    profile = db.query(EchoProfile).filter(EchoProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {
        "user_id": user_id,
        "style_fingerprint": profile.style_fingerprint,
        "belief_graph": profile.belief_graph,
        "knowledge_map": profile.knowledge_map,
        "voice_prompt": profile.voice_prompt,
        "version": profile.version,
        "updated_at": profile.updated_at,
    }


@router.get("/{user_id}/fingerprint")
async def get_fingerprint(user_id: uuid.UUID, db: Session = Depends(get_db)):
    """StyleFingerprint only."""
    profile = db.query(EchoProfile).filter(EchoProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile.style_fingerprint


@router.get("/{user_id}/beliefs")
async def get_beliefs(user_id: uuid.UUID, db: Session = Depends(get_db)):
    """BeliefGraph only."""
    profile = db.query(EchoProfile).filter(EchoProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile.belief_graph


@router.get("/{user_id}/knowledge")
async def get_knowledge(user_id: uuid.UUID, db: Session = Depends(get_db)):
    """KnowledgeMap only."""
    profile = db.query(EchoProfile).filter(EchoProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile.knowledge_map


@router.put("/{user_id}/beliefs")
async def update_beliefs(
    user_id: uuid.UUID, beliefs: dict, db: Session = Depends(get_db)
):
    """Manually update/confirm belief positions."""
    profile = db.query(EchoProfile).filter(EchoProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile.belief_graph = beliefs
    profile.version += 1
    db.commit()
    return {"status": "updated", "version": profile.version}


@router.post("/{user_id}/rebuild")
async def rebuild_profile(user_id: uuid.UUID, db: Session = Depends(get_db)):
    """Trigger a full profile rebuild from all ingest sources."""
    profile = db.query(EchoProfile).filter(EchoProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    # TODO: trigger async rebuild pipeline
    return {"status": "rebuild_queued", "user_id": user_id}
