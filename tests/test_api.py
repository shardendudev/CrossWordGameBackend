import uuid
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="module")


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

    # Generate Level with Dexie exclude_imdb_ids list
    level_res = await async_client.post("/api/v1/gameplay/generate-level", json={
        "user_id": user_id,
        "requested_difficulty": 0.30,
        "exclude_imdb_ids": ["tt0114709", "tt0120338"]
    })
    assert level_res.status_code == 200
    level_data = level_res.json()
    
    assert "level_id" in level_data
    assert level_data["level_number"] == 1
    assert "grid" in level_data
    assert level_data["free_hints_remaining"] == 2
    assert level_data["premium_hints_remaining"] == 5
    assert len(level_data["clues"]) == 6
    # Verify word_lengths and word_pattern are generated for clues
    for clue in level_data["clues"]:
        assert "word_lengths" in clue and isinstance(clue["word_lengths"], list)
        assert "word_pattern" in clue and clue["word_pattern"].startswith("(") and clue["word_pattern"].endswith(")")
    
    # Ensure excluded movies are not present in generated clues
    generated_imdb_ids = [c["imdb_id"] for c in level_data["clues"]]
    assert "tt0114709" not in generated_imdb_ids
    assert "tt0120338" not in generated_imdb_ids


async def test_level_progression_lock(async_client: AsyncClient):
    unique_username = f"lock_user_{uuid.uuid4().hex[:8]}"
    create_res = await async_client.post("/api/v1/users/", json={"username": unique_username})
    user_id = create_res.json()["user_id"]

    # 1. Generate Level 1
    lvl1_res = await async_client.post("/api/v1/gameplay/generate-level", json={
        "user_id": user_id,
        "requested_difficulty": 0.30
    })
    assert lvl1_res.status_code == 200
    lvl1_data = lvl1_res.json()
    level1_id = lvl1_data["level_id"]

    # 2. Attempting to generate Level 2 without completing Level 1 must fail with 400 Bad Request
    lvl2_fail = await async_client.post("/api/v1/gameplay/generate-level", json={
        "user_id": user_id,
        "requested_difficulty": 0.30
    })
    assert lvl2_fail.status_code == 400
    assert "complete level" in lvl2_fail.json()["detail"].lower()

    # 3. Complete Level 1 by submitting telemetry
    sub_res = await async_client.post("/api/v1/gameplay/submit-telemetry", json={
        "user_id": user_id,
        "level_id": level1_id,
        "time_taken_seconds": 30,
        "free_hints_used": 0,
        "cell_error_count": 0,
        "is_completed": True
    })
    assert sub_res.status_code == 200

    # 4. Generating Level 2 now succeeds
    lvl2_success = await async_client.post("/api/v1/gameplay/generate-level", json={
        "user_id": user_id,
        "requested_difficulty": 0.30
    })
    assert lvl2_success.status_code == 200
    assert lvl2_success.json()["level_number"] == 2


