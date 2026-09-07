import logging
from typing import List, Optional
from sqlalchemy import select, between
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.movie import Movie

logger = logging.getLogger(__name__)
async def fetchCandidateMovies(db:AsyncSession, targetDifficulty:float, limit: int = 50, margin: float=0.15) -> List[Movie]:
    min_diff = max(0.0, targetDifficulty - margin)
    max_diff = min(1.0, targetDifficulty + margin)

    query = ( select(Movie).where(between(Movie.base_difficulty,min_diff,max_diff)).order_by(Movie.imdb_votes.desc()).limit(limit))

    result = await db.execute(query)

    return list(result.scalars().all())

async def recommendMoviesByTaste(db: AsyncSession, tasteVector: List[float], targetDifficulty: float, limit: int = 100, margin: float = 0.20) -> List[Movie]:
    min_diff = max(0.0, targetDifficulty - margin)
    max_diff = min(1.0, targetDifficulty + margin)

    query = ( select(Movie).where(between(Movie.base_difficulty,min_diff,max_diff)).order_by(Movie.semantic_embedding.cosine_distance(tasteVector)).limit(limit))

    result = await db.execute(query)

    return list(result.scalars().all())