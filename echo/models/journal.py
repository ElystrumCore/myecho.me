import enum
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, Float, Boolean, DateTime, Enum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echo.database import Base


class EntryStatus(str, enum.Enum):
    draft = "draft"
    pending_review = "pending_review"
    published = "published"
    archived = "archived"


class GeneratedBy(str, enum.Enum):
    echo = "echo"
    user = "user"
    hybrid = "hybrid"


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(512))
    content: Mapped[str] = mapped_column(Text)
    topic_tags: Mapped[list] = mapped_column(ARRAY(String), default=list)
    status: Mapped[EntryStatus] = mapped_column(Enum(EntryStatus), default=EntryStatus.draft)
    generated_by: Mapped[GeneratedBy] = mapped_column(Enum(GeneratedBy), default=GeneratedBy.echo)
    generation_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="journal_entries")


class AskInteraction(Base):
    __tablename__ = "ask_interactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    visitor_id: Mapped[str] = mapped_column(String(128))
    question: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text)
    belief_refs: Mapped[list] = mapped_column(ARRAY(String), default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="ask_interactions")


class DriftEvent(Base):
    __tablename__ = "drift_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    topic: Mapped[str] = mapped_column(String(256))
    original_position: Mapped[str] = mapped_column(Text)
    current_position: Mapped[str] = mapped_column(Text)
    drift_score: Mapped[float] = mapped_column(Float, default=0.0)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="drift_events")
