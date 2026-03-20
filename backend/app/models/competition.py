from datetime import date
from typing import Optional

from sqlalchemy import String, Date, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Competition(Base):
    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    season: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    discipline: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_import_log: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    scores: Mapped[list["Score"]] = relationship(  # noqa: F821
        "Score", back_populates="competition", cascade="all, delete-orphan"
    )
