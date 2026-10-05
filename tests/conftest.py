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


import json
import uuid
from fastapi import Request
from sqlalchemy import select
from app.core.auth import get_current_token_claims, get_current_user
from app.db.models.user import User

@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession):
    """
    FastAPI AsyncClient fixture with get_db and auth dependencies overridden
    to use the transactional rollback session and mock authentication.
    """
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    current_test_uid = {"uid": None}

    async def _override_get_current_token_claims(request: Request):
        # Generate or reuse unique test UID
        uid = f"test_fb_{uuid.uuid4().hex[:8]}"
        current_test_uid["uid"] = uid
        return {"user_id": uid, "sub": uid, "email": f"{uid}@example.com"}

    async def _override_get_current_user(request: Request):
        # Check if user_id was passed in json body or path
        target_uid = None
        body = await request.body()
        if body:
            try:
                data = json.loads(body)
                if isinstance(data, dict):
                    target_uid = data.get("user_id")
            except Exception:
                pass

        if not target_uid:
            target_uid = request.path_params.get("user_id") or current_test_uid["uid"]

        if target_uid:
            res = await db_session.execute(select(User).where(User.user_id == target_uid))
            user = res.scalars().first()
            if user:
                return user

        # If user not found, create a temporary test user
        fallback_uid = target_uid or f"test_user_{uuid.uuid4().hex[:8]}"
        test_user = User(
            user_id=fallback_uid,
            username=f"user_{fallback_uid[:8]}",
            email=f"{fallback_uid}@example.com",
            current_skill_level=0.200,
            premium_hints_balance=5
        )
        db_session.add(test_user)
        await db_session.flush()
        return test_user

    app.dependency_overrides[get_current_token_claims] = _override_get_current_token_claims
    app.dependency_overrides[get_current_user] = _override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()

