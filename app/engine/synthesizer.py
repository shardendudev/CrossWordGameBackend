
import re
import uuid
import secrets
import hashlib
import logging
import asyncio
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.models.movie import Movie
from app.db.models.gameplay import GameplayLevel
from app.schemas.gameplay import LevelResponse
from app.engine.recommender import recommendMoviesByTaste, fetchCandidateMovies
from app.engine.csp_solver import solveCrossword, get_title_stem
from app.engine.dynamic_solver import solveDynamicFreeform
logger = logging.getLogger(__name__)


def hash_cell(salt: str, row: int, col: int, char: str, iterations: int = 15000) -> str:
    """
    Computes a salted PBKDF2-HMAC-SHA256 hash for a crossword cell.
    Parameters align with Web Crypto API:
      password: char.upper()
      salt: f"{salt}:{row}:{col}"
      iterations: 15,000 rounds
      algorithm: SHA-256
      dklen: 32 bytes (64 hex characters)
    """
    return hashlib.pbkdf2_hmac(
        hash_name="sha256",
        password=char.upper().encode("utf-8"),
        salt=f"{salt}:{row}:{col}".encode("utf-8"),
        iterations=iterations,
        dklen=32
    ).hex()





async def generateLevelForUser(
    db: AsyncSession,
    userId: str,
    requestedDifficulty: Optional[float] = None,
    excludeImdbIds: Optional[List[str]] = None,
    rows: int = 10,
    cols: int = 10,
    targetCount: int = 6
) -> LevelResponse:
    """
    Unified level generator supporting dynamic non-square or 10x10 grids,
    vertical-only placement for titles > cols, and dynamic movie counts.
    """

    import time
    t_start = time.perf_counter()

    #1. fetch user profile and difficulty
    result = await db.execute(select(User).where(User.user_id == userId))
    user= result.scalars().first()

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

    # 2. Fetch played IMDB IDs from User.played_imdb_ids & Client Dexie Store
    if user and user.played_imdb_ids:
        played_imdb_ids = set(user.played_imdb_ids)
    else:
        played_imdb_ids = set()

    if excludeImdbIds:
        played_imdb_ids = played_imdb_ids.union(excludeImdbIds)

    

    #3. Fetch candidate movies
    t_db_start = time.perf_counter()
    if taste_vector is not None:
        candidates = await recommendMoviesByTaste(db, tasteVector=taste_vector, targetDifficulty= target_diff, limit=300, margin=0.35)
        mode_used = "Taste-Vector (pgvector)"

    else:
        candidates = await fetchCandidateMovies(db, targetDifficulty=target_diff, limit=300, margin=0.35)
        mode_used= "Cold start (IMDB votes)"

    
    if not candidates or len(candidates) < 10:
        candidates = await fetchCandidateMovies(db, targetDifficulty=0.5, limit=500,margin=0.50)
        mode_used+= "-> Fallback"
    
    t_db_end = time.perf_counter()

    #4. filter previously played movies
    unplayed_candidates = [m for m in candidates if m.imdb_id not in played_imdb_ids]
    final_candidates = unplayed_candidates if len(unplayed_candidates) >= 10 else candidates

    #5. Format candidate dictionaries(Allow titles upto max(rows,cols))
    max_title_len = max(rows,cols)
    seen_stems = set()
    candidate_dicts = []
    filtered_candidates = []

    for m in final_candidates:
        if not m.clean_title:
            continue

        # Support lengths up to max(rows, cols), e.g. 12 on a 12x10 grid
        if not (3 <= len(m.clean_title) <= max_title_len):
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


     # 6. Solve crossword layout via the Dynamic Freeform Solver
    t_solver_start = time.perf_counter()
    solution_placements = await asyncio.to_thread(
        solveDynamicFreeform,
        candidate_dicts,
        targetCount=targetCount,
        rows=rows,
        cols=cols
    )
    t_solver_end = time.perf_counter()
    t_total = time.perf_counter() - t_start
    logger.info(
        f"[PERF] [{rows}x{cols}] Level Gen Total: {t_total*1000:.1f}ms | "
        f"DB Fetch ({mode_used}): {(t_db_end - t_db_start)*1000:.1f}ms | "
        f"Dynamic Solver: {(t_solver_end - t_solver_start)*1000:.1f}ms | "
        f"Candidates: {len(candidate_dicts)}"
    )

    if not solution_placements:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unable to generate a valid crossword layout with candidate movies."
        )

    # 7. Build Clues list, Hint Cache, and Dynamic 2D Grid
    level_id = uuid.uuid4()
    session_salt = secrets.token_hex(16)
    solution_map: Dict[str, str] = {}
    hints_data: Dict[str, Any] = {}
    grid = [["" for _ in range(cols)] for _ in range(rows)]
    clues = []
    sorted_placements = sorted(
        solution_placements,
        key=lambda p: (p["row"], p["col"], 0 if p["direction"] == "ACROSS" else 1)
    )
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
        imdb_id = slot.get("movie", {}).get("imdb_id")
        m = movie_map.get(imdb_id)
        hint_stack = build_hint_stack(m, skill_level, level_id=str(level_id))
        initial_hint = hint_stack[0]

        solution_map[slot["slot_id"]] = clean_word
        hints_data[slot["slot_id"]] = {
            "imdb_id": m.imdb_id if m else None,
            "revealed_up_to": 1,
            "hint_stack": hint_stack
        }

        r, c = slot["row"], slot["col"]
        direction = slot["direction"]
        for idx, ch in enumerate(clean_word):
            gr = r if direction == "ACROSS" else r + idx
            gc = c + idx if direction == "ACROSS" else c
            if 0 <= gr < rows and 0 <= gc < cols:
                grid[gr][gc] = hash_cell(session_salt, gr, gc, ch)

        raw_title = (m.title or m.clean_title) if m else clean_word
        matched_words = re.findall(r'[A-Za-z0-9]+', raw_title)
        word_lengths = [len(w) for w in matched_words] if matched_words else [len(clean_word)]
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
            "display_title": None,
            "difficulty": round(m.base_difficulty, 3) if m else 0.5,
            "hint": initial_hint["text"],
            "hint_tier": initial_hint["tier"],
            "hint_type": initial_hint["type"],
            "hints_available": len(hint_stack) - 1,
            "post_solve_trivia": None
        }
        clues.append(clue_obj)

    # Single unified level session row
    gameplay_level = GameplayLevel(
        level_id=level_id,
        user_id=userId,
        level_number=level_number,
        target_difficulty=target_diff,
        session_salt=session_salt,
        solution_map=solution_map,
        hints_data=hints_data,
        is_completed=False
    )
    db.add(gameplay_level)

    return LevelResponse(
        level_id=level_id,
        level_number=level_number,
        target_difficulty=target_diff,
        session_salt=session_salt,
        free_hints_remaining=2,
        premium_hints_remaining=user.premium_hints_balance if user else 5,
        grid=grid,
        clues=clues
    )




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


# Alias for backward compatibility
generateExperimentalLevelForUser = generateLevelForUser