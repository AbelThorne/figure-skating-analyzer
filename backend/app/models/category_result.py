from typing import Optional

from sqlalchemy import ForeignKey, String, Float, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CategoryResult(Base):
    """Overall result for a skater in a competition category.

    Groups together the individual segment scores (e.g. SP + FS) into a
    single combined result with an overall rank and total points.
    For single-segment categories the combined_total equals the segment score.
    """

    __tablename__ = "category_results"
    __table_args__ = (
        UniqueConstraint(
            "competition_id", "skater_id", "category",
            name="uq_catresult_competition_skater_cat",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id"), nullable=False)
    skater_id: Mapped[int] = mapped_column(ForeignKey("skaters.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    overall_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    combined_total: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Number of segments in this category (1 = FS only, 2 = SP+FS)
    segment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Per-segment ranks (nullable — only present for multi-segment categories)
    sp_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fs_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    competition: Mapped["Competition"] = relationship(  # noqa: F821
        "Competition", back_populates="category_results"
    )
    skater: Mapped["Skater"] = relationship(  # noqa: F821
        "Skater", back_populates="category_results"
    )
