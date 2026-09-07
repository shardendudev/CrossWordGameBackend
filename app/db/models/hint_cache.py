import uuid
import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Integer, String, ForeignKey, UniqueConstraint, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSON
from app.db.base import Base


class LevelHintCache(Base):
    """
    Stores the full hint stack for each (level, slot) pair server-side.

    Invariant: `revealed_up_to` starts at 1 because the first hint (index 0)
    is already given to the client as `initial_hint` in the LevelResponse.
    Subsequent calls to POST /request-hint reveal index `revealed_up_to`,
    then increment it.
    """
    __tablename__ = "level_hint_cache"
    __table_args__ = (
        UniqueConstraint("level_id", "slot_id", name="uq_level_slot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    level_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    slot_id: Mapped[str] = mapped_column(String(32), nullable=False)
    imdb_id: Mapped[Optional[str]] = mapped_column(String(32), ForeignKey("movies.imdb_id"), nullable=True)
    hint_stack: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False)
    revealed_up_to: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
