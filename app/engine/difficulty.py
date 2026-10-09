from fastapi import param_functions
import math
import re
import numpy as np
from app.engine.config import get_era_ceiling, difficulty_config


def calculateCommercialImpact(
    revenue: int = 0,
    budget: int = 0,
    year: int = 2000, 
) -> float | dict:
    """
    Evaluates era-adjusted commercial impact B_norm on a scale of [0.0, 1.0].
    """


    rev = max(0, revenue or 0)
    bud = max(0, budget or 0)
    commercial = rev if rev > 0 else bud

    era_ceiling = get_era_ceiling(year)


    b_era = min(1.0, commercial / era_ceiling)

    p_term = 0.5 #baseline for missing budget and revenue data

    if rev > 0 and bud > 0:
        raw_roi = rev / bud
        p_term = min(1.0, raw_roi / 5.0)

    
    b_norm = 0.65 * b_era + 0.35 * p_term

    return b_norm

    


    """
  this is older version kept just for reference
    b_era = math.log10(commercial + 1) / math.log10(era_ceiling + 1)

    profit_multiplier = 1.0
    profit_ratio = None
    if rev > 0 and bud > 0:
        profit_ratio = rev / bud
        profit_multiplier = max(0.85, min(1.15, 1.0 + 0.15 * math.log10(profit_ratio)))

    b_norm = min(1.0, max(0.0, b_era * profit_multiplier))

    if returnDetails:
        return{
            "b_norm": round(float(b_norm), 3),
            "b_era": round(float(b_era), 3),
            "commercial": commercial,
            "era_ceiling": era_ceiling,
            "profit_ratio": round(float(profit_ratio), 2) if profit_ratio else None,
            "profit_multiplier": round(float(profit_multiplier), 3),
        }
        
    return round(float(b_norm), 3)
    """


def calculateVoteVolume(
    imdbVotes: int = 0,
    minVotes: int = difficulty_config.MIN_VOTES,
    maxVotes: int = difficulty_config.MAX_VOTES,
) -> float:
    """
    Evaluates logarithmic vote volume V_norm on a scale of [0.0, 1.0]:
    V_norm = (log10(v_clamped + 1) - log10(minVotes + 1)) / (
        log10(maxVotes + 1) - log10(minVotes + 1)
    )
    Clamps imdbVotes to [minVotes, maxVotes] to ensure boundedness in [0.0, 1.0].
    """
    v_clamped = max(minVotes, min(maxVotes, imdbVotes or 0))
    v_norm = (math.log10(v_clamped + 1) - math.log10(minVotes + 1)) / (
        math.log10(maxVotes + 1) - math.log10(minVotes + 1)
    )
    return float(v_norm)


def calculateAwardsBonus(awardsSummary: str = "") -> float:
    """
    Evaluates awards & cultural legacy bonus A_bonus on a scale of [0.0, 1.0].
    Prioritizes Oscar/Palme d'Or wins, National Film Registry, then nominations,
    BAFTA/Golden Globe, and generic festival wins.
    """
    if not awardsSummary:
        return 0.0

    a_bonus = 0.00
    text_lower = awardsSummary.lower()

    # Oscar / Academy Award / Palme d'Or wins with count
    oscar_win = re.search(r"won\s+(\d+)?\s*(?:academy\s+award|oscar|palme\s+d'or)", text_lower)
    if oscar_win:
        count = int(oscar_win.group(1)) if oscar_win.group(1) else 1
        a_bonus = min(1.0, 0.70 + (count - 1) * 0.05)
    elif "national film registry" in text_lower:
        a_bonus = 0.80

    # Oscar nominations
    oscar_nom = re.search(r"nominat\w*\s+(?:for\s+)?(\d+)?\s*(?:academy\s+award|oscar)", text_lower)
    if oscar_nom:
        count = int(oscar_nom.group(1)) if oscar_nom.group(1) else 1
        a_bonus = max(a_bonus, min(0.60, 0.35 + (count - 1) * 0.05))

    # BAFTA / Golden Globe wins
    if any(kw in text_lower for kw in ["won a bafta", "won bafta", "golden globe winner", "won golden globe"]):
        a_bonus = max(a_bonus, 0.50)
    elif any(kw in text_lower for kw in ["bafta", "golden globe"]):
        a_bonus = max(a_bonus, 0.30)

    # Generic festival wins
    generic_wins = re.search(r"(\d+)\s+win", text_lower)
    if generic_wins:
        w_count = int(generic_wins.group(1))
        a_bonus = max(a_bonus, min(0.25, 0.10 + w_count * 0.01))

    return round(float(a_bonus), 3)


