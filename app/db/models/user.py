import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Float, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import ARRAY
from pgvector.sqlalchemy import Vector
from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    current_skill_level: Mapped[float] = mapped_column(Float, default=0.200)
    total_games_played: Mapped[int] = mapped_column(Integer, default=0)
    levels_generated: Mapped[int] = mapped_column(Integer, default=0)
    premium_hints_balance: Mapped[int] = mapped_column(Integer, default=5)
    taste_vector: Mapped[Optional[Vector]] = mapped_column(Vector(1024), nullable=True)

    # Fast in-memory deduplication array
    played_imdb_ids: Mapped[List[str]] = mapped_column(
        ARRAY(String(32)), server_default="{}", default=list, nullable=False
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )




