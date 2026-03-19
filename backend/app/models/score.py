from typing import Optional

from sqlalchemy import ForeignKey, String, Float, Integer, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Score(Base):
    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"), nullable=False)
    skater_id: Mapped[int] = mapped_column(ForeignKey("skaters.id"), nullable=False)
    segment: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "SP", "FS"
    rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    technical_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    component_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    deductions: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pdf_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    competition: Mapped["Competition"] = relationship(  # noqa: F821
        "Competition", back_populates="scores"
    )
    skater: Mapped["Skater"] = relationship(  # noqa: F821
        "Skater", back_populates="scores"
    )
