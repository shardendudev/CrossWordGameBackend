import uuid
from typing import Optional,List
from sqlalchemy import String, Integer, Float
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from app.db.base import Base

class User(Base):
    __tablename__="users"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    username: Mapped[str] = mapped_column(String(128),unique=True, nullable=False)
    current_skill_level: Mapped[float] = mapped_column(Float, default=0.200)
    total_games_played: Mapped[int] = mapped_column(Integer,default=0)
    levels_generated: Mapped[int] = mapped_column(Integer, default=0)
    premium_hints_balance: Mapped[int] = mapped_column(Integer, default=5)
    taste_vector: Mapped[Optional[Vector]] = mapped_column(Vector(1024), nullable=True)



