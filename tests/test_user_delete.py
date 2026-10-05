import uuid
import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import select

from app.main import app
from app.db.models.user import User
from app.db.models.gameplay import GameplayLevel
from app.core.auth import get_current_user
from app.api.v1.endpoints.users import deleteAccount

pytestmark = pytest.mark.asyncio(loop_scope="module")


async def test_delete_account_unit_success():
    """Unit test: Verify deleteAccount deletes dependent data, calls Firebase Admin SDK, and commits."""
    user = User(user_id="test_uid_999", username="player_999", email="player@example.com")
    db = AsyncMock()

    with patch("app.api.v1.endpoints.users.delete_firebase_user") as mock_fb:
        await deleteAccount(current_user=user, db=db)

        # 1. Firebase deletion called with user ID
        mock_fb.assert_called_once_with("test_uid_999")
        # 2. User delete and flush called
        db.delete.assert_called_once_with(user)
        assert db.flush.called
        # 3. Transaction committed
        assert db.commit.called
        assert not db.rollback.called


async def test_delete_account_firebase_failure_triggers_rollback():
    """Unit test: Verify that if Firebase Admin SDK fails, Postgres transaction is rolled back."""
    user = User(user_id="test_uid_error", username="player_err", email="err@example.com")
    db = AsyncMock()

    with patch("app.api.v1.endpoints.users.delete_firebase_user", side_effect=Exception("Firebase Auth Connection Timeout")):
        with pytest.raises(HTTPException) as exc_info:
            await deleteAccount(current_user=user, db=db)

        assert exc_info.value.status_code == 500
        assert "Firebase Auth Connection Timeout" in exc_info.value.detail
        # Ensure commit was NOT called and rollback was executed
        assert not db.commit.called
        assert db.rollback.called


async def test_delete_account_e2e_postgres(async_client: AsyncClient, db_session):
    """
    E2E integration test against Postgres:
    1. Create a real User and GameplayLevel record in DB.
    2. Override get_current_user to simulate the authenticated session.
    3. Call DELETE /api/v1/users/me.
    4. Assert response is HTTP 204 No Content.
    5. Verify User and GameplayLevel rows are cascade-deleted from Postgres.
    """
    test_uid = f"e2e_uid_{uuid.uuid4().hex[:8]}"
    test_user = User(
        user_id=test_uid,
        username=f"e2e_user_{uuid.uuid4().hex[:6]}",
        email="e2e@example.com",
        current_skill_level=0.200,
        premium_hints_balance=5
    )
    db_session.add(test_user)
    await db_session.flush()

    test_level_id = uuid.uuid4()
    test_level = GameplayLevel(
        level_id=test_level_id,
        user_id=test_uid,
        level_number=1,
        target_difficulty=0.5,
        session_salt="test_salt_123",
        solution_map={"S1": "AVATAR"},
        hints_data={"S1": {"revealed_up_to": 1, "hint_stack": [{"tier": 1, "text": "test"}]}},
        time_taken_seconds=42,
        is_completed=True
    )
    db_session.add(test_level)
    await db_session.flush()

    # Verify rows exist
    res_user = await db_session.execute(select(User).where(User.user_id == test_uid))
    assert res_user.scalars().first() is not None

    res_level = await db_session.execute(select(GameplayLevel).where(GameplayLevel.user_id == test_uid))
    assert res_level.scalars().first() is not None

    # Override get_current_user dependency to return our test user
    app.dependency_overrides[get_current_user] = lambda: test_user

    try:
        with patch("app.api.v1.endpoints.users.delete_firebase_user") as mock_fb:
            response = await async_client.delete("/api/v1/users/me")
            assert response.status_code == 204
            mock_fb.assert_called_once_with(test_uid)

            # Verify rows are deleted from Postgres via CASCADE
            verify_user = await db_session.execute(select(User).where(User.user_id == test_uid))
            assert verify_user.scalars().first() is None

            verify_level = await db_session.execute(select(GameplayLevel).where(GameplayLevel.user_id == test_uid))
            assert verify_level.scalars().first() is None
    finally:
        app.dependency_overrides.pop(get_current_user, None)

