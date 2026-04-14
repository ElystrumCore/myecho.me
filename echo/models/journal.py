from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echo.database import Base

if TYPE_CHECKING:
    from echo.models.user import User


class EntryStatus(str, enum.Enum):
    draft = "draft"
    pending_review = "pending_review"
    published = "published"
    archived = "archived"


class EntrySecurity(str, enum.Enum):
    public = "public"
    private = "private"
    selected = "selected"


class GeneratedBy(str, enum.Enum):
    echo = "echo"
    user = "user"
    hybrid = "hybrid"


class PropDataType(str, enum.Enum):
    string = "string"
    string_array = "string_array"
    float_ = "float"
    int_ = "int"
    boolean = "boolean"
    json = "json"


# --- JournalEntry: lean metadata, LJ log2 pattern ---

class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(512))
    status: Mapped[EntryStatus] = mapped_column(Enum(EntryStatus), default=EntryStatus.draft)
    security: Mapped[EntrySecurity] = mapped_column(
        Enum(EntrySecurity), default=EntrySecurity.public
    )
    generated_by: Mapped[GeneratedBy] = mapped_column(Enum(GeneratedBy), default=GeneratedBy.echo)
    generation_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    # LJ pattern: date denormalization for archive/timeline queries
    pub_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pub_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pub_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped[User] = relationship(back_populates="journal_entries")
    content: Mapped[JournalContent] = relationship(
        back_populates="entry", uselist=False, cascade="all, delete-orphan"
    )
    props: Mapped[list[EntryProp]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )
    comments: Mapped[list[Comment]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )


# --- JournalContent: heavy body text, LJ logtext2 pattern ---

class JournalContent(Base):
    __tablename__ = "journal_content"

    entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("journal_entries.id"), primary_key=True
    )
    body: Mapped[str] = mapped_column(Text, default="")
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)

    entry: Mapped[JournalEntry] = relationship(back_populates="content")


# --- EntryProp: extensible metadata, LJ logprop2 pattern ---

class EntryProp(Base):
    __tablename__ = "entry_props"

    entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("journal_entries.id"), primary_key=True
    )
    prop_key: Mapped[str] = mapped_column(
        String(64), ForeignKey("prop_catalog.key"), primary_key=True
    )
    prop_value: Mapped[str] = mapped_column(Text, default="")

    entry: Mapped[JournalEntry] = relationship(back_populates="props")
    catalog_entry: Mapped[PropCatalog] = relationship()


# --- PropCatalog: registry of known property types, LJ logproplist pattern ---

class PropCatalog(Base):
    __tablename__ = "prop_catalog"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    data_type: Mapped[PropDataType] = mapped_column(Enum(PropDataType))
    description: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# Default props to seed at init
DEFAULT_PROPS = [
    ("topic_tags", PropDataType.string_array, "Topics this entry relates to"),
    ("echo_mood", PropDataType.string, "Inferred emotional state when generating"),
    ("echo_confidence", PropDataType.float_, "How confident Echo was in this generation"),
    ("belief_refs", PropDataType.string_array, "Which BeliefGraph nodes were drawn on"),
    ("generation_model", PropDataType.string, "Which LLM was used"),
    ("revision_count", PropDataType.int_, "How many times owner edited before publishing"),
]


# --- Comment: threaded comments on entries, LJ talk2 pattern ---

class CommentStatus(str, enum.Enum):
    active = "active"
    hidden = "hidden"       # owner-moderated
    deleted = "deleted"


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("journal_entries.id"), index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("comments.id"), nullable=True
    )
    # LJ talk2 pattern: nodetype makes comments attachable to different content types
    node_type: Mapped[str] = mapped_column(String(32), default="entry")
    # Visitor identity — no account required
    visitor_id: Mapped[str] = mapped_column(String(128))   # session hash
    author_name: Mapped[str] = mapped_column(String(128))  # display name they provide
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[CommentStatus] = mapped_column(
        Enum(CommentStatus), default=CommentStatus.active
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    entry: Mapped[JournalEntry] = relationship(back_populates="comments")
    parent: Mapped[Comment | None] = relationship(
        remote_side="Comment.id", back_populates="replies"
    )
    replies: Mapped[list[Comment]] = relationship(back_populates="parent")


# --- AskInteraction: with LJ nodetype threading ---

class AskInteraction(Base):
    __tablename__ = "ask_interactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    visitor_id: Mapped[str] = mapped_column(String(128))
    question: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text)
    node_type: Mapped[str] = mapped_column(String(32), default="ask")
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ask_interactions.id"), nullable=True
    )
    belief_refs: Mapped[list] = mapped_column(ARRAY(String), default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="ask_interactions")
    parent: Mapped[AskInteraction | None] = relationship(remote_side="AskInteraction.id")


# --- DriftEvent: with echo_mood_at_drift ---

class DriftEvent(Base):
    __tablename__ = "drift_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    topic: Mapped[str] = mapped_column(String(256))
    original_position: Mapped[str] = mapped_column(Text)
    current_position: Mapped[str] = mapped_column(Text)
    drift_score: Mapped[float] = mapped_column(Float, default=0.0)
    echo_mood_at_drift: Mapped[str | None] = mapped_column(String(128), nullable=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="drift_events")
