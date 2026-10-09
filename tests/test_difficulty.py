import pytest
import numpy as np
from app.engine.difficulty import (
    calculateBaseDifficulty,
    calculateExpectedTime,
    calculatePerformanceRatio,
    calculateCommercialImpact,
    calculateVoteVolume,
    calculateAwardsBonus,
    updateUserSkill,
    updateTasteVector,
)
@pytest.mark.parametrize("kwargs",[{},
{"imdbVotes":0,"imdbRating":0,"budget":0,"revenue":0, "awardsSummary":"","lowContext":True},
{"imdbVotes":5000000,"imdbRating":10.0,"budget":1000000,"revenue":3000000000},
{"imdbVotes":-50,"imdbRating":-2.0,"budget":-100},
{"imdbVotes":250000,"imdbRating":7.5}])
def test_boundedness_and_default_values(kwargs):
    result = calculateBaseDifficulty(**kwargs)

    print(result)
    assert isinstance(result,float)

    assert 0.0 <= result <= 1.0


def test_difficulty_for_extremes():
    blockbuster_args = {"imdbVotes":2500000,"imdbRating":9.0,"revenue":2000000000,"awardsSummary":"Won 3 Oscars","lowContext":False}
    indie_args = {"imdbVotes":50,"imdbRating":4.0,"budget":0,"revenue":0,"awardsSummary":"","lowContext":True}
    blockbuster_diff = calculateBaseDifficulty(**blockbuster_args)
    indie_diff = calculateBaseDifficulty(**indie_args)

    print(blockbuster_diff,indie_diff)
    assert blockbuster_diff < indie_diff
    assert blockbuster_diff < 0.20
    assert indie_diff > 0.85



def test_feature_sensitivity():
    baseline = {"imdbVotes": 50_000, "imdbRating": 7.0, "revenue": 50_000_000}
    lowVote_diff = calculateBaseDifficulty(imdbVotes=1000)
    highVote_diff = calculateBaseDifficulty(imdbVotes=500000)
    print(lowVote_diff,highVote_diff)
    assert highVote_diff < lowVote_diff

    no_awards_diff = calculateBaseDifficulty(**baseline,awardsSummary="")
    high_awards_diff = calculateBaseDifficulty(**baseline,awardsSummary="Won 10 Oscars")
    print(no_awards_diff,high_awards_diff)

    assert no_awards_diff > high_awards_diff

    low_context_diff = calculateBaseDifficulty(**baseline,lowContext=True)
    high_context_diff = calculateBaseDifficulty(**baseline,lowContext=False)

    print(low_context_diff, high_context_diff)
    assert low_context_diff > high_context_diff

    baselineCommercial = {"imdbVotes": 50000, "imdbRating": 7.0, "year": 2000}

    low_commercial_diff = calculateBaseDifficulty(**baselineCommercial, revenue=0, budget=0)
    high_commercial_diff = calculateBaseDifficulty(**baselineCommercial, revenue=500_000_000, budget=100_000_000)

    print(low_commercial_diff, high_commercial_diff)
    assert low_commercial_diff > high_commercial_diff


def test_performance_ratio():
    # 1. Baseline Equilibrium
    p_baseline = calculatePerformanceRatio(timeTakenSeconds=100.0, expectedTimeSeconds=100.0)
    assert p_baseline == 1.0
    # 2. Fast solve (2x speed)
    p_fast = calculatePerformanceRatio(timeTakenSeconds=50.0, expectedTimeSeconds=100.0)
    assert p_fast == 2.0
    # 3. Slow with hints & errors
    p_struggle = calculatePerformanceRatio(
        timeTakenSeconds=150.0,
        expectedTimeSeconds=100.0,
        freeHints=2,
        premiumHints=1,
        errors=3
    )
    assert p_struggle < 0.50
    # 4. Anti-cheat cap (ratio 20x capped at 3.0)
    p_instant = calculatePerformanceRatio(timeTakenSeconds=5.0, expectedTimeSeconds=100.0)
    assert p_instant == 3.0


