import pytest
import pytest_asyncio
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
