import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.user import User
from app.db.models.telemetry import UserMovieTelemetry
from app.engine.synthesizer import generateLevelForUser

pytestmark = pytest.mark.asyncio(loop_scope="module")


async def test_generateLevelForUser(db_session: AsyncSession):
    test_user_id = uuid.uuid4()
    level_response = await generateLevelForUser(db_session, userId=test_user_id, requestedDifficulty=0.35)

    # Assertions
    assert level_response.level_id is not None
    assert level_response.target_difficulty == 0.35
    assert len(level_response.grid) > 0
    assert len(level_response.clues) > 0

    # Print visual 10x10 grid matrix
    print(f"\n [Synthesizer Test] Level Generated Successfully!")
    print(f"  - Level ID: {level_response.level_id}")
    print(f"  - Clues Generated: {len(level_response.clues)}")

    print("\n 🧩 10x10 VISUAL CROSSWORD GRID:")
    print("  +" + "---+" * 10)
    for row in level_response.grid:
        row_str = " | " + " | ".join([cell if cell else "." for cell in row]) + " |"
        print(row_str)
    print("  +" + "---+" * 10)

    print("\n 💡 GENERATED CLUES & PLACED MOVIES:")
    for clue in level_response.clues:
        print(f"  • [{clue.direction}] {clue.display_title}: {clue.hint[:80]}...")


async def test_played_movie_deduplication(db_session: AsyncSession):
    test_user_id = uuid.uuid4()
    
    # Insert user to satisfy foreign key constraint
    test_user = User(user_id=test_user_id, username=f"player_{test_user_id.hex[:6]}")
    db_session.add(test_user)
    await db_session.commit()

    # 1. Generate Level 1
    level1 = await generateLevelForUser(db_session, userId=test_user_id, requestedDifficulty=0.35)
    assert level1.level_number == 1
    level1_imdb_ids = {c.imdb_id for c in level1.clues if c.imdb_id}
    assert len(level1_imdb_ids) > 0

    # 2. Record Level 1 movies as played in UserMovieTelemetry
    for imdb_id in level1_imdb_ids:
        telemetry = UserMovieTelemetry(
            user_id=test_user_id,
            level_id=level1.level_id,
            imdb_id=imdb_id
        )
        db_session.add(telemetry)
    await db_session.commit()

    # 3. Generate Level 2 for the same user
    level2 = await generateLevelForUser(db_session, userId=test_user_id, requestedDifficulty=0.35)
    assert level2.level_number == 2
    level2_imdb_ids = {c.imdb_id for c in level2.clues if c.imdb_id}

    # 4. Assert ZERO overlap between Level 1 and Level 2 movies!
    overlap = level1_imdb_ids.intersection(level2_imdb_ids)
    print(f"\n [Deduplication Test] Level 1 Movies: {len(level1_imdb_ids)}, Level 2 Movies: {len(level2_imdb_ids)}")
    print(f"  - Overlapping Movies Count: {len(overlap)}")
    print(f"  - Level 1 Movies: {[c.display_title for c in level1.clues]}")
    print(f"  - Level 2 Movies: {[c.display_title for c in level2.clues]}")
    assert len(overlap) == 0, f"Movies repeated across levels: {overlap}"