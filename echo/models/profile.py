from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echo.database import Base

# JSONB on Postgres (indexable, fast), generic JSON on sqlite (test runs).
# Real prod is always Postgres; sqlite is for tests only.
_JSON = JSONB().with_variant(JSON(), "sqlite")

if TYPE_CHECKING:
    from echo.models.user import User


class EchoProfile(Base):
    __tablename__ = "echo_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    style_fingerprint: Mapped[dict] = mapped_column(_JSON, default=dict)
    belief_graph: Mapped[dict] = mapped_column(_JSON, default=dict)
    knowledge_map: Mapped[dict] = mapped_column(_JSON, default=dict)
    voice_prompt: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped[User] = relationship(back_populates="profile")
