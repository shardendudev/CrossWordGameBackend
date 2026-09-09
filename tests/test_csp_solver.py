import pytest
from app.engine.csp_solver import solveCrossword


def test_solveCrossword_set_1():
    sample_candidates = [
        {"imdb_id": "tt0499549", "title": "Avatar", "clean_title": "AVATAR"},
        {"imdb_id": "tt0120338", "title": "Titanic", "clean_title": "TITANIC"},
        {"imdb_id": "tt0133093", "title": "Matrix", "clean_title": "MATRIX"},
        {"imdb_id": "tt0078748", "title": "Alien", "clean_title": "ALIEN"},
        {"imdb_id": "tt7286456", "title": "Joker", "clean_title": "JOKER"},
        {"imdb_id": "tt0371724", "title": "Batman", "clean_title": "BATMAN"},
        {"imdb_id": "tt1375666", "title": "Inception", "clean_title": "INCEPTION"},
        {"imdb_id": "tt0172495", "title": "Gladiator", "clean_title": "GLADIATOR"},
    ]

    _run_and_render_solver("SET 1: SCI-FI & ACTION", sample_candidates)


def test_solveCrossword_set_2():
    sample_candidates = [
        {"imdb_id": "tt0068646", "title": "Godfather", "clean_title": "GODFATHER"},
        {"imdb_id": "tt0137523", "title": "Fight Club", "clean_title": "FIGHTCLUB"},
        {"imdb_id": "tt2582802", "title": "Whiplash", "clean_title": "WHIPLASH"},
        {"imdb_id": "tt0054215", "title": "Psycho", "clean_title": "PSYCHO"},
        {"imdb_id": "tt0093773", "title": "Predator", "clean_title": "PREDATOR"},
        {"imdb_id": "tt0090605", "title": "Aliens", "clean_title": "ALIENS"},
        {"imdb_id": "tt0114369", "title": "Seven", "clean_title": "SEVEN"},
        {"imdb_id": "tt1160419", "title": "Dune", "clean_title": "DUNE"},
    ]

    _run_and_render_solver("SET 2: DRAMA & THRILLERS", sample_candidates)


def test_solveCrossword_prevents_franchise_duplicates():
    # Includes both Toy Story and Toy Story 3
    sample_candidates = [
        {"imdb_id": "tt0114709", "title": "Toy Story", "clean_title": "TOYSTORY"},
        {"imdb_id": "tt0435761", "title": "Toy Story 3", "clean_title": "TOYSTORY3"},
        {"imdb_id": "tt0137523", "title": "Fight Club", "clean_title": "FIGHTCLUB"},
        {"imdb_id": "tt0120338", "title": "Titanic", "clean_title": "TITANIC"},
        {"imdb_id": "tt0172495", "title": "Gladiator", "clean_title": "GLADIATOR"},
        {"imdb_id": "tt0133093", "title": "Matrix", "clean_title": "MATRIX"},
        {"imdb_id": "tt0078748", "title": "Alien", "clean_title": "ALIEN"},
        {"imdb_id": "tt7286456", "title": "Joker", "clean_title": "JOKER"},
    ]
    placements = solveCrossword(sample_candidates, targetCount=6, gridSize=10)
    assert placements is not None
    words = [p["word"] for p in placements]
    # Ensure BOTH TOYSTORY and TOYSTORY3 are not present in the same level
    assert not ("TOYSTORY" in words and "TOYSTORY3" in words), "Franchise titles Toy Story & Toy Story 3 must not coexist in the same level!"



def _run_and_render_solver(test_name: str, candidates: list):
    placements = solveCrossword(candidates, targetCount=6, gridSize=10)

    # Assertions
    assert placements is not None, f"[{test_name}] Solver failed to generate placement layout"
    assert len(placements) == 6, f"[{test_name}] Expected 6 placed words, got {len(placements)}"

    # Construct visual grid
    grid = [["." for _ in range(10)] for _ in range(10)]
    print("\n\n" + "=" * 60)
    print(f" 🎬 OR-TOOLS CP-SAT CROSSWORD SOLVER TEST — {test_name}")
    print("=" * 60)
    print(f"\n Successfully placed {len(placements)} movies on 10x10 grid:\n")

    for p in placements:
        print(f"  • [{p['direction']:6s}] {p['word']:10s} | Start: (row {p['row']}, col {p['col']})")
        for i, ch in enumerate(p["word"]):
            r = p["row"] if p["direction"] == "ACROSS" else p["row"] + i
            c = p["col"] + i if p["direction"] == "ACROSS" else p["col"]
            grid[r][c] = ch

    print("\n 🧩 10x10 VISUAL CROSSWORD GRID:")
    print("  +" + "---+" * 10)
    for r in grid:
        print("  | " + " | ".join(r) + " |")
    print("  +" + "---+" * 10 + "\n")