def test_user_skill_update():
    # 1. Equilibrium: skill unchanged
    s_steady = updateUserSkill(currentSkill=0.50, pLevel=1.0)
    assert s_steady == 0.50

    # 2. Good game increases skill
    s_up = updateUserSkill(currentSkill=0.50, pLevel=2.0)
    assert s_up > 0.50

    # 3. Bad game decreases skill
    s_down = updateUserSkill(currentSkill=0.50, pLevel=0.50)
    assert s_down < 0.50

    # 4. Boundary clamping [0.05, 0.95]
    s_max = updateUserSkill(currentSkill=0.95, pLevel=3.0)
    assert s_max == 0.95

    s_min = updateUserSkill(currentSkill=0.05, pLevel=0.10)
    assert s_min == 0.05


def test_taste_vector_update():
    # 1. Cold start with 2 movies
    m1 = [1.0, 0.0, 0.0]
    m2 = [0.0, 1.0, 0.0]
    cold_vector = updateTasteVector(currentVector=None, solvedMovieVector=[m1, m2])
    
    # Must be unit length
    assert np.isclose(np.linalg.norm(cold_vector), 1.0)

    # 2. Existing profile updated with new level
    current = [1.0, 0.0, 0.0]
    new_level = [[0.0, 1.0, 0.0]]
    updated = updateTasteVector(currentVector=current, solvedMovieVector=new_level, beta=0.85)

    # Length must still be 1.0
    assert np.isclose(np.linalg.norm(updated), 1.0)
    # 85% inertia means the 1st component should still dominate (> 0.90)
    assert updated[0] > 0.90
    assert updated[1] > 0.10



@pytest.mark.parametrize(
    "name, budget, revenue, year, expected_b_norm",
    [
        # Era 1: Pre-1980 (< 1980, Ceiling = $150M)
        (
            "pre_1980_modest_hit",
            4_000_000,
            10_000_000,
            1965,
            0.65 * (10 / 150) + 0.35 * (2.5 / 5.0),
        ),
        (
            "pre_1980_phenomenon_capped",
            11_000_000,
            150_000_000,
            1977,
            1.0,
        ),
        (
            "pre_1980_boundary_year_1979",
            10_000_000,
            75_000_000,
            1979,
            0.65 * 0.50 + 0.35 * 1.0,
        ),

        # Era 2: 1980 - 1999 (Ceiling = $800M)
        (
            "era_1980_boundary_start",
            50_000_000,
            400_000_000,
            1980,
            0.65 * 0.50 + 0.35 * 1.0,
        ),
        (
            "era_1990s_blockbuster",
            63_000_000,
            800_000_000,
            1993,
            1.0,
        ),
        (
            "era_1999_boundary_end",
            15_000,
            100_000_000,
            1999,
            0.65 * (100 / 800) + 0.35 * 1.0,
        ),

        # Era 3: 2000+ (Ceiling = $2.5B)
        (
            "modern_avatar_phenomenon",
            237_000_000,
            2_500_000_000,
            2009,
            1.0,
        ),
        (
            "modern_solid_hit",
            100_000_000,
            500_000_000,
            2018,
            0.65 * (500 / 2500) + 0.35 * 1.0,
        ),
        (
            "modern_box_office_bomb",
            200_000_000,
            20_000_000,
            2020,
            0.65 * (20 / 2500) + 0.35 * (0.1 / 5.0),
        ),

        # Streaming / Missing Revenue (Volume falls back to budget)
        (
            "streaming_original_known_budget",
            100_000_000,
            0,
            2022,
            0.65 * (100 / 2500) + 0.35 * 0.50,
        ),

        # Completely Missing / Zero Data
        (
            "complete_missing_data",
            0,
            0,
            2015,
            0.65 * 0.0 + 0.35 * 0.50,
        ),

        # 1. Type Safety & Dirty Data (None & Negatives)
        (
            "none_values_fallback",
            None,
            None,
            2015,
            0.65 * 0.0 + 0.35 * 0.50,
        ),
        (
            "negative_bad_data_clamped",
            -50_000_000,
            -100_000_000,
            2015,
            0.65 * 0.0 + 0.35 * 0.50,
        ),
        (
            "revenue_known_budget_zero_division_safe",
            0,
            10_000_000,
            2018,
            0.65 * (10 / 2500) + 0.35 * 0.50,
        ),
        (
            "revenue_known_budget_none",
            None,
            50_000_000,
            2018,
            0.65 * (50 / 2500) + 0.35 * 0.50,
        ),

        # 2. Micro-Budget Phenomenon (Paranormal Activity ROI ~12,800x capped at 1.0)
        (
            "microbudget_phenomenon_paranormal_activity",
            15_000,
            193_000_000,
            2007,
            0.65 * (193 / 2500) + 0.35 * 1.0,
        ),

        # 3. Hollywood Industry Multiplier Benchmarks (2.5x Break-Even, 5x Mega-Hit, 1x Flop)
        (
            "hollywood_breakeven_2_5x_roi",
            100_000_000,
            250_000_000,
            2015,
            0.65 * (250 / 2500) + 0.35 * 0.50,
        ),
        (
            "hollywood_megahit_5x_roi",
            50_000_000,
            250_000_000,
            2015,
            0.65 * (250 / 2500) + 0.35 * 1.0,
        ),
        (
            "hollywood_underperformer_1x_roi",
            100_000_000,
            100_000_000,
            2015,
            0.65 * (100 / 2500) + 0.35 * (1.0 / 5.0),
        ),

        # 4. Overflow / Beyond Ceiling Super-Blockbuster
        (
            "super_blockbuster_exceeding_ceiling_capped",
            250_000_000,
            3_000_000_000,
            2023,
            1.0,
        ),

        # 5. Historic Silent Era (Pre-1980 Ceiling = $150M)
        (
            "silent_era_historic_1927_metropolis",
            1_300_000,
            5_000_000,
            1927,
            0.65 * (5 / 150) + 0.35 * ((5.0 / 1.3) / 5.0),
        ),
    ],
)
def test_commercial_impact_exact_scenarios(name, budget, revenue, year, expected_b_norm):
    """Verifies exact era ceilings, volume fallbacks, profit terms, and final scores."""
    b_norm = calculateCommercialImpact(revenue=revenue, budget=budget, year=year)
    assert b_norm == pytest.approx(expected_b_norm, abs=1e-4)
    assert 0.0 <= b_norm <= 1.0


