import uuid
from typing import Optional
from sqlalchemy import Integer, Boolean, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base

class UserGameplayTelemetry(Base):
    __tablename__="user_gameplay_telemetry"

    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.user_id"),nullable=False, index=True)
    level_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    imdb_id: Mapped[Optional[str]] = mapped_column(String(32), ForeignKey("movies.imdb_id"),nullable=True)

    time_taken_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    free_hints_used: Mapped[int] = mapped_column(Integer, default=0)
    premium_hints_used: Mapped[int] = mapped_column(Integer, default=0)
    cell_error_count: Mapped[int] = mapped_column(Integer, default=0)
    is_completed: Mapped[bool] = mapped_column(Boolean,default=True)
