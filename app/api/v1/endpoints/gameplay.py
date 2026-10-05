import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user

from app.db.session import get_db
from app.db.models.user import User
from app.db.models.movie import Movie
from app.db.models.gameplay import GameplayLevel
from app.schemas.gameplay import (
    GenerateLevelRequest,
    GenerateLevelExperimentalRequest,
    LevelResponse,
    HintRequest,
    HintResponse,
    SubmitTelemetryRequest,
    TelemetryResponse,
    LevelHistoryItem,
)
from app.engine.synthesizer import (generateLevelForUser, generateExperimentalLevelForUser)
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> LevelResponse:
    """
    Generates a personalized, adaptive crossword level for a user (default 10x10, 6 movies).
    Excludes previously played movies and applies skill-adapted clue text.
    """
    logger.info("Generating level for user '%s' (%dx%d, target_movies=%d) with requested_difficulty=%s",
                current_user.user_id, payload.rows, payload.cols, payload.target_movies, payload.requested_difficulty)

    # Enforce sequential level progression: user cannot generate a new level if they have an active uncompleted level
    active_level_res = await db.execute(
        select(GameplayLevel).where(
            GameplayLevel.user_id == current_user.user_id,
            GameplayLevel.is_completed == False
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
        userId=current_user.user_id,
        requestedDifficulty=payload.requested_difficulty,
        excludeImdbIds=payload.exclude_imdb_ids,
        rows=payload.rows,
        cols=payload.cols,
        targetCount=payload.target_movies
    )

    logger.info("Level '%s' generated successfully with %d clues.", level_response.level_id, len(level_response.clues))

    try:
        # Commit Postgres (Single GameplayLevel row created in generator)
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Failed to save generated level hints")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while saving generated level hints."
        )

    return level_response


# Alias for backward compatibility
generateLevelExperimental = generateLevel


FREE_HINTS_PER_LEVEL = 2


@router.post("/request-hint", response_model=HintResponse)
async def requestHint(
    payload: HintRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> HintResponse:
    """
    Requests the next progressive hint for a specific level slot.
    Deducts premium hint balance when level-wide free hint budget is exhausted.
    """

    # Fetch GameplayLevel row (enforce ownership)
    level_res = await db.execute(
        select(GameplayLevel).where(
            GameplayLevel.level_id == payload.level_id,
            GameplayLevel.user_id == current_user.user_id
        )
    )
    level = level_res.scalars().first()
    if not level or not level.hints_data or payload.slot_id not in level.hints_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hint data for the requested level and slot not found."
        )

    slot_data = level.hints_data[payload.slot_id]
    stack = slot_data.get("hint_stack", [])
    revealed_count = slot_data.get("revealed_up_to", 1)

    if revealed_count >= len(stack):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No additional hints available for this slot."
        )

    next_hint = stack[revealed_count]

    # Calculate total extra hints revealed across ALL slots in this level so far
    total_extra_hints_used = sum(
        max(0, s.get("revealed_up_to", 1) - 1)
        for s in level.hints_data.values()
    )

    # Charge premium token only when level-wide free hint budget is exhausted
    cost = 0 if total_extra_hints_used < FREE_HINTS_PER_LEVEL else 1

    cost_charged = 0
    if cost > 0:
        if current_user.premium_hints_balance < cost:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Insufficient premium hint balance."
            )
        current_user.premium_hints_balance -= cost
        cost_charged = cost

    slot_data["revealed_up_to"] = revealed_count + 1
    flag_modified(level, "hints_data")

    try:
        await db.commit()
        await db.refresh(current_user)
    except Exception:
        await db.rollback()
        logger.exception("Failed to process hint request")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process hint request."
        )

    hints_left = len(stack) - slot_data["revealed_up_to"]
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
        premium_hints_remaining=current_user.premium_hints_balance,
        hints_left_for_slot=hints_left
    )


@router.post("/submit-telemetry", response_model=TelemetryResponse)
async def submitTelemetry(
    payload: SubmitTelemetryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> TelemetryResponse:
    """
    Submits game completion metrics, records session telemetry, and updates player skill rating & taste vector.
    """
    user = current_user

    # 1. Fetch existing GameplayLevel
    level_res = await db.execute(
        select(GameplayLevel).where(
            GameplayLevel.user_id == current_user.user_id,
            GameplayLevel.level_id == payload.level_id
        )
    )
    level = level_res.scalars().first()
    if not level:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Level session not found."
        )

    if level.is_completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Telemetry already submitted for this level."
        )

    session_id = payload.session_id or level.level_id

    # Update level completion telemetry
    level.time_taken_seconds = payload.time_taken_seconds
    level.free_hints_used = payload.free_hints_used
    level.premium_hints_used = payload.premium_hints_used
    level.cell_error_count = payload.cell_error_count
    level.is_completed = payload.is_completed
    level.completed_at = func.now()

    # 2. Extract per-movie solve metrics from level.hints_data
    movie_telem_list = []
    imdb_ids = []
    total_depth_sum = 0.0

    hints_data = level.hints_data or {}
    for slot_id, slot_info in hints_data.items():
        imdb_id = slot_info.get("imdb_id")
        if not imdb_id:
            continue
        imdb_ids.append(imdb_id)
        revealed_up_to = slot_info.get("revealed_up_to", 1)
        hints_rev = max(0, revealed_up_to - 1)
        stack = slot_info.get("hint_stack", [])
        if revealed_up_to > 1 and stack:
            deepest_tier = stack[min(revealed_up_to - 1, len(stack) - 1)].get("tier", 0)
        else:
            deepest_tier = 0

        total_depth_sum += min(1.0, hints_rev / 5.0)
        movie_telem_list.append({
            "imdb_id": imdb_id,
            "hints_revealed": hints_rev,
            "deepest_hint_tier": deepest_tier
        })

    # Fallback to payload imdb_ids if hints_data has none
    if not imdb_ids and payload.imdb_ids:
        imdb_ids = payload.imdb_ids

    level.movie_telemetry = movie_telem_list
    flag_modified(level, "movie_telemetry")

    # Append to user.played_imdb_ids for fast future deduplication
    if imdb_ids:
        existing_played = set(user.played_imdb_ids or [])
        user.played_imdb_ids = list(existing_played.union(imdb_ids))

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
        user_id=current_user.user_id,
        session_id=session_id,
        previous_skill_level=prev_skill,
        new_skill_level=new_skill,
        skill_delta=skill_delta
    )


@router.get("/history", response_model=List[Dict[str, Any]])
async def getUserHistory(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Returns paginated level telemetry history for a user from Postgres."""
    safe_limit = min(100, max(1, limit))
    safe_offset = max(0, offset)

    history_res = await db.execute(
        select(GameplayLevel)
        .where(
            GameplayLevel.user_id == current_user.user_id,
            GameplayLevel.is_completed == True
        )
        .order_by(GameplayLevel.created_at.desc())
        .limit(safe_limit)
        .offset(safe_offset)
    )
    items = history_res.scalars().all()
    return [
        {
            "session_id": str(item.level_id),
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

