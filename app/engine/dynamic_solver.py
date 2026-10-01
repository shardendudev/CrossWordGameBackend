from typing import List, Dict, Tuple, Optional, Set, Any
import random
import logging

logger = logging.getLogger(__name__)


import re

def get_title_stem(title:str) -> str:
    """Normalises clean title or title into a base franchise stem to prevent multiple movies from the same franchise to be placed in same level."""

    s = title.upper().strip()
    s = re.sub(r'(\b|_)?(PART|VOL|VOLUME|CHAPTER|EPISODE|SEASON)\b.*$', '', s)
    s = re.sub(r'(\d+|II|III|IV|V|VI|VII|VIII|IX|X)+$', '', s)
    s = s.strip()
    return s if len(s) >= 3 else title.upper().strip()

def isValidDynamicPlacement(
    grid: List[List[str]],
    word: str,
    r: int,
    c: int,
    direction: str,
    rows: int= 12,
    cols: int = 10,
    occupied_directions: Optional[Dict[Tuple[int,int], Set[str]]] = None
) -> bool:
    """
    Validates dynamic freeform word placmenet on a non-swquare dynamic (rows x cols ) grid:
    - End-cap Buffer: Cells before start and end must be empty.
    - Side- by- side buffer: Non-intersection side cells MUST be empty.
    - Same-Direction Overlap: Reject if cell is already occupied by the same direction.
    """

    length = len(word)

    #1. Grid Bounds & End-Cap Buffers
    if direction == "ACROSS":
        #cannot fit horizontally if word is longer than cols
        if c < 0 or c+length > cols or r < 0 or r>=rows:
            return False
        
        if c-1>=0 and grid[r][c-1] != "":
            return False

        if c+length < cols and grid[r][c+length] != "":
            return False

    if direction == "DOWN":
        #cannot fit vertically if word is longer than rows
        if r < 0 or r+length > rows or c<0 or c>=cols:
            return False

        if r - 1>=0 and grid[r-1][c] != "":
            return False

        if r+length < rows and grid[r+length][c] != "":
            return False

    #2. Cell occupancy, Letter consistency and side adjacency
    for i,ch in enumerate(word):
        curr_r = r if direction =="ACROSS" else r+i
        curr_c = c+i if direction == "ACROSS" else c
        existing = grid[curr_r][curr_c]

        if existing != "" and existing != ch:
            return False #letter conflict

        if existing !="":
            #only perpendicular intersections are allowed
            if occupied_directions and direction in occupied_directions.get((curr_r,curr_c),set()):
                return False

        if existing == "":
            if direction == "ACROSS":
                if curr_r - 1>= 0 and grid[curr_r -1][curr_c] != "":
                    return False

                if curr_r + 1 < rows and grid[curr_r + 1][curr_c] != "":
                    return False
            
            else: #DOWN
                if curr_c - 1>=0 and grid[curr_r][curr_c - 1] != "":
                    return False

                if curr_c + 1 < cols and grid[curr_r][curr_c+1] != "":
                    return False

    return True


