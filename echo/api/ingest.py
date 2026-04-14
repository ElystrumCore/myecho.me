import uuid

from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session

from echo.database import get_db
from echo.models.ingest import IngestSource, SourceType, IngestStatus

router = APIRouter()


@router.post("/linkedin/messages")
async def ingest_linkedin_messages(
    user_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload LinkedIn messages.csv for voice/tone analysis."""
    source = IngestSource(
        user_id=user_id,
        source_type=SourceType.linkedin_messages,
        file_path=file.filename or "messages.csv",
        status=IngestStatus.pending,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return {"source_id": source.id, "status": source.status}


@router.post("/linkedin/endorsements")
async def ingest_linkedin_endorsements(
    user_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload LinkedIn endorsements CSV for KnowledgeMap."""
    source = IngestSource(
        user_id=user_id,
        source_type=SourceType.linkedin_endorsements,
        file_path=file.filename or "endorsements.csv",
        status=IngestStatus.pending,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return {"source_id": source.id, "status": source.status}


@router.post("/linkedin/connections")
async def ingest_linkedin_connections(
    user_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload LinkedIn connections CSV for network graph."""
    source = IngestSource(
        user_id=user_id,
        source_type=SourceType.linkedin_connections,
        file_path=file.filename or "connections.csv",
        status=IngestStatus.pending,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return {"source_id": source.id, "status": source.status}


@router.post("/career")
async def ingest_career(
    user_id: uuid.UUID,
    career_data: dict,
    db: Session = Depends(get_db),
):
    """Submit career history as structured JSON."""
    source = IngestSource(
        user_id=user_id,
        source_type=SourceType.career_history,
        file_path="career_history.json",
        status=IngestStatus.pending,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return {"source_id": source.id, "status": source.status}


@router.post("/writing")
async def ingest_writing(
    user_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload writing samples."""
    source = IngestSource(
        user_id=user_id,
        source_type=SourceType.writing_sample,
        file_path=file.filename or "writing_sample.txt",
        status=IngestStatus.pending,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return {"source_id": source.id, "status": source.status}


@router.post("/declaration")
async def ingest_declaration(
    user_id: uuid.UUID,
    text: str,
    db: Session = Depends(get_db),
):
    """Submit a voice declaration — free-form text to seed positions."""
    source = IngestSource(
        user_id=user_id,
        source_type=SourceType.voice_declaration,
        file_path="declaration.txt",
        status=IngestStatus.pending,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return {"source_id": source.id, "status": source.status}


@router.get("/status/{user_id}")
async def ingest_status(user_id: uuid.UUID, db: Session = Depends(get_db)):
    """Check ingest pipeline status for a user."""
    sources = db.query(IngestSource).filter(IngestSource.user_id == user_id).all()
    return {
        "user_id": user_id,
        "sources": [
            {
                "id": s.id,
                "type": s.source_type,
                "status": s.status,
                "record_count": s.record_count,
                "created_at": s.created_at,
                "processed_at": s.processed_at,
            }
            for s in sources
        ],
    }
