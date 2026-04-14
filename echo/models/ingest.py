from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echo.database import Base

if TYPE_CHECKING:
    from echo.models.user import User


class SourceType(str, enum.Enum):
    linkedin_messages = "linkedin_messages"
    linkedin_endorsements = "linkedin_endorsements"
    linkedin_connections = "linkedin_connections"
    career_history = "career_history"
    writing_sample = "writing_sample"
    voice_declaration = "voice_declaration"


class IngestStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class IngestSource(Base):
    __tablename__ = "ingest_sources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType))
    file_path: Mapped[str] = mapped_column(String(1024))
    status: Mapped[IngestStatus] = mapped_column(Enum(IngestStatus), default=IngestStatus.pending)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship(back_populates="ingest_sources")