async def test_submit_telemetry_api(async_client: AsyncClient):
    unique_username = f"telemetry_user_{uuid.uuid4().hex[:8]}"
    create_res = await async_client.post("/api/v1/users/", json={"username": unique_username})
    user_id = create_res.json()["user_id"]

    # 1. Generate level first
    level_res = await async_client.post("/api/v1/gameplay/generate-level", json={
        "user_id": user_id,
        "requested_difficulty": 0.30
    })
    level_id = level_res.json()["level_id"]
    session_id = str(uuid.uuid4())

    # 2. Submit Telemetry
    telemetry_payload = {
        "user_id": user_id,
        "session_id": session_id,
        "level_id": level_id,
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


async def test_get_user_history_api(async_client: AsyncClient):
    unique_username = f"history_user_{uuid.uuid4().hex[:8]}"
    create_res = await async_client.post("/api/v1/users/", json={"username": unique_username})
    user_id = create_res.json()["user_id"]

    # 1. Generate a Level
    level_res = await async_client.post("/api/v1/gameplay/generate-level", json={
        "user_id": user_id,
        "requested_difficulty": 0.35
    })
    assert level_res.status_code == 200
    level_id = level_res.json()["level_id"]

    # 2. Submit Telemetry
    telemetry_payload = {
        "user_id": user_id,
        "session_id": str(uuid.uuid4()),
        "level_id": level_id,
        "time_taken_seconds": 48,
        "free_hints_used": 1,
        "cell_error_count": 0,
        "is_completed": True
    }
    sub_res = await async_client.post("/api/v1/gameplay/submit-telemetry", json=telemetry_payload)
    assert sub_res.status_code == 200

    # 3. Verify level completion status in Postgres history endpoint
    updated_hist = await async_client.get(f"/api/v1/gameplay/history/{user_id}")
    assert updated_hist.status_code == 200
    data = updated_hist.json()
    assert len(data) >= 1
    assert data[0]["level_id"] == level_id
    assert data[0]["status"] == "completed"
    assert data[0]["time_taken_seconds"] == 48

    # 4. Verify non-existent user returns 404
    fake_id = str(uuid.uuid4())
    missing_res = await async_client.get(f"/api/v1/gameplay/history/{fake_id}")
    assert missing_res.status_code == 404



async def test_request_hint_api(async_client: AsyncClient):
    unique_username = f"hint_user_{uuid.uuid4().hex[:8]}"
    create_res = await async_client.post("/api/v1/users/", json={"username": unique_username})
    user_data = create_res.json()
    user_id = user_data["user_id"]
    initial_premium_balance = user_data["premium_hints_balance"]  # Default 5

    # 1. Generate level
    level_res = await async_client.post("/api/v1/gameplay/generate-level", json={
        "user_id": user_id,
        "requested_difficulty": 0.35
    })
    assert level_res.status_code == 200
    level_data = level_res.json()
    level_id = level_data["level_id"]
    slot_1 = level_data["clues"][0]["slot_id"]
    slot_2 = level_data["clues"][1]["slot_id"]

    # 2. Request 1st hint on Slot 1 -> Free (Level total: 1)
    hint_res1 = await async_client.post("/api/v1/gameplay/request-hint", json={
        "user_id": user_id,
        "level_id": level_id,
        "slot_id": slot_1
    })
    assert hint_res1.status_code == 200
    hdata1 = hint_res1.json()
    assert hdata1["cost_charged"] == 0
    assert hdata1["free_hints_remaining"] == 1
    assert hdata1["premium_hints_remaining"] == initial_premium_balance

    # 3. Request 1st hint on Slot 2 -> Free (Level total: 2)
    hint_res2 = await async_client.post("/api/v1/gameplay/request-hint", json={
        "user_id": user_id,
        "level_id": level_id,
        "slot_id": slot_2
    })
    assert hint_res2.status_code == 200
    hdata2 = hint_res2.json()
    assert hdata2["cost_charged"] == 0
    assert hdata2["free_hints_remaining"] == 0
    assert hdata2["premium_hints_remaining"] == initial_premium_balance

    # 4. Request 2nd hint on Slot 1 -> Exceeds level free budget -> Costs 1 Premium Token (Level total: 3)
    hint_res3 = await async_client.post("/api/v1/gameplay/request-hint", json={
        "user_id": user_id,
        "level_id": level_id,
        "slot_id": slot_1
    })
    assert hint_res3.status_code == 200
    hdata3 = hint_res3.json()
    assert hdata3["cost_charged"] == 1
    assert hdata3["free_hints_remaining"] == 0
    assert hdata3["premium_hints_remaining"] == initial_premium_balance - 1


async def test_duplicate_telemetry_rejection(async_client: AsyncClient):
    unique_username = f"dup_user_{uuid.uuid4().hex[:8]}"
    create_res = await async_client.post("/api/v1/users/", json={"username": unique_username})
    user_id = create_res.json()["user_id"]

    level_res = await async_client.post("/api/v1/gameplay/generate-level", json={
        "user_id": user_id,
        "requested_difficulty": 0.30
    })
    level_id = level_res.json()["level_id"]

    telemetry_payload = {
        "user_id": user_id,
        "level_id": level_id,
        "time_taken_seconds": 30,
        "free_hints_used": 0,
        "cell_error_count": 0,
        "is_completed": True
    }

    sub_res1 = await async_client.post("/api/v1/gameplay/submit-telemetry", json=telemetry_payload)
    assert sub_res1.status_code == 200

    # Second submission for same level should be rejected with 409 Conflict
    sub_res2 = await async_client.post("/api/v1/gameplay/submit-telemetry", json=telemetry_payload)
    assert sub_res2.status_code == 409
    assert sub_res2.json()["detail"] == "Telemetry already submitted for this level."






