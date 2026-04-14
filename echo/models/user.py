import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echo.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(256))
    email: Mapped[str] = mapped_column(String(320), unique=True)
    profile_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    profile: Mapped["EchoProfile"] = relationship(back_populates="user", uselist=False)
    ingest_sources: Mapped[list["IngestSource"]] = relationship(back_populates="user")
    journal_entries: Mapped[list["JournalEntry"]] = relationship(back_populates="user")
    ask_interactions: Mapped[list["AskInteraction"]] = relationship(back_populates="user")
    drift_events: Mapped[list["DriftEvent"]] = relationship(back_populates="user")
    theme: Mapped["ThemeConfig"] = relationship(back_populates="user", uselist=False)
