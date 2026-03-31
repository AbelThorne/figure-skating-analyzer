from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Integer, JSON, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SelfEvaluation(Base):
    __tablename__ = "self_evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    skater_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skaters.id", ondelete="CASCADE"), nullable=False
    )
    mood_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("training_moods.id", ondelete="SET NULL"), nullable=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    element_ratings: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    shared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
