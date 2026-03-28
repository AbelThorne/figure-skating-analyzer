from datetime import date, datetime
from typing import Optional

from sqlalchemy import String, Date, Text, JSON, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Competition(Base):
    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    date_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    season: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    discipline: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    rink: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ligue: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    competition_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    metadata_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    polling_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    polling_activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_import_log: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    scores: Mapped[list["Score"]] = relationship(  # noqa: F821
        "Score", back_populates="competition", cascade="all, delete-orphan"
    )
    category_results: Mapped[list["CategoryResult"]] = relationship(  # noqa: F821
        "CategoryResult", back_populates="competition", cascade="all, delete-orphan"
    )
