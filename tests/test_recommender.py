import pytest
import pytest_asyncio
from sqlalchemy import select
from app.db.models.movie import Movie
from app.engine.difficulty import updateTasteVector
from app.db.session import AsyncSessionLocal, engine
from app.engine.recommender import fetchCandidateMovies, recommendMoviesByTaste

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(autouse=True, scope="module")
async def cleanup_engine():
    yield
    await engine.dispose()


async def test_fetchCandidateMovies():
    async with AsyncSessionLocal() as session:
        # Fetch 1 sample movie to get a 1024-dim test vector
        sample = await fetchCandidateMovies(session, targetDifficulty=0.35, limit=1)

        test_vector = sample[0].semantic_embedding

        recs = await recommendMoviesByTaste(session, test_vector, targetDifficulty=0.35, limit=5, margin=0.15)

        assert len(recs) > 0
        print(f"\n [Recommender Test] Top 5 vector similar movies for {sample[0].title}")

        for m in recs:
            print(f"  • {m.title}")

async def test_real_db_taste_evolution():
    async with AsyncSessionLocal() as session:
        # 1. Fetch 3 real Sci-Fi movies that have embeddings
        scifi_res = await session.execute(
            select(Movie)
            .where(Movie.genres.ilike("%Sci-Fi%"), Movie.semantic_embedding.isnot(None))
            .limit(3)
        )
        scifi_movies = scifi_res.scalars().all()
        assert len(scifi_movies) >= 3

        print(f"\n[Level 1: Sci-Fi Movies Solved]")
        for m in scifi_movies:
            print(f"  • {m.title} ({m.genres})")

        # 2. Level 1 Centroid Update (Cold Start)
        scifi_vectors = [list(m.semantic_embedding) for m in scifi_movies]
        taste_v1 = updateTasteVector(currentVector=None, solvedMovieVector=scifi_vectors, beta=0.85)

        # 3. Query pgvector recommendations for Level 1 taste
        recs_v1 = await recommendMoviesByTaste(session, tasteVector=taste_v1, targetDifficulty=0.40, limit=5)
        print(f"\n[Top 5 Recommendations after Level 1 (Sci-Fi)]")
        for m in recs_v1:
            print(f"  -> {m.title} ({m.genres})")

        # 4. Level 2: Player plays a Romance level
        romance_res = await session.execute(
            select(Movie)
            .where(Movie.genres.ilike("%Romance%"), Movie.semantic_embedding.isnot(None))
            .limit(3)
        )
        romance_movies = romance_res.scalars().all()
        assert len(romance_movies) >= 3

        print(f"\n[Level 2: Romance Movies Solved]")
        for m in romance_movies:
            print(f"  • {m.title} ({m.genres})")

        # 5. EMA Blend with beta = 0.85
        romance_vectors = [list(m.semantic_embedding) for m in romance_movies]
        taste_v2 = updateTasteVector(currentVector=taste_v1, solvedMovieVector=romance_vectors, beta=0.85)

        # 6. Query pgvector recommendations after Level 2
        recs_v2 = await recommendMoviesByTaste(session, tasteVector=taste_v2, targetDifficulty=0.40, limit=5)
        print(f"\n[Top 5 Recommendations after Level 2 (85% Sci-Fi + 15% Romance)]")
        for m in recs_v2:
            print(f"  -> {m.title} ({m.genres})")

        assert len(recs_v2) > 0

