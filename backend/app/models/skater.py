from typing import Optional

from sqlalchemy import String, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Skater(Base):
    __tablename__ = "skaters"
    __table_args__ = (
        UniqueConstraint("first_name", "last_name", name="uq_skater_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    last_name: Mapped[str] = mapped_column(String(255), nullable=False)
    nationality: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    club: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    birth_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    scores: Mapped[list["Score"]] = relationship(  # noqa: F821
        "Score", back_populates="skater"
    )
    category_results: Mapped[list["CategoryResult"]] = relationship(  # noqa: F821
        "CategoryResult", back_populates="skater"
    )

    @property
    def display_name(self) -> str:
        """Formatted display name: 'Firstname LASTNAME'."""
        if self.first_name:
            return f"{self.first_name} {self.last_name}"
        return self.last_name
