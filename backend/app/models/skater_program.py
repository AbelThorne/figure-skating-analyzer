from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, JSON, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SkaterProgram(Base):
    __tablename__ = "skater_programs"
    __table_args__ = (
        UniqueConstraint("skater_id", "segment", name="uq_program_skater_segment"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    skater_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skaters.id", ondelete="CASCADE"), nullable=False
    )
    segment: Mapped[str] = mapped_column(String(4), nullable=False)
    elements: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
