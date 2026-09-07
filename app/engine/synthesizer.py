import uuid
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.models.movie import Movie
from app.db.models.telemetry import UserGameplayTelemetry
from app.db.models.hint_cache import LevelHintCache
from app.schemas.gameplay import LevelResponse
from app.services.history_store import history_store
from app.engine.recommender import recommendMoviesByTaste, fetchCandidateMovies
from app.engine.csp_solver import solveCrossword

logger = logging.getLogger(__name__)


def build_hint_stack(movie: Optional[Movie], skill_level: float) -> List[Dict[str, Any]]:
    """
    Builds an ordered hint stack (T1 hardest -> T7 easiest) for a movie.
    Determines starting tier index based on player's skill_level.
    """
    if not movie:
        return [{
            "tier": 7,
            "type": "title_clue",
            "text": "Movie title clue",
            "cost": 0
        }]

    all_tiers = [
        {"tier": 1, "type": "trivia", "text": movie.trivia_hints},
        {"tier": 2, "type": "props", "text": movie.famous_props_macguffins},
        {"tier": 3, "type": "cultural_impact", "text": movie.cultural_impact_legacy},
        {"tier": 4, "type": "famous_scene", "text": movie.famous_scene_hints},
        {"tier": 5, "type": "theme", "text": movie.theme_hints},
        {"tier": 6, "type": "plot", "text": movie.plot_hints},
        {"tier": 7, "type": "character", "text": movie.character_hints},
    ]

    available = [h for h in all_tiers if h["text"]]
    if not available:
        available = [{
            "tier": 7,
            "type": "fallback",
            "text": f"Famous {movie.year} film directed by {movie.director or 'Unknown'}"
        }]

    if skill_level >= 0.70:
        start_min_tier = 1
    elif skill_level >= 0.40:
        start_min_tier = 3
    else:
        start_min_tier = 5

    eligible = [h for h in available if h["tier"] >= start_min_tier]
    if not eligible:
        eligible = available[-1:]

    stack = []
    for i, h in enumerate(eligible):
        stack.append({
            "tier": h["tier"],
            "type": h["type"],
            "text": h["text"],
            "cost": 0 if i == 0 else (0 if i <= 2 else 1)
        })
    return stack


async def generateLevelForUser(
    db: AsyncSession, 
    userId: uuid.UUID, 
    requestedDifficulty: Optional[float] = None
) -> LevelResponse:
    # 1. Fetch User Profile
    result = await db.execute(select(User).where(User.user_id == userId))
    user = result.scalars().first()

    skill_level = user.current_skill_level if user else 0.200
    taste_vector = user.taste_vector if user else None
    target_diff = requestedDifficulty if requestedDifficulty is not None else skill_level

    # 2. Fetch Played IMDb IDs for this User to prevent duplicates across levels
    history_query = select(UserGameplayTelemetry.imdb_id).where(
        UserGameplayTelemetry.user_id == userId,
        UserGameplayTelemetry.imdb_id.is_not(None)
    )
    history_res = await db.execute(history_query)
    played_imdb_ids = set(history_res.scalars().all())

    # Union with history_store for instant deduplication across in-progress and completed levels
    store_played_ids = await history_store.get_played_movie_ids(str(userId))
    played_imdb_ids = played_imdb_ids.union(store_played_ids)

    # 3. Fetch Candidate Movies
    if taste_vector is not None:
        candidates = await recommendMoviesByTaste(db, tasteVector=taste_vector, targetDifficulty=target_diff, limit=300, margin=0.35)
    else:
        candidates = await fetchCandidateMovies(db, targetDifficulty=target_diff, limit=300, margin=0.35)

    if not candidates or len(candidates) < 10:
        candidates = await fetchCandidateMovies(db, targetDifficulty=0.5, limit=500, margin=0.50)

    # 4. Filter out previously played movies
    unplayed_candidates = [m for m in candidates if m.imdb_id not in played_imdb_ids]
    final_candidates = unplayed_candidates if len(unplayed_candidates) >= 10 else candidates

    # 5. Format Candidate Dictionaries for Freeform Solver
    candidate_dicts = [
        {
            "imdb_id": m.imdb_id,
            "title": m.title,
            "clean_title": m.clean_title
        }
        for m in final_candidates if m.clean_title
    ]
    movie_map = {m.clean_title: m for m in final_candidates if m.clean_title}

    # 6. Solve crossword layout (OR-Tools primary, greedy fallback)
    solution_placements = solveCrossword(candidate_dicts, targetCount=6, gridSize=10)

    # 7. Build Clues, Hint Cache entries, and Placed Words list
    placed_words = []
    clues = []
    level_id = uuid.uuid4()
    
    if solution_placements:
        grid = [["" for _ in range(10)] for _ in range(10)]
        
        for slot in solution_placements:
            clean_word = slot["word"]
            m = movie_map.get(clean_word)
            hint_stack = build_hint_stack(m, skill_level)
            initial_hint = hint_stack[0]
            
            # Save hint stack in database
            hint_cache_row = LevelHintCache(
                level_id=level_id,
                slot_id=slot["slot_id"],
                imdb_id=m.imdb_id if m else None,
                hint_stack=hint_stack,
                revealed_up_to=1
            )
            db.add(hint_cache_row)

            r, c = slot["row"], slot["col"]
            direction = slot["direction"]
            for idx, ch in enumerate(clean_word):
                gr = r if direction in ("H", "ACROSS") else r + idx
                gc = c + idx if direction in ("H", "ACROSS") else c
                if 0 <= gr < 10 and 0 <= gc < 10:
                    grid[gr][gc] = ch

            post_trivia = (m.awards_summary or m.iconic_dialogue or "Iconic cinema classic!") if m else ""

            clue_obj = {
                "slot_id": slot["slot_id"],
                "direction": slot["direction"],
                "start_row": slot["row"],
                "start_col": slot["col"],
                "length": slot["length"],
                "initial_hint": initial_hint["text"],
                "clue_text": initial_hint["text"],
                "initial_hint_tier": initial_hint["tier"],
                "initial_hint_type": initial_hint["type"],
                "hints_available": len(hint_stack) - 1,
                "post_solve_trivia": post_trivia,
                "display_title": m.title if m else clean_word,
                "imdb_id": m.imdb_id if m else None
            }
            clues.append(clue_obj)
            placed_words.append(slot)

        await db.commit()
    else:
        grid = [["" for _ in range(10)] for _ in range(10)]

    return LevelResponse(
        level_id=level_id,
        target_difficulty=target_diff,
        grid=grid,
        placed_words=placed_words,
        clues=clues
    )


    