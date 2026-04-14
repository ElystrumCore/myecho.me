import enum
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, Integer, DateTime, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echo.database import Base


class ThemeGeneratedBy(str, enum.Enum):
    ai = "ai"
    user = "user"
    template = "template"


class ThemeConfig(Base):
    __tablename__ = "theme_configs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    name: Mapped[str] = mapped_column(String(128), default="Default")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    css_overrides: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_by: Mapped[ThemeGeneratedBy] = mapped_column(
        Enum(ThemeGeneratedBy), default=ThemeGeneratedBy.template
    )
    base_template: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped["User"] = relationship(back_populates="theme")