def test_commercial_impact_edge_cases_and_robustness():
    """Verifies relative orderings, hit vs flop, era scaling, and boundary transitions."""
    # 1. Missing data yields neutral baseline (0.175)
    score_zero = calculateCommercialImpact(revenue=0, budget=0, year=2010)
    score_none = calculateCommercialImpact(revenue=None, budget=None, year=2010)
    assert score_zero == pytest.approx(0.175, abs=1e-4)
    assert score_none == pytest.approx(0.175, abs=1e-4)

    # 2. Flop vs Hit with same revenue ($150M) in modern era
    score_hit = calculateCommercialImpact(revenue=150_000_000, budget=25_000_000, year=2010)
    print(f"score_hit : {score_hit}")
    score_flop = calculateCommercialImpact(revenue=150_000_000, budget=300_000_000, year=2010)
    print(f"score_flop : {score_flop}")
    assert score_hit > score_flop

    # 3. Same $50M revenue has higher impact in 1965 ($150M ceiling) than 1995 ($800M) and 2015 ($2.5B)
    score_1965 = calculateCommercialImpact(revenue=50_000_000, budget=10_000_000, year=1965)
    print(f"score_1965 : {score_1965}")
    score_1995 = calculateCommercialImpact(revenue=50_000_000, budget=10_000_000, year=1995)
    print(f"score_1995 : {score_1995}")
    score_2015 = calculateCommercialImpact(revenue=50_000_000, budget=10_000_000, year=2015)
    print(f"score_2015 : {score_2015}")
    assert score_1965 > score_1995 > score_2015

    # 4. Monotonicity: Higher revenue with same budget strictly increases commercial score
    score_low = calculateCommercialImpact(revenue=50_000_000, budget=50_000_000, year=2010)
    score_mid = calculateCommercialImpact(revenue=200_000_000, budget=50_000_000, year=2010)
    score_high = calculateCommercialImpact(revenue=500_000_000, budget=50_000_000, year=2010)
    print(f"score_low:{score_low}, score_mid: {score_mid}, score_high: {score_high}")
    assert score_low < score_mid < score_high

    # 5. Volume Equivalence: Box office only vs Streaming budget only
    score_bo_only = calculateCommercialImpact(revenue=100_000_000, budget=0, year=2020)
    score_stream_only = calculateCommercialImpact(revenue=0, budget=100_000_000, year=2020)
    assert score_bo_only == pytest.approx(score_stream_only, abs=1e-4)

    # 6. Era Boundary Steps: 1979 vs 1980 ($150M vs $800M ceiling)
    score_boundary_1979 = calculateCommercialImpact(revenue=100_000_000, budget=20_000_000, year=1979)
    score_boundary_1980 = calculateCommercialImpact(revenue=100_000_000, budget=20_000_000, year=1980)
    print(f"score_boundary_1979:{score_boundary_1979}, score_boundary_1980: {score_boundary_1980}")
    assert score_boundary_1979 > score_boundary_1980

    # 7. Era Boundary Steps: 1999 vs 2000 ($800M vs $2.5B ceiling)
    score_boundary_1999 = calculateCommercialImpact(revenue=500_000_000, budget=50_000_000, year=1999)
    score_boundary_2000 = calculateCommercialImpact(revenue=500_000_000, budget=50_000_000, year=2000)
    print(f"score_boundary_1999:{score_boundary_1999}, score_boundary_2000: {score_boundary_2000}")

    assert score_boundary_1999 > score_boundary_2000

    # 8. Future Release Year Support
    score_future_2028 = calculateCommercialImpact(revenue=500_000_000, budget=100_000_000, year=2028)
    score_present_2024 = calculateCommercialImpact(revenue=500_000_000, budget=100_000_000, year=2024)
    assert score_future_2028 == pytest.approx(score_present_2024, abs=1e-4)

    # 9. Break-Even vs Missing Baseline Property:
    # A flop (< 2.5x ROI) is worse than neutral missing data with same volume; a hit (> 2.5x ROI) is better.
    score_neutral = calculateCommercialImpact(revenue=100_000_000, budget=0, year=2020)
    score_profitable = calculateCommercialImpact(revenue=100_000_000, budget=25_000_000, year=2020)  # 4x ROI
    score_loss_maker = calculateCommercialImpact(revenue=100_000_000, budget=100_000_000, year=2020)  # 1x ROI
    assert score_profitable > score_neutral > score_loss_maker


