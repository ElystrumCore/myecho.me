"""Exchange models — Letters, GhostEnvelope, GhostDraft, Guestbook."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echo.database import Base

if TYPE_CHECKING:
    from echo.models.user import User


# --- Enums ---

class LetterTransport(str, enum.Enum):
    web = "web"
    email = "email"
    a2a = "a2a"
    future = "future"


class GhostMode(str, enum.Enum):
    off = "off"
    draft = "draft"
    auto = "auto"


class GhostComposedBy(str, enum.Enum):
    holder = "holder"
    ghost = "ghost"


class GhostDraftStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    edited_and_sent = "edited_and_sent"
    rejected = "rejected"
    expired = "expired"


# --- Letter ---

class Letter(Base):
    __tablename__ = "letters"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    from_address: Mapped[str] = mapped_column(String(256))  # echo://{uin}@myecho.me
    to_address: Mapped[str] = mapped_column(String(256), index=True)
    subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    transport: Mapped[LetterTransport] = mapped_column(
        Enum(LetterTransport), default=LetterTransport.web
    )
    # Threading
    thread_root_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("letters.id"), nullable=True
    )
    in_reply_to_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("letters.id"), nullable=True
    )
    # Ghost metadata (JSONB — versioned, extensible per spec)
    ghost_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Delivery state
    sender_mood: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# --- GhostDraft ---

class GhostDraft(Base):
    __tablename__ = "ghost_drafts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    incoming_letter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("letters.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    draft_body: Mapped[str] = mapped_column(Text)
    # GhostEnvelope as JSONB (versioned, extensible)
    generated_envelope: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[GhostDraftStatus] = mapped_column(
        Enum(GhostDraftStatus), default=GhostDraftStatus.pending
    )
    holder_decision_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    edit_diff: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    incoming_letter: Mapped[Letter] = relationship(foreign_keys=[incoming_letter_id])


# --- GhostSettings ---

class GhostSettings(Base):
    __tablename__ = "ghost_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), primary_key=True
    )
    mode: Mapped[GhostMode] = mapped_column(Enum(GhostMode), default=GhostMode.off)
    # Per-correspondent overrides stored as JSONB
    # {"echo://2@myecho.me": "draft", "echo://5@myecho.me": "auto"}
    correspondent_overrides: Mapped[dict] = mapped_column(JSONB, default=dict)
    total_drafts_approved: Mapped[int] = mapped_column(Integer, default=0)
    send_as_written_count: Mapped[int] = mapped_column(Integer, default=0)
    auto_consent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


# --- Guestbook ---

class GuestbookEntry(Base):
    __tablename__ = "guestbook_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    echo_address: Mapped[str] = mapped_column(String(256), index=True)  # whose guestbook
    from_address: Mapped[str] = mapped_column(String(256))
    from_name: Mapped[str] = mapped_column(String(256), default="")
    body: Mapped[str] = mapped_column(String(280))  # enforce short limit
    from_mood: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
