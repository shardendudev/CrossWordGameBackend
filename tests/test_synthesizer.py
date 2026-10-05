import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.user import User
from app.engine.synthesizer import generateLevelForUser

pytestmark = pytest.mark.asyncio(loop_scope="module")


async def test_generateLevelForUser(db_session: AsyncSession):
    test_user_id = str(uuid.uuid4())
    test_user = User(user_id=test_user_id, username=f"gen_{test_user_id[:6]}")
    db_session.add(test_user)
    await db_session.commit()

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
        print(f"  • [{clue.direction}] {clue.hint[:80]}...")


async def test_played_movie_deduplication(db_session: AsyncSession):
    test_user_id = str(uuid.uuid4())
    
    # Insert user to satisfy foreign key constraint
    test_user = User(user_id=test_user_id, username=f"player_{test_user_id[:6]}")
    db_session.add(test_user)
    await db_session.commit()

    # 1. Generate Level 1
    level1 = await generateLevelForUser(db_session, userId=test_user_id, requestedDifficulty=0.35)
    assert level1.level_number == 1
    
    # Query DB hints_data for imdb_ids (server-side tracking)
    from app.db.models.gameplay import GameplayLevel
    from sqlalchemy import select
    
    db_level1 = (await db_session.execute(select(GameplayLevel).where(GameplayLevel.level_id == level1.level_id))).scalars().first()
    level1_imdb_ids = {info["imdb_id"] for info in db_level1.hints_data.values() if info.get("imdb_id")}
    assert len(level1_imdb_ids) > 0

    # 2. Record Level 1 movies as played and mark level completed
    test_user.played_imdb_ids = list(level1_imdb_ids)
    db_level1.is_completed = True
    await db_session.commit()

    # 3. Generate Level 2 for the same user
    level2 = await generateLevelForUser(db_session, userId=test_user_id, requestedDifficulty=0.35)
    assert level2.level_number == 2
    
    db_level2 = (await db_session.execute(select(GameplayLevel).where(GameplayLevel.level_id == level2.level_id))).scalars().first()
    level2_imdb_ids = {info["imdb_id"] for info in db_level2.hints_data.values() if info.get("imdb_id")}

    # 4. Assert ZERO overlap between Level 1 and Level 2 movies!
    overlap = level1_imdb_ids.intersection(level2_imdb_ids)
    print(f"\n [Deduplication Test] Level 1 Movies: {len(level1_imdb_ids)}, Level 2 Movies: {len(level2_imdb_ids)}")
    print(f"  - Overlapping Movies Count: {len(overlap)}")
    assert len(overlap) == 0, f"Movies repeated across levels: {overlap}"