def calculateBaseDifficulty(
    imdbVotes: int = 0,
    imdbRating: float = 0.0,
    budget: int = 0,
    revenue: int = 0,
    year: int = 2000,
    awardsSummary: str = "",
    lowContext: bool = False,
    minVotes: int = difficulty_config.MIN_VOTES,
    maxVotes: int = difficulty_config.MAX_VOTES,
) -> float:
    """
    Multi-attribute Movie Difficulty & Popularity Engine:
    D_base = 1.0 - min(1.0, [w_v * V_norm + w_r * R_norm + w_b * B_norm + w_a * A_bonus - P_context])
    """
    # 1. Logarithmic Vote Volume (V_norm)
    v_norm = calculateVoteVolume(imdbVotes=imdbVotes, minVotes=minVotes, maxVotes=maxVotes)

    # 2. Box office commercial impact (B_norm)
    b_norm = calculateCommercialImpact(revenue=revenue, budget=budget, year=year)

    # 3. Critical Acclaim (R_norm)
    r_norm = min(1.0, max(0.0, (imdbRating or 0.0) / 10.0))

    # 4. Awards & Cultural Legacy Bonus (A_bonus)
    a_bonus = calculateAwardsBonus(awardsSummary=awardsSummary)

    # 5. Low Context Penalty (P_context)
    p_context = difficulty_config.LOW_CONTEXT_PENALTY if lowContext else 0.00

    # Parameter Weights
    w_v = difficulty_config.WEIGHT_VOTES
    w_b = difficulty_config.WEIGHT_COMMERCIAL
    w_r = difficulty_config.WEIGHT_RATING
    w_a = difficulty_config.WEIGHT_AWARDS

    raw_pop = (w_v * v_norm) + (w_r * r_norm) + (w_b * b_norm) + (w_a * a_bonus) - p_context
    popularity = max(0.0, min(1.0, raw_pop))
    d_base = 1.0 - popularity

    return round(float(np.clip(d_base, 0.0, 1.0)), 3)


def calculateExpectedTime(wordCount: int, baseDifficulty: float) -> float:
    """
    Expected completion baseline in seconds:
    T_expected = 15s x word_count x (1+D_base)
    """
    safe_word_count = max(1, wordCount)
    safe_difficulty = max(0.0, min(1.0, baseDifficulty))
    return float(difficulty_config.TIME_PER_WORD_SECONDS * safe_word_count * (1.0 + safe_difficulty))


def calculatePerformanceRatio(
    timeTakenSeconds: float,
    wordCount: int = 6,
    baseDifficulty: float = 0.5,
    expectedTimeSeconds: float | None = None,
    freeHints: int = 0,
    premiumHints: int = 0,
    errors: int = 0
) -> float:
    """
    Evaluates player solve performance P_level.
    - P_level > 1.0: Player solved quickly with few hints.
    - P_level < 1.0: Player took long or used many hints.
    """
    if expectedTimeSeconds is None:
        expectedTimeSeconds = calculateExpectedTime(wordCount=wordCount, baseDifficulty=baseDifficulty)

    tActual = max(float(timeTakenSeconds), 5.0)
    rawTimeFactor = expectedTimeSeconds / tActual

    timeFactor = min(3.0,rawTimeFactor)


    friction = 1.0 + (0.20 * freeHints) + (1.25 * premiumHints) + (0.15 * errors)
    penaltyFactor = 1.0 / friction
    
    return float(timeFactor * penaltyFactor)


def updateUserSkill(
    currentSkill: float,
    pLevel: float,
    alpha: float = 0.20,  #learning rate
    gamma: float = 0.08 #adaptation sensitivity 
) -> float:
    """
    Updates player skill rating S_user using Exponential Moving Average (EMA).
    - Bounded between 0.05 (Beginner) and 0.95 (Expert).
    """
    delta = gamma * (pLevel - 1.0)
    targetSkill = max(0.05, min(0.95, currentSkill + delta))
    newSkill = (1.0 - alpha) * currentSkill + alpha * targetSkill
    return round(float(newSkill), 3)


def updateTasteVector(
    currentVector: list[float] | None,
    solvedMovieVector: list[float] | None,
    beta: float = 0.85
) -> list[float] | None:
    
    if not solvedMovieVector:
        return currentVector

    #convert to 2D numpy array of shape (num_movies, 1024)
    if isinstance(solvedMovieVector[0],(int,float)):
        #single 1d vector was passed
        movie_arrays = [np.array(solvedMovieVector, dtype=np.float32)]

    else:
        #List of 1D vectors
        movie_arrays = [np.array(v, dtype=np.float32) for v in solvedMovieVector if v is not None]

    if not movie_arrays:
        return currentVector

    
    #compute the mean across all movies in the level
    centroid = np.mean(movie_arrays, axis=0)

    #cold start case
    if currentVector is None:
        norm = np.linalg.norm(centroid)
        return (centroid / norm).tolist() if norm > 0 else centroid.tolist()


    #EMA blended taste vector update
    uCurr = np.array(currentVector, dtype=np.float32)
    updated = beta * uCurr + (1.0 - beta) * centroid
    normUpdated = np.linalg.norm(updated)
    if normUpdated > 0:
        updated = updated / normUpdated
    return updated.tolist()