# =====================================================================
# Comprehensive Unit Tests for calculateVoteVolume
# =====================================================================

@pytest.mark.parametrize(
    "name, imdb_votes, min_votes, max_votes, expected_v_norm",
    [
        # Minimum Boundary & Below Minimum (Clamped to 0.0)
        ("zero_votes", 0, 100, 2_500_000, 0.0),
        ("none_votes", None, 100, 2_500_000, 0.0),
        ("negative_votes", -100, 100, 2_500_000, 0.0),
        ("sub_threshold_50", 50, 100, 2_500_000, 0.0),
        ("exact_min_100", 100, 100, 2_500_000, 0.0),

        # Maximum Boundary & Above Maximum (Clamped to 1.0)
        ("exact_max_ceiling", 2_500_000, 100, 2_500_000, 1.0),
        ("above_max_ceiling", 3_500_000, 100, 2_500_000, 1.0),

        # Intermediate Popularity Tiers
        (
            "indie_tier_1k",
            1_000,
            100,
            2_500_000,
            (np.log10(1_001) - np.log10(101)) / (np.log10(2_500_001) - np.log10(101)),
        ),
        (
            "cult_tier_10k",
            10_000,
            100,
            2_500_000,
            (np.log10(10_001) - np.log10(101)) / (np.log10(2_500_001) - np.log10(101)),
        ),
        (
            "popular_tier_100k",
            100_000,
            100,
            2_500_000,
            (np.log10(100_001) - np.log10(101)) / (np.log10(2_500_001) - np.log10(101)),
        ),
        (
            "blockbuster_tier_1m",
            1_000_000,
            100,
            2_500_000,
            (np.log10(1_000_001) - np.log10(101)) / (np.log10(2_500_001) - np.log10(101)),
        ),

        # Custom Min / Max Bounds
        (
            "custom_bounds_midpoint",
            1_000,
            10,
            100_000,
            (np.log10(1_001) - np.log10(11)) / (np.log10(100_001) - np.log10(11)),
        ),
    ],
)
def test_vote_volume_exact_scenarios(name, imdb_votes, min_votes, max_votes, expected_v_norm):
    """Verifies boundary clamps, scale normalization, and exact logarithmic values."""
    v_norm = calculateVoteVolume(imdbVotes=imdb_votes, minVotes=min_votes, maxVotes=max_votes)
    assert v_norm == pytest.approx(expected_v_norm, abs=1e-5)
    assert 0.0 <= v_norm <= 1.0


