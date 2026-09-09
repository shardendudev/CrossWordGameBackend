import re
import random
import logging
from typing import List, Dict, Tuple, Optional, Set, Any
from ortools.sat.python import cp_model

logger = logging.getLogger(__name__)


def get_title_stem(title: str) -> str:
    """
    Normalizes clean_title or title into a base franchise stem to prevent
    multiple movies from the same franchise (e.g. 'Toy Story' and 'Toy Story 3')
    from being placed in the same level.
    """
    s = title.upper().strip()
    s = re.sub(r'(\b|_)?(PART|VOL|VOLUME|CHAPTER|EPISODE|SEASON)\b.*$', '', s)
    s = re.sub(r'(\d+|II|III|IV|V|VI|VII|VIII|IX|X)+$', '', s)
    s = s.strip()
    return s if len(s) >= 3 else title.upper().strip()


# 1. Spatial Placement Rule Validator (used by greedy solver & bounds checker)

def isValidFreeformPlacement(grid: List[List[str]], word: str, r: int, c: int, direction: str, size: int = 10) -> bool:
    """
    Validates dynamic freeform word placement with strict End-Cap Buffers and Side-by-Side Adjacency rules.
    - End-Cap Buffer: Cells before start and after end MUST be empty.
    - Side-by-Side Buffer: Non-intersection side cells MUST be empty.
    """
    length = len(word)
    
    # 1. Grid Bounds Check & End-Cap Buffers
    if direction == "ACROSS":
        if c < 0 or c + length > size or r < 0 or r >= size:
            return False
        if c - 1 >= 0 and grid[r][c - 1] != "":
            return False
        if c + length < size and grid[r][c + length] != "":
            return False
    else:  # DOWN
        if r < 0 or r + length > size or c < 0 or c >= size:
            return False
        if r - 1 >= 0 and grid[r - 1][c] != "":
            return False
        if r + length < size and grid[r + length][c] != "":
            return False

    # 2. Cell Occupancy & Side Adjacency Checks
    for i, ch in enumerate(word):
        curr_r = r if direction == "ACROSS" else r + i
        curr_c = c + i if direction == "ACROSS" else c
        existing = grid[curr_r][curr_c]
        
        if existing != "" and existing != ch:
            return False  # Letter mismatch
            
        if existing == "":
            if direction == "ACROSS":
                if curr_r - 1 >= 0 and grid[curr_r - 1][curr_c] != "":
                    return False
                if curr_r + 1 < size and grid[curr_r + 1][curr_c] != "":
                    return False
            else:
                if curr_c - 1 >= 0 and grid[curr_r][curr_c - 1] != "":
                    return False
                if curr_c + 1 < size and grid[curr_r][curr_c + 1] != "":
                    return False

    return True

# 2. PRODUCTION OR-TOOLS CP-SAT SOLVER (Linearized & Thread-Capped)

def filterConnectableCandidates(candidateWords: List[Dict[str, Any]], maxCount: int = 25) -> List[Dict[str, Any]]:
    """
    Pre-filters candidate movies by removing titles that share fewer than 2 distinct characters
    with the rest of the candidate pool, preventing wasted placement variables.
    """
    valid = [w for w in candidateWords if w.get("clean_title") and 3 <= len(w["clean_title"]) <= 10]
    if len(valid) <= maxCount:
        return valid

    # Cap to top 50 candidates before calculating intersection matrix
    valid = valid[:50]

    # Calculate letter overlap counts
    word_sets = [set(w["clean_title"]) for w in valid]
    scores = []
    for i, w_set in enumerate(word_sets):
        overlap_score = sum(len(w_set.intersection(other_set)) for j, other_set in enumerate(word_sets) if i != j)
        scores.append((overlap_score, valid[i]))

    # Sort candidates by character overlap connectivity
    scores.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scores[:maxCount]]


SOLVER_TIME_LIMIT_S: float = 0.75  # 750ms time budget for OR-Tools CP-SAT



