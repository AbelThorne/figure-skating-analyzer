from typing import Optional

from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Skater(Base):
    __tablename__ = "skaters"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    nationality: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    club: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    birth_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    scores: Mapped[list["Score"]] = relationship(  # noqa: F821
        "Score", back_populates="skater"
    )
