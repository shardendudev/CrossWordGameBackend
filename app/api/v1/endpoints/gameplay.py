import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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

logger = logging.getLogger(__name__)
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
    logger.info("Generating level for user '%s' with requested_difficulty=%s", payload.user_id, payload.requested_difficulty)

    # Verify user exists
    user_res = await db.execute(select(User).where(User.user_id == payload.user_id))
    user = user_res.scalars().first()
    if not user:
        logger.warning("Failed to generate level: User '%s' not found.", payload.user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{payload.user_id}' not found."
        )

    # Enforce sequential level progression: user cannot generate a new level if they have an active uncompleted level
    active_level_res = await db.execute(
        select(UserGameplayTelemetry).where(
            UserGameplayTelemetry.user_id == payload.user_id,
            UserGameplayTelemetry.is_completed == False
        )
    )
    active_level = active_level_res.scalars().first()
    if active_level:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You must complete level {active_level.level_number or ''} before generating a new level."
        )

    level_response = await generateLevelForUser(
        db=db,
        userId=payload.user_id,
        requestedDifficulty=payload.requested_difficulty,
        excludeImdbIds=payload.exclude_imdb_ids
    )

    # Record initial in-progress telemetry row to lock level progression until completed
    initial_telemetry = UserGameplayTelemetry(
        user_id=payload.user_id,
        level_id=level_response.level_id,
        level_number=level_response.level_number,
        time_taken_seconds=0,
        free_hints_used=0,
        premium_hints_used=0,
        cell_error_count=0,
        is_completed=False
    )
    db.add(initial_telemetry)

    logger.info("Level '%s' generated successfully with %d clues.", level_response.level_id, len(level_response.clues))

    try:
        # Commit Postgres (LevelHintCache & initial UserGameplayTelemetry rows)
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Failed to save generated level hints")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while saving generated level hints."
        )

    return level_response



FREE_HINTS_PER_LEVEL = 2


@router.post("/request-hint", response_model=HintResponse)
async def requestHint(
    payload: HintRequest,
    db: AsyncSession = Depends(get_db)
) -> HintResponse:
    """
    Requests the next progressive hint for a specific level slot.
    Deducts premium hint balance when level-wide free hint budget is exhausted.
    """
    # Fetch User
    user_res = await db.execute(select(User).where(User.user_id == payload.user_id))
    user = user_res.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{payload.user_id}' not found."
        )

    # Fetch all Hint Cache entries for this level to calculate level-wide free hint usage
    cache_res = await db.execute(
        select(LevelHintCache).where(LevelHintCache.level_id == payload.level_id)
    )
    all_entries = cache_res.scalars().all()
    hint_entry = next((entry for entry in all_entries if entry.slot_id == payload.slot_id), None)
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

    # Calculate total extra hints revealed across ALL slots in this level so far
    total_extra_hints_used = sum(max(0, entry.revealed_up_to - 1) for entry in all_entries)

    # Charge premium token only when level-wide free hint budget is exhausted
    cost = 0 if total_extra_hints_used < FREE_HINTS_PER_LEVEL else 1

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
    try:
        await db.commit()
        await db.refresh(user)
    except Exception:
        await db.rollback()
        logger.exception("Failed to process hint request")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process hint request."
        )

    hints_left = len(stack) - hint_entry.revealed_up_to
    total_extra_hints_after = total_extra_hints_used + 1
    free_hints_remaining = max(0, FREE_HINTS_PER_LEVEL - total_extra_hints_after)

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

    # Prevent duplicate telemetry submissions for an already completed level
    existing_res = await db.execute(
        select(UserGameplayTelemetry).where(
            UserGameplayTelemetry.user_id == payload.user_id,
            UserGameplayTelemetry.level_id == payload.level_id
        )
    )
    existing_telemetry = existing_res.scalars().first()
    if existing_telemetry:
        if existing_telemetry.is_completed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Telemetry already submitted for this level."
            )
        # Update existing in-progress telemetry row to completed status
        existing_telemetry.time_taken_seconds = payload.time_taken_seconds
        existing_telemetry.free_hints_used = payload.free_hints_used
        existing_telemetry.premium_hints_used = payload.premium_hints_used
        existing_telemetry.cell_error_count = payload.cell_error_count
        existing_telemetry.is_completed = payload.is_completed
        if payload.session_id:
            existing_telemetry.session_id = payload.session_id
        session_id = existing_telemetry.session_id
    else:
        session_id = payload.session_id or uuid.uuid4()
        level_telemetry = UserGameplayTelemetry(
            session_id=session_id,
            user_id=payload.user_id,
            level_id=payload.level_id,
            level_number=payload.level_number,
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

    # Automatically resolve imdb_ids from LevelHintCache or client payload
    imdb_ids = list(cache_by_imdb.keys())
    if not imdb_ids and payload.imdb_ids:
        imdb_ids = payload.imdb_ids
    elif not imdb_ids and payload.hint_usage:
        imdb_ids = [u.imdb_id for u in payload.hint_usage]


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
        # Commit Postgres transaction
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Failed to record level completion telemetry")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while recording level completion telemetry."
        )


    return TelemetryResponse(
        user_id=payload.user_id,
        session_id=session_id,
        previous_skill_level=prev_skill,
        new_skill_level=new_skill,
        skill_delta=skill_delta
    )


@router.get("/history/{user_id}", response_model=List[Dict[str, Any]])
async def getUserHistory(
    user_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Returns paginated level telemetry history for a user from Postgres."""
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

    history_res = await db.execute(
        select(UserGameplayTelemetry)
        .where(UserGameplayTelemetry.user_id == user_id)
        .order_by(UserGameplayTelemetry.created_at.desc())
        .limit(safe_limit)
        .offset(safe_offset)
    )
    items = history_res.scalars().all()
    return [
        {
            "session_id": str(item.session_id),
            "level_id": str(item.level_id),
            "level_number": item.level_number,
            "user_id": str(item.user_id),
            "status": "completed" if item.is_completed else "in_progress",
            "time_taken_seconds": item.time_taken_seconds,
            "free_hints_used": item.free_hints_used,
            "premium_hints_used": item.premium_hints_used,
            "cell_error_count": item.cell_error_count,
            "created_at": item.created_at.isoformat() if item.created_at else ""
        }
        for item in items
    ]