def solveWithORTools(
    candidateWords: List[Dict[str, Any]],
    targetCount: int = 6,
    gridSize: int = 10,
    timeLimitSeconds: float = SOLVER_TIME_LIMIT_S,
    maxCandidates: int = 25
) -> Optional[List[Dict[str, Any]]]:
    """
    Production-grade Google OR-Tools CP-SAT solver for 2D crossword placement.
    Uses direct linear constraints (zero reified variable overhead) and capped worker threads.
    """
    candidates = filterConnectableCandidates(candidateWords, maxCount=maxCandidates)
    if len(candidates) < targetCount:
        return None

    # 1. Enumerate valid placements
    placements: List[Tuple] = []
    for w_idx, cand in enumerate(candidates):
        word = cand["clean_title"]
        L = len(word)
        for r in range(gridSize):
            for c in range(gridSize - L + 1):
                placements.append((len(placements), w_idx, word, cand, r, c, "ACROSS", L))
        for r in range(gridSize - L + 1):
            for c in range(gridSize):
                placements.append((len(placements), w_idx, word, cand, r, c, "DOWN", L))

    N = len(placements)
    if N == 0:
        return None

    # 2. Build spatial letter map
    # (r, c) -> list of (p_idx, char, direction)
    cell_letters: Dict[Tuple[int, int], List[Tuple[int, str, str]]] = {}
    for p_idx, _, word, _, row, col, d, L in placements:
        for i, ch in enumerate(word):
            r = row if d == "ACROSS" else row + i
            c = col + i if d == "ACROSS" else col
            cell_letters.setdefault((r, c), []).append((p_idx, ch, d))

    # 3. Build CP-SAT Model
    model = cp_model.CpModel()
    x = [model.NewBoolVar(f"x_{i}") for i in range(N)]

    # C1: Select exactly targetCount words
    model.Add(sum(x) == targetCount)

    # C2: At most 1 placement per candidate movie and at most 1 per title stem (no franchise duplicates)
    by_word: Dict[int, List[int]] = {}
    by_stem: Dict[str, List[int]] = {}
    for p in placements:
        by_word.setdefault(p[1], []).append(p[0])
        stem = get_title_stem(p[2])
        by_stem.setdefault(stem, []).append(p[0])

    for indices in by_word.values():
        model.Add(sum(x[i] for i in indices) <= 1)

    for indices in by_stem.values():
        model.Add(sum(x[i] for i in indices) <= 1)


    # C3: Cell level direction & letter consistency constraints
    intersection_pairs: List[Tuple[int, int]] = []

    for cell, occupants in cell_letters.items():
        across_ps = [p for p, _, d in occupants if d == "ACROSS"]
        down_ps = [p for p, _, d in occupants if d == "DOWN"]

        # Max 1 ACROSS and max 1 DOWN word per cell
        if len(across_ps) > 1:
            model.Add(sum(x[p] for p in across_ps) <= 1)
        if len(down_ps) > 1:
            model.Add(sum(x[p] for p in down_ps) <= 1)

        # Direct pairwise constraints: Forbid letter mismatch at intersections
        across_dict = {p: ch for p, ch, d in occupants if d == "ACROSS"}
        down_dict = {p: ch for p, ch, d in occupants if d == "DOWN"}

        for a_p, a_ch in across_dict.items():
            for d_p, d_ch in down_dict.items():
                if a_ch != d_ch:
                    # Letter mismatch -> cannot both be active
                    model.Add(x[a_p] + x[d_p] <= 1)
                else:
                    # Valid intersection pair!
                    intersection_pairs.append((a_p, d_p))

    # C4: End-Cap Empty Buffer Constraints (Direct Pairwise Linear Bounds)
    for p_idx, _, _, _, row, col, d, L in placements:
        # Determine end-cap cells
        end_caps = []
        if d == "ACROSS":
            if col > 0: end_caps.append((row, col - 1))
            if col + L < gridSize: end_caps.append((row, col + L))
        else:
            if row > 0: end_caps.append((row - 1, col))
            if row + L < gridSize: end_caps.append((row + L, col))

        for cap in end_caps:
            if cap in cell_letters:
                # Placements that occupy the end-cap cell cannot be active if p_idx is active
                for other_p, _, _ in cell_letters[cap]:
                    if other_p != p_idx:
                        model.Add(x[p_idx] + x[other_p] <= 1)

    # C5: Side-Adjacency Buffer Constraints
    # Prevents parallel adjacent words from touching side-by-side unless connected by an intersection
    for cell, occupants in cell_letters.items():
        r, c = cell
        across_ps = [p for p, _, d in occupants if d == "ACROSS"]
        down_ps = [p for p, _, d in occupants if d == "DOWN"]

        # Check vertical neighbours for ACROSS words
        if across_ps:
            for dr in (-1, 1):
                adj_cell = (r + dr, c)
                if adj_cell in cell_letters:
                    adj_ps = [p for p, _, _ in cell_letters[adj_cell]]
                    for a_p in across_ps:
                        for adj_p in adj_ps:
                            if adj_p != a_p and adj_p not in down_ps:
                                model.Add(x[a_p] + x[adj_p] <= 1)

        # Check horizontal neighbours for DOWN words
        if down_ps:
            for dc in (-1, 1):
                adj_cell = (r, c + dc)
                if adj_cell in cell_letters:
                    adj_ps = [p for p, _, _ in cell_letters[adj_cell]]
                    for d_p in down_ps:
                        for adj_p in adj_ps:
                            if adj_p != d_p and adj_p not in across_ps:
                                model.Add(x[d_p] + x[adj_p] <= 1)

    # C6: Objective Function — Maximize Intersections (Linear Product Constraints)
    intersection_vars = []
    for a_p, d_p in set(intersection_pairs):
        ix = model.NewBoolVar(f"ix_{a_p}_{d_p}")
        model.Add(ix <= x[a_p])
        model.Add(ix <= x[d_p])
        model.Add(ix >= x[a_p] + x[d_p] - 1)
        intersection_vars.append(ix)

    if intersection_vars:
        model.Maximize(sum(intersection_vars))

    # 4. Configure C++ Solver & Thread Capping
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = timeLimitSeconds
    solver.parameters.num_search_workers = 2  # Production CPU thread guardrail

    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        result = []
        for i in range(N):
            if solver.Value(x[i]):
                p = placements[i]
                result.append({
                    "slot_id": f"S{len(result) + 1}",
                    "word": p[2],
                    "movie": p[3],
                    "length": p[7],
                    "row": p[4],
                    "col": p[5],
                    "direction": p[6]
                })
        if len(result) == targetCount:
            logger.info(f"Production OR-Tools solved crossword: {len(result)} words, "
                        f"{solver.ObjectiveValue():.0f} intersections")
            return result

    return None

