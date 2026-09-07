import uuid
from typing import Optional
from sqlalchemy import Integer, Boolean, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base

class UserGameplayTelemetry(Base):
    """Stores overall level completion telemetry (1 row per level session)."""
    __tablename__ = "user_gameplay_telemetry"

    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)
    level_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    time_taken_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    free_hints_used: Mapped[int] = mapped_column(Integer, default=0)
    premium_hints_used: Mapped[int] = mapped_column(Integer, default=0)
    cell_error_count: Mapped[int] = mapped_column(Integer, default=0)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=True)


class UserMovieTelemetry(Base):
    """Stores per-movie hint and solve diagnostic telemetry (N rows per level)."""
    __tablename__ = "user_movie_telemetry"
    __table_args__ = (
        UniqueConstraint("user_id", "level_id", "imdb_id", name="uq_user_level_movie"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)
    level_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    imdb_id: Mapped[str] = mapped_column(String(32), ForeignKey("movies.imdb_id"), nullable=False, index=True)

    hints_revealed: Mapped[int] = mapped_column(Integer, default=0)
    deepest_hint_tier: Mapped[int] = mapped_column(Integer, default=0)


