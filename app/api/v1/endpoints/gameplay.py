import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models.user import User
from app.db.models.movie import Movie
from app.db.models.telemetry import UserGameplayTelemetry
from app.schemas.gameplay import (
    GenerateLevelRequest,
    LevelResponse,
    SubmitTelemetryRequest,
    TelemetryResponse
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
    return level_response


@router.post("/submit-telemetry", response_model=TelemetryResponse)
async def submitTelemetry(
    payload: SubmitTelemetryRequest,
    db: AsyncSession = Depends(get_db)
) -> TelemetryResponse:
    """
    Submits game completion metrics, records session telemetry, and updates player skill rating & taste vector.
    """
    # Fetch User
    user_res = await db.execute(select(User).where(User.user_id == payload.user_id))
    user = user_res.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{payload.user_id}' not found."
        )

    # 1. Record Telemetry
    telemetry = UserGameplayTelemetry(
        session_id=payload.session_id,
        user_id=payload.user_id,
        level_id=payload.level_id,
        imdb_id=payload.imdb_id,
        time_taken_seconds=payload.time_taken_seconds,
        free_hints_used=payload.free_hints_used,
        premium_hints_used=0,
        cell_error_count=payload.cell_error_count,
        is_completed=payload.is_completed
    )
    db.add(telemetry)

    # 2. Skill Level Update
    prev_skill = user.current_skill_level
    p_level = calculatePerformanceRatio(
        timeTakenSeconds=payload.time_taken_seconds,
        freeHints=payload.free_hints_used,
        premiumHints=0,
        errors=payload.cell_error_count
    )
    new_skill = updateUserSkill(currentSkill=prev_skill, pLevel=p_level)
    skill_delta = round(new_skill - prev_skill, 3)

    # 3. Taste Vector Update (if solved movie provided)
    if payload.imdb_id:
        movie_res = await db.execute(select(Movie).where(Movie.imdb_id == payload.imdb_id))
        movie = movie_res.scalars().first()
        if movie and movie.semantic_embedding is not None:
            updated_taste = updateTasteVector(
                currentVector=list(user.taste_vector) if user.taste_vector is not None else None,
                solvedMovieVector=list(movie.semantic_embedding)
            )
            user.taste_vector = updated_taste

    # Update User attributes
    user.current_skill_level = new_skill
    user.total_games_played += 1

    await db.commit()

    return TelemetryResponse(
        user_id=payload.user_id,
        session_id=payload.session_id,
        previous_skill_level=prev_skill,
        new_skill_level=new_skill,
        skill_delta=skill_delta
    )
