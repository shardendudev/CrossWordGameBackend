import re
import uuid
import hashlib
import logging
import asyncio
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.models.movie import Movie
from app.db.models.telemetry import UserGameplayTelemetry, UserMovieTelemetry
from app.db.models.hint_cache import LevelHintCache
from app.schemas.gameplay import LevelResponse
from app.engine.recommender import recommendMoviesByTaste, fetchCandidateMovies
from app.engine.csp_solver import solveCrossword, get_title_stem

logger = logging.getLogger(__name__)


def _pick_hint(raw: str, seed: str) -> str:
    """
    Selects one hint from a pipe-separated hint string deterministically.

    The seed (level_id + imdb_id + tier) means:
    - Same movie in the same level always shows the same single hint (stable mid-session).
    - Same movie in a different level shows a different hint (freshness across replays).
    - No randomness — fully reproducible from the same inputs.
    """
    hints = [h.strip() for h in raw.split("|") if h.strip()]
    if not hints:
        return raw.strip()  # not pipe-separated — return as-is
    if len(hints) == 1:
        return hints[0]
    idx = int(hashlib.md5(seed.encode(), usedforsecurity=False).hexdigest(), 16) % len(hints)
    return hints[idx]


def build_hint_stack(
    movie: Optional[Movie],
    skill_level: float,
    level_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Builds an ordered hint stack (T1 hardest -> T7 easiest) for a movie.
    Determines starting tier index based on player's skill_level.

    Each multi-hint column (pipe-separated) is resolved to a single hint using
    a deterministic hash of (level_id, imdb_id, tier) so hints vary per level
    but are stable within a session.
    """
    if not movie:
        return [{
            "tier": 7,
            "type": "title_clue",
            "text": "Movie title clue",
            "cost": 0
        }]

    # Build a stable seed base for this (level, movie) pair
    seed_base = f"{level_id or 'default'}{movie.imdb_id}"

    def pick(raw: Optional[str], tier: int) -> Optional[str]:
        if not raw:
            return None
        return _pick_hint(raw, seed=f"{seed_base}{tier}")

    all_tiers = [
        {"tier": 1, "type": "trivia",          "text": pick(movie.trivia_hints, 1)},
        {"tier": 2, "type": "theme",           "text": pick(movie.theme_hints, 2)},
        {"tier": 3, "type": "props",           "text": pick(movie.famous_props_macguffins, 3)},
        {"tier": 4, "type": "cultural_impact", "text": pick(movie.cultural_impact_legacy, 4)},
        {"tier": 5, "type": "famous_scene",    "text": pick(movie.famous_scene_hints, 5)},
        {"tier": 6, "type": "plot",            "text": pick(movie.plot_hints, 6)},
        {"tier": 7, "type": "character",       "text": pick(movie.character_hints, 7)},
    ]

    available = [h for h in all_tiers if h["text"]]
    if not available:
        available = [{
            "tier": 7,
            "type": "fallback",
            "text": f"Famous {movie.year} film directed by {movie.director or 'Unknown'}"
        }]

    # Continuously map skill_level (0.05 to 0.95) across all 7 hint tiers (Tier 7 easiest -> Tier 1 hardest)
    clamped_skill = max(0.05, min(0.95, skill_level))
    raw_tier = 7.0 - ((clamped_skill - 0.05) / 0.90) * 6.0
    target_tier = max(1, min(7, int(round(raw_tier))))

    # Select primary initial hint closest to target_tier
    primary_hint = min(available, key=lambda h: abs(h["tier"] - target_tier))

    # Remaining hints ordered logically for progressive requests
    remaining_hints = [h for h in available if h != primary_hint]
    if target_tier >= 4:
        # For beginners/intermediates: progressively reveal remaining hints from easiest to hardest
        remaining_hints.sort(key=lambda h: h["tier"], reverse=True)
    else:
        # For experts: progressively reveal remaining hints from hardest to easiest
        remaining_hints.sort(key=lambda h: h["tier"])

    ordered_hints = [primary_hint] + remaining_hints

    stack = []
    for i, h in enumerate(ordered_hints):
        stack.append({
            "tier": h["tier"],
            "type": h["type"],
            "text": h["text"],
            "cost": 0
        })
    return stack


async def generateLevelForUser(
    db: AsyncSession,
    userId: uuid.UUID,
    requestedDifficulty: Optional[float] = None,
    excludeImdbIds: Optional[List[str]] = None
) -> LevelResponse:
    import time
    t_start = time.perf_counter()

    # 1. Fetch User Profile
    result = await db.execute(select(User).where(User.user_id == userId))
    user = result.scalars().first()

    skill_level = user.current_skill_level if user else 0.200
    taste_vector = user.taste_vector if user else None
    target_diff = requestedDifficulty if requestedDifficulty is not None else skill_level

    if user:
        user.levels_generated = User.levels_generated + 1
        await db.flush()
        await db.refresh(user)
        level_number = user.levels_generated
    else:
        level_number = 1

    # 2. Fetch Played IMDb IDs for this User from Postgres Telemetry
    history_query = select(UserMovieTelemetry.imdb_id).where(
        UserMovieTelemetry.user_id == userId
    )
    history_res = await db.execute(history_query)
    played_imdb_ids = set(history_res.scalars().all())

    # Combine Postgres telemetry history with client-passed Dexie.js exclusion list
    if excludeImdbIds:
        played_imdb_ids = played_imdb_ids.union(excludeImdbIds)


    # 3. Fetch Candidate Movies
    t_db_start = time.perf_counter()
    if taste_vector is not None:
        candidates = await recommendMoviesByTaste(db, tasteVector=taste_vector, targetDifficulty=target_diff, limit=300, margin=0.35)
        mode_used = "Taste-Vector (pgvector)"
    else:
        candidates = await fetchCandidateMovies(db, targetDifficulty=target_diff, limit=300, margin=0.35)
        mode_used = "Cold-Start (IMDb Votes)"

    if not candidates or len(candidates) < 10:
        candidates = await fetchCandidateMovies(db, targetDifficulty=0.5, limit=500, margin=0.50)
        mode_used += " -> Fallback"
    t_db_end = time.perf_counter()

    # 4. Filter out previously played movies
    unplayed_candidates = [m for m in candidates if m.imdb_id not in played_imdb_ids]
    final_candidates = unplayed_candidates if len(unplayed_candidates) >= 10 else candidates

    # 5. Format Candidate Dictionaries for Freeform Solver (Deduplicate by Title Stem)
    seen_stems = set()
    candidate_dicts = []
    filtered_candidates = []
    for m in final_candidates:
        if not m.clean_title:
            continue
        stem = get_title_stem(m.clean_title)
        if stem not in seen_stems:
            seen_stems.add(stem)
            candidate_dicts.append({
                "imdb_id": m.imdb_id,
                "title": m.title,
                "clean_title": m.clean_title
            })
            filtered_candidates.append(m)

    movie_map = {m.imdb_id: m for m in filtered_candidates if m.imdb_id}

    # 6. Solve crossword layout (OR-Tools primary, greedy fallback offloaded to thread pool)
    t_solver_start = time.perf_counter()
    solution_placements = await asyncio.to_thread(
        solveCrossword,
        candidate_dicts,
        targetCount=6,
        gridSize=10
    )
    t_solver_end = time.perf_counter()

    t_total = time.perf_counter() - t_start
    logger.info(
        f"[PERF] Level Gen Total: {t_total*1000:.1f}ms | "
        f"DB Fetch ({mode_used}): {(t_db_end - t_db_start)*1000:.1f}ms | "
        f"CSP Solver: {(t_solver_end - t_solver_start)*1000:.1f}ms | "
        f"Candidates Pool: {len(candidate_dicts)}"
    )


    # 7. Build Clues list and Hint Cache entries
    clues = []
    level_id = uuid.uuid4()

    if solution_placements:
        grid = [["" for _ in range(10)] for _ in range(10)]

        # Sort placements by row, then col, then direction (ACROSS first) for standard crossword numbering
        sorted_placements = sorted(
            solution_placements,
            key=lambda p: (p["row"], p["col"], 0 if p["direction"] == "ACROSS" else 1)
        )

        # Assign standard crossword grid numbers (1, 2, 3...) to unique starting cells
        num_map = {}
        curr_num = 1
        for slot in sorted_placements:
            pos_key = (slot["row"], slot["col"])
            if pos_key not in num_map:
                num_map[pos_key] = curr_num
                curr_num += 1
            slot["number"] = num_map[pos_key]

        for slot in sorted_placements:
            clean_word = slot["word"]
            # Lookup by imdb_id to avoid clean_title collision
            imdb_id = slot.get("movie", {}).get("imdb_id")
            m = movie_map.get(imdb_id)
            hint_stack = build_hint_stack(m, skill_level, level_id=str(level_id))
            initial_hint = hint_stack[0]

            # Save hint stack in database (committed by the route layer, not here)
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
                gr = r if direction == "ACROSS" else r + idx
                gc = c + idx if direction == "ACROSS" else c
                if 0 <= gr < 10 and 0 <= gc < 10:
                    grid[gr][gc] = ch

            post_trivia = (m.awards_summary or m.iconic_dialogue or "Iconic cinema classic!") if m else ""

            # Extract individual word lengths from movie title (e.g. "The Batman" -> [3, 6], "(3,6)")
            raw_title = (m.clean_title or m.title) if m else clean_word
            matched_words = re.findall(r'[A-Za-z0-9]+', raw_title)
            if matched_words:
                word_lengths = [len(w) for w in matched_words]
            else:
                word_lengths = [len(clean_word)]
            word_pattern = f"({','.join(str(l) for l in word_lengths)})"

            clue_obj = {
                "slot_id": slot["slot_id"],
                "number": slot["number"],
                "direction": slot["direction"],
                "row": slot["row"],
                "col": slot["col"],
                "length": slot["length"],
                "word_lengths": word_lengths,
                "word_pattern": word_pattern,
                "imdb_id": m.imdb_id if m else None,
                "display_title": m.title if m else clean_word,
                "difficulty": round(m.base_difficulty, 3) if m else 0.5,
                "hint": initial_hint["text"],
                "hint_tier": initial_hint["tier"],
                "hint_type": initial_hint["type"],
                "hints_available": len(hint_stack) - 1,
                "post_solve_trivia": post_trivia
            }
            clues.append(clue_obj)


        # NOTE: db.commit() is intentionally NOT called here.
        # The route layer (generateLevel in gameplay.py) commits AFTER
        # history_store.save_generated_level() succeeds, keeping both writes atomic.
    else:
        grid = [["" for _ in range(10)] for _ in range(10)]

    return LevelResponse(
        level_id=level_id,
        level_number=level_number,
        target_difficulty=target_diff,
        free_hints_remaining=2,
        premium_hints_remaining=user.premium_hints_balance if user else 5,
        grid=grid,
        clues=clues
    )