def solveDynamicFreeform(
    candidateWords: List[Dict[str,Any]],
    targetCount: int = 6,
    rows: int=12,
    cols: int = 10,
    maxRetries: int = 60
) -> Optional[List[Dict[str, Any]]]:
    """
    Dynamic greedy freeform solver for non-square grids(e.g 12 rows x 10 cols).
    - Titles > cols (e.g. 11-12 chars) are strictly restricted to vertical ('DOWN') placement.
    """

    max_len = max(rows,cols)
    valid_candidates = [
        w for w in candidateWords
        if w.get("clean_title") and 3 <= len(w["clean_title"]) <= max_len
    ]

    if not valid_candidates:
        return None

    

    #Cap to top 40 candidates for fast shuffle loops
    valid_candidates = valid_candidates[:40]

    for attempt in range(maxRetries):
        shuffled = list(valid_candidates)
        random.shuffle(shuffled)

        grid = [["" for _ in range(cols)] for _ in range(rows)]
        placed: List[Dict[str,Any]] = []
        placed_titles: Set[str] = set()
        placed_stems: Set[str] = set()
        occupied_dirs: Dict[Tuple[int,int], Set[str]] = {}


        #1. seed placement
        seed_movie = shuffled[0]
        seed_word = seed_movie["clean_title"]
        seed_stem = get_title_stem(seed_word)
        seed_len = len(seed_word)

        #If seed word exceeds column count, force it DOWN; otherwise start ACROSS
        if seed_len <= cols:
            seed_dir = "ACROSS"
            seed_r = rows // 3
            seed_c = max(0, (cols - seed_len) // 2)
        
        else:
            seed_dir = "DOWN"
            seed_r = max(0,(rows - seed_len) // 2)
            seed_c = cols//2

        if not isValidDynamicPlacement(grid, seed_word, seed_r, seed_c, seed_dir, rows, cols, occupied_dirs):
            continue

        for i,ch in enumerate(seed_word):
            gr = seed_r if seed_dir == "ACROSS" else seed_r+i
            gc = seed_c + i if seed_dir == "ACROSS" else seed_c
            grid[gr][gc] = ch
            occupied_dirs.setdefault((gr,gc), set()).add(seed_dir)

        
        placed.append({
            "slot_id":"S1",
            "word":seed_word,
            "movie":seed_movie,
            "length": seed_len,
            "row": seed_r,
            "col":seed_c,
            "direction":seed_dir
        })
        placed_titles.add(seed_word)
        placed_stems.add(seed_stem)


        #2. Intersecting placement of remaining candidates
        for cand in shuffled[1:]:
            if len(placed) >= targetCount:
                break

            clean_word = cand["clean_title"]
            cand_stem = get_title_stem(clean_word)
            cand_len = len(clean_word)


            if clean_word in placed_titles or cand_stem in placed_stems:
                continue

            placed_this_word = False
            for p in list(placed):
                if placed_this_word:
                    break

                p_word = p["word"]
                p_r, p_c = p["row"], p["col"]
                p_dir = p["direction"]


                #New word must run perpendicular to existing_word
                new_dir = "DOWN" if p_dir == "ACROSS" else "ACROSS"

                #Constraint: words longer than cols can never be placed ACROSS
                if new_dir == "ACROSS" and cand_len > cols:
                    continue


                for p_idx, p_ch in enumerate(p_word):
                    if placed_this_word:
                        break
                
                    #1. Absolute grid coordinate of letter in placed word
                    cell_r = p_r if p_dir == "ACROSS" else p_r + p_idx
                    cell_c = p_c + p_idx if p_dir == "ACROSS" else p_c


                    #2. Look for matching letter in candidate word
                    for w_idx,w_ch in enumerate(clean_word):
                        if w_ch == p_ch:
                            #3. Calculate candidate start coordinate so letter aligns at (cell_r,cell_c)

                            new_r = cell_r if new_dir == "ACROSS" else cell_r - w_idx
                            new_c = cell_c - w_idx if new_dir == "ACROSS" else cell_c

                            #4. Check if this placement satisfies all rules
                            if isValidDynamicPlacement(grid, clean_word, new_r, new_c, new_dir, rows, cols, occupied_dirs):
                                #commit letters to grid
                                for idx, ch in enumerate(clean_word):
                                    gr = new_r if new_dir == "ACROSS" else new_r + idx
                                    gc = new_c + idx if new_dir == "ACROSS"  else new_c

                                    grid[gr][gc] = ch
                                    occupied_dirs.setdefault((gr,gc), set()).add(new_dir)

                                placed.append({
                                    "slot_id": f"S{len(placed) + 1}",
                                    "word":clean_word,
                                    "movie":cand,
                                    "length":cand_len,
                                    "row":new_r,
                                    "col":new_c,
                                    "direction":new_dir
                                })

                                placed_titles.add(clean_word)
                                placed_stems.add(cand_stem)
                                placed_this_word = True
                                break
        
        if len(placed) >= targetCount:
            return placed


    return None                    