def test_vote_volume_properties_and_robustness():
    """Verifies strict monotonicity, diminishing marginal returns (logarithmic curve), and bounds."""
    # 1. Strict monotonicity within active range [100, 2_500_000]
    vote_samples = [100, 500, 2_000, 15_000, 80_000, 500_000, 1_500_000, 2_500_000]
    scores = [calculateVoteVolume(imdbVotes=v) for v in vote_samples]
    for i in range(len(scores) - 1):
        assert scores[i] < scores[i + 1], f"Expected {scores[i]} < {scores[i+1]} for votes {vote_samples[i]} vs {vote_samples[i+1]}"

    # 2. Diminishing returns (concave logarithmic property)
    # Adding +9,000 votes to an indie film (1k -> 10k) should yield a far bigger boost
    # than adding +9,000 votes to a huge hit (1,000,000 -> 1,009,000)
    delta_indie = calculateVoteVolume(imdbVotes=10_000) - calculateVoteVolume(imdbVotes=1_000)
    delta_hit = calculateVoteVolume(imdbVotes=1_009_000) - calculateVoteVolume(imdbVotes=1_000_000)
    assert delta_indie > delta_hit * 10, "Logarithmic volume should reward early votes significantly more than late votes"

    # 3. Robustness against negative, zero, None, and extreme outliers
    assert calculateVoteVolume(imdbVotes=None) == 0.0
    assert calculateVoteVolume(imdbVotes=0) == 0.0
    assert calculateVoteVolume(imdbVotes=-9999) == 0.0
    assert calculateVoteVolume(imdbVotes=100_000_000) == 1.0


# =====================================================================
# Comprehensive Unit Tests for calculateAwardsBonus
# =====================================================================

@pytest.mark.parametrize(
    "name, awards_summary, expected_bonus",
    [
        ("empty_string", "", 0.0),
        ("no_awards_info", "No major awards won or recorded.", 0.0),
        ("single_oscar_win", "Won 1 Oscar. Another 20 wins.", 0.70),
        ("oscar_win_unspecified_count", "Won Academy Award for Best Director.", 0.70),
        ("palme_dor_win", "Won Palme d'Or at Cannes.", 0.70),
        ("triple_oscar_win", "Won 3 Oscars. Another 45 wins.", 0.80),
        ("record_11_oscars", "Won 11 Academy Awards including Best Picture.", 1.0),
        ("national_film_registry", "Added to the National Film Registry in 2010.", 0.80),
        ("single_oscar_nomination", "Nominated for 1 Oscar. Another 5 wins.", 0.35),
        ("multiple_oscar_nominations", "Nominated for 5 Academy Awards.", 0.55),
        ("capped_oscar_nominations", "Nominated for 14 Oscars.", 0.60),
        ("bafta_win", "Won a BAFTA Film Award.", 0.50),
        ("golden_globe_winner", "Golden Globe Winner for Best Actor.", 0.50),
        ("bafta_nomination", "Nominated for BAFTA Award.", 0.30),
        ("golden_globe_nomination", "Golden Globe nominee for Best Screenplay.", 0.30),
        ("generic_12_wins", "Another 12 wins and 30 nominations.", 0.22),
        ("generic_wins_capped", "Won 80 wins in regional festivals.", 0.25),
    ],
)
def test_awards_bonus_exact_scenarios(name, awards_summary, expected_bonus):
    """Verifies regex extraction, tier hierarchy, and score limits for award summaries."""
    bonus = calculateAwardsBonus(awardsSummary=awards_summary)
    assert bonus == pytest.approx(expected_bonus, abs=1e-3)
    assert 0.0 <= bonus <= 1.0


