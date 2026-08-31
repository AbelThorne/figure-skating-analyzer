# backend/app/models/french_ranking_entry.py
"""Cache local du French Ranking : une ligne = un patineur, remplacé en bloc à
chaque rafraîchissement (pas de diff/hash).

Contrairement au projet ligue, pas de dimension saison : une instance SkateLab
n'a qu'une saison courante (`app_settings.current_season`).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FrenchRankingEntry(Base):
    __tablename__ = "french_ranking_entries"
    __table_args__ = (Index("ix_french_ranking_entries_licence", "licence_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    licence_number: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sex: Mapped[str | None] = mapped_column(String(1), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    club_name_raw: Mapped[str] = mapped_column(String(255), nullable=False)
    has_competition_licence: Mapped[bool] = mapped_column(Boolean, nullable=False)
    filiere: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ligue_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
