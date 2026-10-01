import pytest
from app.engine.dynamic_solver import solveDynamicFreeform, isValidDynamicPlacement, get_title_stem


def test_dynamic_solver_12x10_long_word_vertical():
    sample_candidates = [
        {"imdb_id": "tt0816692", "title": "Interstellar", "clean_title": "INTERSTELLAR"},  # len 12
        {"imdb_id": "tt0499549", "title": "Avatar", "clean_title": "AVATAR"},              # len 6
        {"imdb_id": "tt0120338", "title": "Titanic", "clean_title": "TITANIC"},            # len 7
        {"imdb_id": "tt0133093", "title": "Matrix", "clean_title": "MATRIX"},              # len 6
        {"imdb_id": "tt0078748", "title": "Alien", "clean_title": "ALIEN"},                # len 5
        {"imdb_id": "tt7286456", "title": "Joker", "clean_title": "JOKER"},                # len 5
        {"imdb_id": "tt0371724", "title": "Batman", "clean_title": "BATMAN"},              # len 6
        {"imdb_id": "tt1375666", "title": "Inception", "clean_title": "INCEPTION"},        # len 9
    ]

    placements = solveDynamicFreeform(sample_candidates, targetCount=6, rows=12, cols=10)
    assert placements is not None, "Solver failed to place 6 words on 12x10 grid"
    assert len(placements) == 6

    for p in placements:
        # Check boundary bounds
        if p["direction"] == "ACROSS":
            assert p["col"] + p["length"] <= 10
            assert p["row"] < 12
        else:
            assert p["row"] + p["length"] <= 12
            assert p["col"] < 10

        # Enforce that INTERSTELLAR (len 12) is strictly DOWN
        if p["length"] > 10:
            assert p["direction"] == "DOWN", f"Word {p['word']} (len {p['length']}) must be placed DOWN"


def test_dynamic_solver_custom_dimensions_and_movie_count():
    sample_candidates = [
        {"imdb_id": "tt0816692", "title": "Interstellar", "clean_title": "INTERSTELLAR"},
        {"imdb_id": "tt0499549", "title": "Avatar", "clean_title": "AVATAR"},
        {"imdb_id": "tt0120338", "title": "Titanic", "clean_title": "TITANIC"},
        {"imdb_id": "tt0133093", "title": "Matrix", "clean_title": "MATRIX"},
        {"imdb_id": "tt0078748", "title": "Alien", "clean_title": "ALIEN"},
        {"imdb_id": "tt7286456", "title": "Joker", "clean_title": "JOKER"},
        {"imdb_id": "tt0371724", "title": "Batman", "clean_title": "BATMAN"},
        {"imdb_id": "tt1375666", "title": "Inception", "clean_title": "INCEPTION"},
        {"imdb_id": "tt0172495", "title": "Gladiator", "clean_title": "GLADIATOR"},
    ]

    # Test 14 rows x 11 cols with 7 movies
    placements = solveDynamicFreeform(sample_candidates, targetCount=7, rows=14, cols=11)
    assert placements is not None
    assert len(placements) == 7

    for p in placements:
        if p["direction"] == "ACROSS":
            assert p["col"] + p["length"] <= 11
            assert p["row"] < 14
        else:
            assert p["row"] + p["length"] <= 14
            assert p["col"] < 11


def test_dynamic_solver_prevents_franchise_duplicates():
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
    placements = solveDynamicFreeform(sample_candidates, targetCount=6, rows=12, cols=10)
    assert placements is not None
    words = [p["word"] for p in placements]
    assert not ("TOYSTORY" in words and "TOYSTORY3" in words), "Franchise titles must not coexist in the same level"
