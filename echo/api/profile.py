import json
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from echo.database import get_db
from echo.models.profile import EchoProfile
from echo.models.user import User

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


class IngestConversationsRequest(BaseModel):
    source_type: str  # "claude" or "chatgpt"


@router.post("/{user_id}/ingest/conversations")
async def ingest_conversations(
    user_id: uuid.UUID,
    source_type: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a Claude or ChatGPT conversations.json and process it.

    Extracts user messages, builds StyleFingerprint + BeliefGraph,
    merges into the existing profile, recompiles voice prompt.
    """
    from echo.ingest.conversations import (
        process_conversation_export,
        merge_fingerprints,
    )
    from echo.profile.compiler import compile_voice_prompt

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = db.query(EchoProfile).filter(EchoProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found — register first")

    # Parse uploaded JSON
    raw = await file.read()
    data = json.loads(raw)

    # Process
    messages, fingerprint, beliefs = process_conversation_export(data, source_type)

    if not messages:
        raise HTTPException(status_code=400, detail=f"No user messages found in {source_type} export")

    # Merge with existing profile
    existing_fp = profile.style_fingerprint or {}
    if existing_fp.get("structure", {}).get("total_messages", 0) > 0:
        merged_fp = merge_fingerprints([existing_fp, fingerprint])
    else:
        merged_fp = fingerprint

    # Merge belief graphs
    existing_topics = {t["name"]: t for t in (profile.belief_graph or {}).get("topics", [])}
    for topic in beliefs.get("topics", []):
        name = topic["name"]
        if name in existing_topics:
            existing_topics[name]["mention_count"] += topic["mention_count"]
            existing_topics[name]["confidence"] = min(1.0, existing_topics[name]["mention_count"] / 50)
        else:
            existing_topics[name] = topic
    merged_beliefs = {
        "topics": sorted(existing_topics.values(), key=lambda t: t["mention_count"], reverse=True),
        "total_topics": len(existing_topics),
        "total_messages_analyzed": (
            (profile.belief_graph or {}).get("total_messages_analyzed", 0)
            + beliefs.get("total_messages_analyzed", 0)
        ),
    }

    # Compile voice prompt
    voice_prompt = compile_voice_prompt(
        display_name=user.display_name,
        style_fingerprint=merged_fp,
        belief_graph=merged_beliefs,
        knowledge_map=profile.knowledge_map,
    )

    # Update profile
    profile.style_fingerprint = merged_fp
    profile.belief_graph = merged_beliefs
    profile.voice_prompt = voice_prompt
    profile.version += 1
    db.commit()

    return {
        "status": "processed",
        "messages_extracted": len(messages),
        "total_messages": merged_fp.get("structure", {}).get("total_messages", 0),
        "voice_prompt_length": len(voice_prompt),
        "profile_version": profile.version,
        "topics": [t["name"] for t in merged_beliefs.get("topics", [])[:5]],
    }


@router.post("/{user_id}/rebuild")
async def rebuild_profile(user_id: uuid.UUID, db: Session = Depends(get_db)):
    """Trigger a full profile rebuild — recompile voice prompt from current data."""
    from echo.profile.compiler import compile_voice_prompt

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = db.query(EchoProfile).filter(EchoProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    voice_prompt = compile_voice_prompt(
        display_name=user.display_name,
        style_fingerprint=profile.style_fingerprint or {},
        belief_graph=profile.belief_graph or {},
        knowledge_map=profile.knowledge_map,
    )

    profile.voice_prompt = voice_prompt
    profile.version += 1
    db.commit()

    return {
        "status": "rebuilt",
        "voice_prompt_length": len(voice_prompt),
        "profile_version": profile.version,
    }
