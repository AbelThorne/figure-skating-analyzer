from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TrainingMood(Base):
    __tablename__ = "training_moods"
    __table_args__ = (
        UniqueConstraint("skater_id", "date", name="uq_mood_skater_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    skater_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skaters.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
