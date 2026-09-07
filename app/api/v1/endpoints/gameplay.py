import uuid
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.history_store import history_store
from app.db.session import get_db
from app.db.models.user import User
from app.db.models.movie import Movie
from app.db.models.telemetry import UserGameplayTelemetry, UserMovieTelemetry
from app.db.models.hint_cache import LevelHintCache
from app.schemas.gameplay import (
    GenerateLevelRequest,
    LevelResponse,
    HintRequest,
    HintResponse,
    SubmitTelemetryRequest,
    TelemetryResponse,
    LevelHistoryItem,
)
from app.engine.synthesizer import generateLevelForUser
from app.engine.difficulty import (
    calculatePerformanceRatio,
    updateUserSkill,
    updateTasteVector
)

router = APIRouter()


@router.post("/generate-level", response_model=LevelResponse)
async def generateLevel(
    payload: GenerateLevelRequest,
    db: AsyncSession = Depends(get_db)
) -> LevelResponse:
    """
    Generates a personalized, adaptive 6-movie 10x10 crossword level for a user.
    Excludes previously played movies and applies skill-adapted clue text.
    """
    # Verify user exists
    user_res = await db.execute(select(User).where(User.user_id == payload.user_id))
    user = user_res.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{payload.user_id}' not found."
        )

    level_response = await generateLevelForUser(
        db=db,
        userId=payload.user_id,
        requestedDifficulty=payload.requested_difficulty
    )

    movie_summaries = [
        {
            "imdb_id": clue.imdb_id,
            "title": clue.display_title,
            "difficulty": clue.difficulty,
            "direction": clue.direction,
            "slot_id": clue.slot_id
        }
        for clue in level_response.clues
    ]

    puzzle_data = {
        "grid": level_response.grid,
        "clues": [clue.model_dump() for clue in level_response.clues]
    }

    try:
        # Record SQLite history FIRST so both stores succeed or neither does
        await history_store.save_generated_level(
            user_id=str(payload.user_id),
            level_id=str(level_response.level_id),
            target_difficulty=level_response.target_difficulty,
            movies=movie_summaries,
            puzzle_data=puzzle_data
        )
        # Commit Postgres (LevelHintCache rows) only after SQLite succeeds
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save generated level: {str(e)}"
        )

    return level_response


@router.post("/request-hint", response_model=HintResponse)
async def requestHint(
    payload: HintRequest,
    db: AsyncSession = Depends(get_db)
) -> HintResponse:
    """
    Requests the next progressive hint for a specific level slot.
    Deducts premium hint balance when required.
    """
    # Fetch User
    user_res = await db.execute(select(User).where(User.user_id == payload.user_id))
    user = user_res.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{payload.user_id}' not found."
        )

    # Fetch Hint Cache entry
    cache_res = await db.execute(
        select(LevelHintCache).where(
            LevelHintCache.level_id == payload.level_id,
            LevelHintCache.slot_id == payload.slot_id
        )
    )
    hint_entry = cache_res.scalars().first()
    if not hint_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hint data for the requested level and slot not found."
        )

    stack = hint_entry.hint_stack
    revealed_count = hint_entry.revealed_up_to

    if revealed_count >= len(stack):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No additional hints available for this slot."
        )

    next_hint = stack[revealed_count]
    cost = next_hint.get("cost", 0)

    cost_charged = 0
    if cost > 0:
        if user.premium_hints_balance < cost:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Insufficient premium hint balance."
            )
        user.premium_hints_balance -= cost
        cost_charged = cost

    hint_entry.revealed_up_to += 1
    await db.commit()
    await db.refresh(user)

    hints_left = len(stack) - hint_entry.revealed_up_to

    # Compute how many remaining hints in the stack are free (cost == 0)
    free_hints_remaining = sum(
        1 for h in stack[hint_entry.revealed_up_to:]
        if h.get("cost", 0) == 0
    )

    return HintResponse(
        level_id=payload.level_id,
        slot_id=payload.slot_id,
        hint_text=next_hint["text"],
        tier=next_hint["tier"],
        type=next_hint["type"],
        cost_charged=cost_charged,
        free_hints_remaining=free_hints_remaining,
        premium_hints_remaining=user.premium_hints_balance,
        hints_left_for_slot=hints_left
    )


@router.post("/submit-telemetry", response_model=TelemetryResponse)
async def submitTelemetry(
    payload: SubmitTelemetryRequest,
    db: AsyncSession = Depends(get_db)
) -> TelemetryResponse:
    """
    Submits game completion metrics, records session telemetry, and updates player skill rating & taste vector.
    """
    user_res = await db.execute(select(User).where(User.user_id == payload.user_id))
    user = user_res.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{payload.user_id}' not found."
        )

    # Build map of per-movie hint usage if provided by client
    usage_map: Dict[str, Dict[str, int]] = {}
    if payload.hint_usage:
        for u in payload.hint_usage:
            usage_map[u.imdb_id] = {
                "hints_revealed": u.hints_revealed,
                "deepest_tier": u.deepest_tier
            }

    session_id = payload.session_id or uuid.uuid4()

    # 1. Level-level summary row (1 row)
    level_telemetry = UserGameplayTelemetry(
        session_id=session_id,
        user_id=payload.user_id,
        level_id=payload.level_id,
        time_taken_seconds=payload.time_taken_seconds,
        free_hints_used=payload.free_hints_used,
        premium_hints_used=payload.premium_hints_used,
        cell_error_count=payload.cell_error_count,
        is_completed=payload.is_completed
    )
    db.add(level_telemetry)

    # 2. Per-movie detail rows — read hint state & movies from server-side LevelHintCache
    cache_res = await db.execute(
        select(LevelHintCache).where(LevelHintCache.level_id == payload.level_id)
    )
    hint_caches = cache_res.scalars().all()
    cache_by_imdb = {hc.imdb_id: hc for hc in hint_caches if hc.imdb_id}

    # Automatically resolve imdb_ids from LevelHintCache or SQLite history_store
    imdb_ids = list(cache_by_imdb.keys())
    if not imdb_ids:
        level_doc = await history_store.get_level(str(payload.level_id))
        if level_doc and "movies" in level_doc:
            imdb_ids = [m["imdb_id"] for m in level_doc["movies"] if m.get("imdb_id")]

    total_depth_sum = 0.0
    if imdb_ids:
        for imdb_id in imdb_ids:
            hc = cache_by_imdb.get(imdb_id)
            if hc:
                # extra hints beyond the initial (initial is pre-revealed at index 0, revealed_up_to starts at 1)
                hints_rev = max(0, hc.revealed_up_to - 1)
                # Only record hint depth if player explicitly requested at least one additional hint
                if hc.revealed_up_to > 1 and hc.hint_stack:
                    deepest_tier = hc.hint_stack[hc.revealed_up_to - 1]["tier"]
                else:
                    deepest_tier = 0
            else:
                u = usage_map.get(imdb_id, {})
                hints_rev = u.get("hints_revealed", 0)
                deepest_tier = u.get("deepest_tier", 0)

            total_depth_sum += min(1.0, hints_rev / 5.0)

            movie_telemetry = UserMovieTelemetry(
                user_id=payload.user_id,
                level_id=payload.level_id,
                imdb_id=imdb_id,
                hints_revealed=hints_rev,
                deepest_hint_tier=deepest_tier
            )
            db.add(movie_telemetry)

    # Compute average hint depth (0.0 to 1.0)
    avg_hint_depth = (total_depth_sum / len(imdb_ids)) if imdb_ids else 0.0

    prev_skill = user.current_skill_level
    p_level = calculatePerformanceRatio(
        timeTakenSeconds=payload.time_taken_seconds,
        freeHints=payload.free_hints_used,
        premiumHints=payload.premium_hints_used,
        errors=payload.cell_error_count,
        avgHintDepth=avg_hint_depth
    )
    new_skill = updateUserSkill(currentSkill=prev_skill, pLevel=p_level)
    skill_delta = round(new_skill - prev_skill, 3)

    # Fetch all movies in a single query (avoids N+1 pattern)
    if imdb_ids:
        movie_res = await db.execute(select(Movie).where(Movie.imdb_id.in_(imdb_ids)))
        movies_by_id = {m.imdb_id: m for m in movie_res.scalars().all()}

        for imdb_id in imdb_ids:
            movie = movies_by_id.get(imdb_id)
            if movie and movie.semantic_embedding is not None:
                updated_taste = updateTasteVector(
                    currentVector=list(user.taste_vector) if user.taste_vector is not None else None,
                    solvedMovieVector=list(movie.semantic_embedding)
                )
                user.taste_vector = updated_taste

    user.current_skill_level = new_skill
    user.total_games_played = User.total_games_played + 1

    try:
        # Record SQLite history FIRST (Fix 1.3 dual-DB coordination)
        await history_store.record_level_completion(
            user_id=str(payload.user_id),
            level_id=str(payload.level_id),
            time_taken_seconds=payload.time_taken_seconds,
            telemetry={
                "free_hints_used": payload.free_hints_used,
                "premium_hints_used": payload.premium_hints_used,
                "cell_error_count": payload.cell_error_count
            }
        )

        # Commit Postgres transaction LAST
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record level completion telemetry: {str(e)}"
        )

    return TelemetryResponse(
        user_id=payload.user_id,
        session_id=session_id,
        previous_skill_level=prev_skill,
        new_skill_level=new_skill,
        skill_delta=skill_delta
    )


@router.get("/history/{user_id}", response_model=List[LevelHistoryItem])
async def getUserHistory(
    user_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Returns paginated play history for a user."""
    # Verify user exists
    user_res = await db.execute(select(User).where(User.user_id == user_id))
    user = user_res.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{user_id}' not found."
        )

    safe_limit = min(100, max(1, limit))
    safe_offset = max(0, offset)

    return await history_store.get_user_history(
        user_id=str(user_id),
        limit=safe_limit,
        offset=safe_offset
    )