# 3. FAST-PATH SOLVER: Greedy Freeform (< 1ms)

def solveFreeform(
    candidateWords: List[Dict[str, Any]],
    targetCount: int = 6,
    gridSize: int = 10,
    maxRetries: int = 30
) -> Optional[List[Dict[str, Any]]]:
    """
    Greedy freeform crossword solver used as a fast-path solver (< 1ms).
    """
    valid_candidates = [w for w in candidateWords if w.get("clean_title") and 3 <= len(w.get("clean_title")) <= 10]
    if not valid_candidates:
        return None

    # Cap to top 35 candidate words to keep greedy shuffle loops fast (< 20ms)
    valid_candidates = valid_candidates[:35]

    for attempt in range(maxRetries):
        shuffled = list(valid_candidates)
        random.shuffle(shuffled)
        
        grid = [["" for _ in range(gridSize)] for _ in range(gridSize)]
        placed = []
        placed_titles: Set[str] = set()
        placed_stems: Set[str] = set()

        seed_movie = shuffled[0]
        seed_word = seed_movie["clean_title"]
        seed_stem = get_title_stem(seed_word)
        seed_len = len(seed_word)
        seed_r = 3
        seed_c = max(1, (gridSize - seed_len) // 2)

        if not isValidFreeformPlacement(grid, seed_word, seed_r, seed_c, "ACROSS", gridSize):
            continue

        for i, ch in enumerate(seed_word):
            grid[seed_r][seed_c + i] = ch
        placed.append({
            "slot_id": "S1",
            "word": seed_word,
            "movie": seed_movie,
            "length": seed_len,
            "row": seed_r,
            "col": seed_c,
            "direction": "ACROSS"
        })
        placed_titles.add(seed_word)
        placed_stems.add(seed_stem)

        for cand in shuffled[1:]:
            if len(placed) >= targetCount:
                break
            
            clean_word = cand["clean_title"]
            cand_stem = get_title_stem(clean_word)
            if clean_word in placed_titles or cand_stem in placed_stems:
                continue


            placed_this_word = False
            for p in list(placed):
                if placed_this_word:
                    break
                p_word = p["word"]
                p_r, p_c = p["row"], p["col"]
                p_dir = p["direction"]

                for p_idx, p_ch in enumerate(p_word):
                    if placed_this_word:
                        break
                    cell_r = p_r if p_dir == "ACROSS" else p_r + p_idx
                    cell_c = p_c + p_idx if p_dir == "ACROSS" else p_c
                    new_dir = "DOWN" if p_dir == "ACROSS" else "ACROSS"

                    for w_idx, w_ch in enumerate(clean_word):
                        if w_ch == p_ch:
                            new_r = cell_r if new_dir == "ACROSS" else cell_r - w_idx
                            new_c = cell_c - w_idx if new_dir == "ACROSS" else cell_c

                            if isValidFreeformPlacement(grid, clean_word, new_r, new_c, new_dir, gridSize):
                                for idx, ch in enumerate(clean_word):
                                    gr = new_r if new_dir == "ACROSS" else new_r + idx
                                    gc = new_c + idx if new_dir == "ACROSS" else new_c
                                    grid[gr][gc] = ch
                                
                                placed.append({
                                    "slot_id": f"S{len(placed) + 1}",
                                    "word": clean_word,
                                    "movie": cand,
                                    "length": len(clean_word),
                                    "row": new_r,
                                    "col": new_c,
                                    "direction": new_dir
                                })
                                placed_titles.add(clean_word)
                                placed_stems.add(cand_stem)
                                placed_this_word = True
                                break


        if len(placed) >= targetCount:
            return placed

    return None

# 4. PUBLIC ENTRY POINT (Production Hybrid Cascade)


def solveCrossword(
    candidateWords: List[Dict[str, Any]],
    targetCount: int = 6,
    gridSize: int = 10
) -> Optional[List[Dict[str, Any]]]:
    """
    Production entry point for crossword level generation.
    1. Primary: Exact Google OR-Tools CP-SAT solver for maximum intersections & layout optimality.
    2. Fallback: Fast geometric freeform solver.
    """
    # 1. Primary: Google OR-Tools CP-SAT
    result = solveWithORTools(
        candidateWords,
        targetCount=targetCount,
        gridSize=gridSize,
        timeLimitSeconds=SOLVER_TIME_LIMIT_S,
        maxCandidates=25
    )
    if result:
        return result

    # 2. Resilient Fallback
    logger.info("OR-Tools did not find a layout within time limit, executing freeform fallback.")
    return solveFreeform(candidateWords, targetCount=targetCount, gridSize=gridSize, maxRetries=50)



def calculateLayoutScore(placed: List[Dict[str, Any]]) -> float:
    """Evaluates grid visual layout score based on intersections, aspect ratio, and area."""
    if not placed:
        return -100000.0

    grid: Dict[Tuple[int, int], Set[str]] = {}
    for w in placed:
        word = w["word"]
        r, c = w["row"], w["col"]
        direction = w["direction"]
        for i in range(len(word)):
            cell = (r if direction == "ACROSS" else r + i, c + i if direction == "ACROSS" else c)
            grid.setdefault(cell, set()).add("ACROSS" if direction == "ACROSS" else "DOWN")

    intersections = sum(1 for dirs in grid.values() if len(dirs) > 1)

    rows, cols = [], []
    for w in placed:
        wordLen = len(w["word"])
        r, c = w["row"], w["col"]
        if w["direction"] == "ACROSS":
            rows.append(r)
            cols.extend([c, c + wordLen - 1])
        else:
            rows.extend([r, r + wordLen - 1])
            cols.append(c)

    minR, maxR = min(rows), max(rows)
    minC, maxC = min(cols), max(cols)
    width = maxC - minC + 1
    height = maxR - minR + 1
    area = width * height
    ratio = min(width, height) / max(width, height)

    return (intersections * 25.0) + (ratio * 15.0) - (area * 0.15)
