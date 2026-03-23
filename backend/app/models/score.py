from datetime import date
from typing import Optional

from sqlalchemy import Date, ForeignKey, String, Float, Integer, JSON, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (
        UniqueConstraint("competition_id", "skater_id", "category", "segment", name="uq_score_competition_skater_cat_seg"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"), nullable=False)
    skater_id: Mapped[int] = mapped_column(ForeignKey("skaters.id"), nullable=False)
    segment: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    starting_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    technical_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    component_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    deductions: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    components: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    elements: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    event_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    pdf_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    skating_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    age_group: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    competition: Mapped["Competition"] = relationship(  # noqa: F821
        "Competition", back_populates="scores"
    )
    skater: Mapped["Skater"] = relationship(  # noqa: F821
        "Skater", back_populates="scores"
    )