def test_awards_bonus_hierarchy_and_case_insensitivity():
    """Verifies that top honors dominate and parsing is case-insensitive."""
    # Case insensitivity
    assert calculateAwardsBonus("WON 2 OSCARS") == pytest.approx(0.75, abs=1e-3)

    # Oscar win (0.75) takes precedence over generic festival wins (0.25) or BAFTA noms (0.30)
    complex_summary = "Won 2 Oscars. Nominated for BAFTA. Another 35 wins."
    assert calculateAwardsBonus(complex_summary) == pytest.approx(0.75, abs=1e-3)


# =====================================================================
# Comprehensive Unit Tests for calculateExpectedTime
# =====================================================================

@pytest.mark.parametrize(
    "name, word_count, base_difficulty, expected_seconds",
    [
        ("beginner_baseline", 4, 0.0, 15.0 * 4 * 1.0),       # 60.0s
        ("medium_standard", 6, 0.5, 15.0 * 6 * 1.5),         # 135.0s
        ("hard_large_puzzle", 8, 1.0, 15.0 * 8 * 2.0),       # 240.0s
        ("clamped_zero_words", 0, 0.5, 15.0 * 1 * 1.5),       # Clamped to 1 word -> 22.5s
        ("clamped_negative_words", -5, 0.2, 15.0 * 1 * 1.2),   # Clamped to 1 word -> 18.0s
        ("clamped_subzero_diff", 5, -0.5, 15.0 * 5 * 1.0),    # Diff clamped to 0.0 -> 75.0s
        ("clamped_excess_diff", 5, 2.5, 15.0 * 5 * 2.0),     # Diff clamped to 1.0 -> 150.0s
    ],
)
def test_expected_time_exact_scenarios(name, word_count, base_difficulty, expected_seconds):
    """Verifies formula T_expected = 15s x word_count x (1 + D_base) and boundary clamping."""
    result = calculateExpectedTime(wordCount=word_count, baseDifficulty=base_difficulty)
    assert result == pytest.approx(expected_seconds, abs=1e-4)


# =====================================================================
# Comprehensive Unit Tests for calculatePerformanceRatio
# =====================================================================

def test_performance_ratio_comprehensive():
    """Verifies speed calculation, anti-cheat limits, and friction penalty weights."""
    # 1. Equilibrium (exact time, 0 hints, 0 errors)
    p_eq = calculatePerformanceRatio(timeTakenSeconds=120.0, expectedTimeSeconds=120.0)
    assert p_eq == pytest.approx(1.0, abs=1e-4)

    # 2. Faster than expected (1.5x)
    p_fast = calculatePerformanceRatio(timeTakenSeconds=80.0, expectedTimeSeconds=120.0)
    assert p_fast == pytest.approx(1.5, abs=1e-4)

    # 3. Anti-cheat cap: raw speed of 10x capped to 3.0
    p_superfast = calculatePerformanceRatio(timeTakenSeconds=10.0, expectedTimeSeconds=300.0)
    assert p_superfast == pytest.approx(3.0, abs=1e-4)

    # 4. Anti-cheat minimum time threshold (clamps timeTaken to min 5.0 seconds)
    p_instant = calculatePerformanceRatio(timeTakenSeconds=1.0, expectedTimeSeconds=10.0)
    assert p_instant == pytest.approx(10.0 / 5.0, abs=1e-4)

    # 5. Zero / negative time treated safely via 5.0s floor
    p_zero = calculatePerformanceRatio(timeTakenSeconds=0.0, expectedTimeSeconds=15.0)
    assert p_zero == pytest.approx(3.0, abs=1e-4)

    # 6. Specific friction penalty coefficients
    # Free hints friction (+0.20 per hint)
    p_free_hint = calculatePerformanceRatio(timeTakenSeconds=100.0, expectedTimeSeconds=100.0, freeHints=5)
    # friction = 1.0 + 5 * 0.20 = 2.0 -> penaltyFactor = 0.5
    assert p_free_hint == pytest.approx(0.5, abs=1e-4)

    # Premium hints friction (+1.25 per hint)
    p_prem_hint = calculatePerformanceRatio(timeTakenSeconds=100.0, expectedTimeSeconds=100.0, premiumHints=1)
    # friction = 1.0 + 1.25 = 2.25 -> ratio = 1.0 / 2.25
    assert p_prem_hint == pytest.approx(1.0 / 2.25, abs=1e-4)

    # Errors friction (+0.15 per error)
    p_errors = calculatePerformanceRatio(timeTakenSeconds=100.0, expectedTimeSeconds=100.0, errors=2)
    # friction = 1.0 + 2 * 0.15 = 1.30 -> ratio = 1.0 / 1.30
    assert p_errors == pytest.approx(1.0 / 1.30, abs=1e-4)


