import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.session import engine, init_db

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module")
async def async_client():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    await engine.dispose()


async def test_health_check(async_client: AsyncClient):
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["version"] == "1.0.0"


async def test_user_creation_and_profile(async_client: AsyncClient):
    unique_username = f"player_{uuid.uuid4().hex[:8]}"
    
    # 1. Create User
    create_res = await async_client.post("/api/v1/users/", json={"username": unique_username})
    assert create_res.status_code == 201
    user_data = create_res.json()
    assert "user_id" in user_data
    assert user_data["username"] == unique_username
    assert user_data["current_skill_level"] == 0.200

    user_id = user_data["user_id"]

    # 2. Get Profile
    get_res = await async_client.get(f"/api/v1/users/{user_id}")
    assert get_res.status_code == 200
    profile_data = get_res.json()
    assert profile_data["user_id"] == user_id
    assert profile_data["username"] == unique_username


async def test_generate_level_api(async_client: AsyncClient):
    unique_username = f"solver_{uuid.uuid4().hex[:8]}"
    create_res = await async_client.post("/api/v1/users/", json={"username": unique_username})
    user_id = create_res.json()["user_id"]

    # Generate Level
    level_res = await async_client.post("/api/v1/gameplay/generate-level", json={
        "user_id": user_id,
        "requested_difficulty": 0.30
    })
    assert level_res.status_code == 200
    level_data = level_res.json()
    
    assert "level_id" in level_data
    assert "grid" in level_data
    assert len(level_data["placed_words"]) == 6
    assert len(level_data["clues"]) == 6


async def test_submit_telemetry_api(async_client: AsyncClient):
    unique_username = f"telemetry_user_{uuid.uuid4().hex[:8]}"
    create_res = await async_client.post("/api/v1/users/", json={"username": unique_username})
    user_id = create_res.json()["user_id"]

    session_id = str(uuid.uuid4())
    level_id = str(uuid.uuid4())

    # Submit Telemetry
    telemetry_payload = {
        "user_id": user_id,
        "session_id": session_id,
        "level_id": level_id,
        "imdb_id": "tt0111161",  # The Shawshank Redemption
        "time_taken_seconds": 35,
        "free_hints_used": 0,
        "cell_error_count": 0,
        "is_completed": True
    }

    sub_res = await async_client.post("/api/v1/gameplay/submit-telemetry", json=telemetry_payload)
    assert sub_res.status_code == 200
    res_data = sub_res.json()

    assert res_data["user_id"] == user_id
    assert res_data["session_id"] == session_id
    assert res_data["previous_skill_level"] == 0.200
    assert "new_skill_level" in res_data
    assert "skill_delta" in res_data
