from typing import Optional
from sqlalchemy import String, BigInteger,Integer, Float, Text 
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from app.db.base import Base


class Movie(Base):
    __tablename__ = "movies"

    #primary key and metadata
    imdb_id: Mapped[str] = mapped_column(String(32),primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255),nullable=False)
    clean_title: Mapped[str] = mapped_column(String(255), nullable= False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    genres: Mapped[Optional[str]] = mapped_column(String(255),nullable=True)
    director: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    actors: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_rating: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    poster_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    budget: Mapped[Optional[int]] = mapped_column(BigInteger, default=0)
    revenue: Mapped[Optional[int]] = mapped_column(BigInteger, default=0)
    imdb_rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    imdb_votes: Mapped[int] = mapped_column(Integer, default=0)

    #hints
    character_hints: Mapped[Optional[str]] = mapped_column(Text,nullable=True)
    plot_hints: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    famous_scene_hints: Mapped[Optional[str]] = mapped_column(Text,nullable=True)
    trivia_hints: Mapped[Optional[str]] = mapped_column(Text,nullable=True)
    theme_hints:Mapped[Optional[str]] = mapped_column(Text,nullable=True)
    famous_props_macguffins: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cultural_impact_legacy: Mapped[Optional[str]] = mapped_column(Text,nullable=True)
    iconic_dialogue: Mapped[Optional[str]] = mapped_column(Text,nullable=True)
    awards_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    era_buckets: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    #Base difficulty & 1024-dim vector embedding
    base_difficulty: Mapped[float] = mapped_column(Float, default=0.5, index=True)
    semantic_embedding: Mapped[Optional[Vector]] = mapped_column(Vector(1024), nullable=True)
    


