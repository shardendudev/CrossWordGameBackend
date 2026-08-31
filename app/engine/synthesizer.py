import uuid
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.models.movie import Movie
from app.db.models.telemetry import UserGameplayTelemetry
from app.schemas.gameplay import LevelResponse
from app.engine.recommender import recommendMoviesByTaste, fetchCandidateMovies
from app.engine.csp_solver import CrosswordCSPSolver, solveFreeform
from app.core.topologies import EASY_TOPOLOGIES, MEDIUM_TOPOLOGIES, HARD_TOPOLOGIES, transformTopology

logger = logging.getLogger(__name__)


def selectClueForSkill(movie: Movie, skillLevel: float) -> str:
    """Selects an adaptive clue hint based on the player's skill rating."""
    if skillLevel < 0.40:
        return movie.plot_hints or movie.character_hints or f"Famous {movie.year} film directed by {movie.director or 'Unknown'}"
    elif skillLevel < 0.70:
        return movie.famous_scene_hints or movie.theme_hints or movie.plot_hints or f"Starring {movie.actors or 'renowned cast'}"
    else:
        return movie.trivia_hints or movie.famous_props_macguffins or movie.cultural_impact_legacy or movie.famous_scene_hints or f"Iconic cinema release from {movie.year}"


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

    # 5. Format Candidate Dictionaries for Freeform & OR-Tools Solver
    candidate_dicts = [
        {
            "imdb_id": m.imdb_id,
            "title": m.title,
            "clean_title": m.clean_title
        }
        for m in final_candidates if m.clean_title
    ]
    movie_map = {m.clean_title: m for m in final_candidates if m.clean_title}

    # 6. Attempt Dynamic Freeform Placement with End-Cap Buffers (< 15ms)
    solution_placements = solveFreeform(candidate_dicts, targetCount=6, gridSize=10)

    # 7. Fallback to Topology Solver if Freeform placement is needed
    if not solution_placements or len(solution_placements) < 6:
        if target_diff <= 0.40:
            topologies_pool = EASY_TOPOLOGIES
        elif target_diff < 0.70:
            topologies_pool = MEDIUM_TOPOLOGIES
        else:
            topologies_pool = HARD_TOPOLOGIES

        expanded_slots_list = []
        for topo in topologies_pool:
            expanded_slots_list.append(topo["slots"])
            expanded_slots_list.append(transformTopology(topo, rotation=90)["slots"])
            expanded_slots_list.append(transformTopology(topo, flip_h=True)["slots"])
            expanded_slots_list.append(transformTopology(topo, flip_v=True)["slots"])

        solver = CrosswordCSPSolver(gridSize=10)
        solution_placements = solver.solveWithTopologies(expanded_slots_list, candidate_dicts, maxAttempts=10)

    # 8. Build Clues and Placed Words list
    placed_words = []
    clues = []
    
    if solution_placements:
        grid = [["" for _ in range(10)] for _ in range(10)]
        
        for slot in solution_placements:
            clean_word = slot["word"]
            m = movie_map.get(clean_word)
            clue_text = selectClueForSkill(m, skill_level) if m else "Movie title clue"
            
            r, c = slot["row"], slot["col"]
            direction = slot["direction"]
            for idx, ch in enumerate(clean_word):
                gr = r if direction in ("H", "ACROSS") else r + idx
                gc = c + idx if direction in ("H", "ACROSS") else c
                if 0 <= gr < 10 and 0 <= gc < 10:
                    grid[gr][gc] = ch

            clue_obj = {
                "slot_id": slot["slot_id"],
                "direction": slot["direction"],
                "start_row": slot["row"],
                "start_col": slot["col"],
                "length": slot["length"],
                "clue_text": clue_text,
                "display_title": m.title if m else clean_word,
                "imdb_id": m.imdb_id if m else None
            }
            clues.append(clue_obj)
            placed_words.append(slot)

        topology_id = "freeform_dynamic_grid"
    else:
        grid = [["" for _ in range(10)] for _ in range(10)]
        topology_id = "fallback_empty"

    level_id = uuid.uuid4()
    return LevelResponse(
        level_id=level_id,
        topology_id=topology_id,
        target_difficulty=target_diff,
        grid=grid,
        placed_words=placed_words,
        clues=clues
    )