import uuid
import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Integer, SmallInteger, Boolean, String, Float,
    ForeignKey, DateTime, Index, func, text
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.base import Base
class GameplayLevel(Base):
    """
    Unified gameplay level session table.
    Consolidates level_hint_cache, user_gameplay_telemetry, and user_movie_telemetry into a single model.
    Tracks full level lifecycle:
      1. Created with is_completed=False when a level is generated
      2. hints_data is mutated in-place by POST /request-hint
         (Note: remember to call flag_modified(level, "hints_data") before commit)
      3. Completed with is_completed=True and telemetry metrics populated on POST /submit-telemetry
    """
    __tablename__ = "gameplay_levels"
    __table_args__ = (
        # Partial unique index: enforces max 1 active uncompleted level per user.
        Index(
            "idx_user_active_level",
            "user_id",
            unique=True,
            postgresql_where=text("is_completed = FALSE")
        ),
        # Covering index for GET /history pagination
        Index("idx_gameplay_user_history", "user_id", "created_at"),
    )
    level_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    level_number: Mapped[int] = mapped_column(Integer, nullable=False)
    target_difficulty: Mapped[float] = mapped_column(Float, default=0.5)
    session_salt: Mapped[str] = mapped_column(String(64), default="")
    # Ground truth answers for server-side verification: {"S1": "AVATAR", "S2": "INTERSTELLAR", ...}
    solution_map: Mapped[Dict[str, str]] = mapped_column(JSONB, nullable=False)
    # Hint stacks & revealed state: {"S1": {"imdb_id": ..., "revealed_up_to": 1, "hint_stack": [...]}, ...}
    hints_data: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # Level lifecycle state: False while in progress, True upon successful completion
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Telemetry metrics (populated upon completion)
    time_taken_seconds: Mapped[int] = mapped_column(Integer, default=0)
    free_hints_used: Mapped[int] = mapped_column(SmallInteger, default=0)
    premium_hints_used: Mapped[int] = mapped_column(SmallInteger, default=0)
    cell_error_count: Mapped[int] = mapped_column(SmallInteger, default=0)
    # Per-movie solve metrics: [{"imdb_id": "tt0499549", "hints_revealed": 1, "deepest_tier": 5}, ...]
    movie_telemetry: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSONB, nullable=True
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )