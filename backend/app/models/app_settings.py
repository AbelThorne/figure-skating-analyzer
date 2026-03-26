from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    club_name: Mapped[str] = mapped_column(String(255), nullable=False)
    club_short: Mapped[str] = mapped_column(String(50), nullable=False)
    logo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_season: Mapped[str] = mapped_column(
        String(20), nullable=False, default="2025-2026"
    )
    training_enabled: Mapped[bool] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
