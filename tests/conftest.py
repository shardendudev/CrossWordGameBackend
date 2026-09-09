import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.main import app
from app.db.session import get_db, init_db, engine


pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_test_environment():
    """Initializes DB schemas before test module execution."""
    await init_db()
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session():
    """
    Transactional DB Session Fixture.
    Wraps test operations in a connection transaction and rolls back
    when the test finishes, guaranteeing zero database pollution.
    """
    connection = await engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint"
    )

    yield session

    await session.close()
    if transaction.is_active:
        await transaction.rollback()
    await connection.close()


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession):
    """
    FastAPI AsyncClient fixture with get_db dependency overridden to use
    the transactional rollback session.
    """
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()