# =====================================================================
# Comprehensive Unit Tests for updateUserSkill
# =====================================================================

def test_user_skill_comprehensive():
    """Verifies EMA skill updates, sensitivity scaling, and clamping [0.05, 0.95]."""
    # 1. Exact mathematical update:
    # delta = gamma * (pLevel - 1.0) = 0.08 * (1.5 - 1.0) = 0.04
    # target = 0.50 + 0.04 = 0.54
    # newSkill = 0.80 * 0.50 + 0.20 * 0.54 = 0.40 + 0.108 = 0.508
    s_next = updateUserSkill(currentSkill=0.50, pLevel=1.5, alpha=0.20, gamma=0.08)
    assert s_next == pytest.approx(0.508, abs=1e-3)

    # 2. Hard clamps at boundaries
    assert updateUserSkill(currentSkill=0.95, pLevel=5.0) == 0.95
    assert updateUserSkill(currentSkill=0.05, pLevel=0.0) == 0.05

    # 3. Custom alpha / gamma parameters
    # If alpha = 1.0 (instant adaptation to target)
    s_instant = updateUserSkill(currentSkill=0.50, pLevel=2.0, alpha=1.0, gamma=0.10)
    # delta = 0.10 * 1.0 = 0.10 -> target = 0.60
    assert s_instant == pytest.approx(0.60, abs=1e-3)

    # 4. Multi-round convergence towards ceiling
    skill = 0.50
    for _ in range(50):
        skill = updateUserSkill(currentSkill=skill, pLevel=3.0)
    assert skill == pytest.approx(0.95, abs=1e-2)


# =====================================================================
# Comprehensive Unit Tests for updateTasteVector
# =====================================================================

def test_taste_vector_comprehensive():
    """Verifies vector cold start, centroid blending, inertia, and input formats."""
    # 1. Empty or None input leaves vector untouched
    assert updateTasteVector(currentVector=[0.5, 0.5], solvedMovieVector=None) == [0.5, 0.5]
    assert updateTasteVector(currentVector=[0.5, 0.5], solvedMovieVector=[]) == [0.5, 0.5]

    # 2. Cold start with single 1D vector -> normalized unit vector
    raw_1d = [3.0, 4.0, 0.0]
    cold_1d = updateTasteVector(currentVector=None, solvedMovieVector=raw_1d)
    assert len(cold_1d) == 3
    assert np.isclose(np.linalg.norm(cold_1d), 1.0)
    assert cold_1d[0] == pytest.approx(0.6, abs=1e-4)
    assert cold_1d[1] == pytest.approx(0.8, abs=1e-4)

    # 3. Cold start with list of multiple 1D vectors -> normalized centroid
    m1 = [1.0, 0.0, 0.0]
    m2 = [0.0, 1.0, 0.0]
    cold_multi = updateTasteVector(currentVector=None, solvedMovieVector=[m1, m2])
    # centroid = [0.5, 0.5, 0.0], norm = sqrt(0.5)
    expected_val = 0.5 / np.sqrt(0.5)
    assert cold_multi[0] == pytest.approx(expected_val, abs=1e-4)
    assert cold_multi[1] == pytest.approx(expected_val, abs=1e-4)
    assert np.isclose(np.linalg.norm(cold_multi), 1.0)

    # 4. Full inertia (beta = 1.0) leaves current vector completely unchanged
    curr = [1.0, 0.0, 0.0]
    no_change = updateTasteVector(currentVector=curr, solvedMovieVector=[[0.0, 1.0, 0.0]], beta=1.0)
    assert no_change == [1.0, 0.0, 0.0]

    # 5. Zero inertia (beta = 0.0) adopts new centroid completely
    full_shift = updateTasteVector(currentVector=curr, solvedMovieVector=[[0.0, 1.0, 0.0]], beta=0.0)
    assert full_shift[1] == pytest.approx(1.0, abs=1e-4)


