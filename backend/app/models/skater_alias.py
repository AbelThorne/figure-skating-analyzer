from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SkaterAlias(Base):
    __tablename__ = "skater_aliases"
    __table_args__ = (
        UniqueConstraint("first_name", "last_name", name="uq_skater_alias_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    last_name: Mapped[str] = mapped_column(String(255), nullable=False)
    skater_id: Mapped[int] = mapped_column(
        ForeignKey("skaters.id", ondelete="CASCADE"), nullable=False
    )
