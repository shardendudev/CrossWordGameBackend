import math
import re
import numpy as np

def calculateBaseDifficulty(
    imdbVotes: int = 0,
    imdbRating: float = 0.0,
    budget: int = 0,
    revenue: int = 0,
    awardsSummary: str = "",
    lowContext: bool = False,
    minVotes: int = 100,
    maxVotes: int = 2500000,
) -> float:
    """
    Multi-attribute Movie Difficulty & Popularity Engine:
    D_base = 1.0 - min(1.0, [w_v * V_norm + w_r * R_norm + w_b * B_norm + w_a * A_bonus - P_context])
    """
    # 1. Logarithmic Vote Volume (V_norm)
    v_clamped = max(minVotes, min(maxVotes, imdbVotes or 0))
    v_norm = (math.log10(v_clamped + 1) - math.log10(minVotes + 1)) / (
        math.log10(maxVotes + 1) - math.log10(minVotes + 1)
    )

    # 2. Box Office Commercial Impact (B_norm)
    commercial = max(revenue or 0, budget or 0)
    b_norm = math.log10(commercial + 1) / math.log10(3_000_000_000 + 1)

    # 3. Critical Acclaim (R_norm)
    r_norm = min(1.0, max(0.0, (imdbRating or 0.0) / 10.0))

    # 4. Awards & Cultural Legacy Bonus (A_bonus)
    a_bonus = 0.00
    if awardsSummary:
        text_lower = awardsSummary.lower()
        top_win_patterns = [
            r"won\s+.*?(?:academy\s+award|oscar|palme\s+d'or)",
            r"(?:academy\s+award|oscar|palme\s+d'or)\s+winner",
        ]
        nomination_patterns = [r"nominat", r"golden\s+globe", r"bafta"]
        if any(re.search(p, text_lower) for p in top_win_patterns):
            a_bonus = 0.10
        elif any(re.search(p, text_lower) for p in nomination_patterns):
            a_bonus = 0.05

    # 5. Low Context Penalty (P_context)
    p_context = 0.15 if lowContext else 0.00

    # Parameter Weights
    w_v = 0.50
    w_b = 0.25
    w_r = 0.15
    w_a = 0.10

    raw_pop = (w_v * v_norm) + (w_r * r_norm) + (w_b * b_norm) + (w_a * a_bonus) - p_context
    popularity = max(0.0, min(1.0, raw_pop))
    d_base = 1.0 - popularity

    return round(float(np.clip(d_base, 0.0, 1.0)), 3)


def calculateExpectedTime(wordCount: int, baseDifficulty: float) -> float:
    """
    Expected completion baseline in seconds:
    T_expected = 15s x word_count x (1+D_base)
    """
    safe_word_count = max(1,wordCount)
    safe_difficulty = max(0.0, min(1.0, baseDifficulty))
    return float(15.0 * safe_word_count * (1.0 + safe_difficulty))


def calculatePerformanceRatio(
    timeTakenSeconds: float,
    expectedTimeSeconds: float = 360.0,
    freeHints: int = 0,
    premiumHints: int = 0,
    errors: int = 0,
    avgHintDepth: float = 0.0
) -> float:
    """
    Evaluates player solve performance P_level.
    - P_level > 1.0: Player solved quickly with few hints.
    - P_level < 1.0: Player took long or used many hints.
    """
    tActual = max(timeTakenSeconds, 10.0)
    # Clamp timeFactor between 0.2x and 2.5x to prevent extreme spikes while staying responsive
    rawTimeFactor = expectedTimeSeconds / tActual
    timeFactor = min(2.5, max(0.2, rawTimeFactor))

    penaltyFactor = 1.0 / (1.0 + (0.25 * freeHints) + (1.20 * premiumHints) + (0.15 * errors))
    depthPenalty = 1.0 - (0.3 * min(1.0, max(0.0, avgHintDepth)))
    
    return float(timeFactor * penaltyFactor * depthPenalty)


def updateUserSkill(
    currentSkill: float,
    pLevel: float,
    alpha: float = 0.3,
    gamma: float = 0.25
) -> float:
    """
    Updates player skill rating S_user using Exponential Moving Average (EMA).
    - Addresses Code Review 3.2: Increased gamma (0.25) & alpha (0.3) for responsive skill progression.
    - Bounded between 0.05 (Beginner) and 0.95 (Expert).
    """
    delta = gamma * (pLevel - 1.0)
    targetSkill = max(0.05, min(0.95, currentSkill + delta))
    newSkill = (1.0 - alpha) * currentSkill + alpha * targetSkill
    return round(float(newSkill), 3)


def updateTasteVector(
    currentVector: list[float] | None,
    solvedMovieVector: list[float] | None,
    beta: float = 0.60
) -> list[float] | None:
    
    if solvedMovieVector is None:
        return currentVector
    
    vSolved = np.array(solvedMovieVector, dtype=np.float32)
    normSolved = np.linalg.norm(vSolved)
    if normSolved > 0:
        vSolved = vSolved / normSolved  # Pre-normalize solved vector
    
    if currentVector is None:
        return vSolved.tolist()
    
    uCurr = np.array(currentVector, dtype=np.float32)
    updated = beta * uCurr + (1.0 - beta) * vSolved
    normUpdated = np.linalg.norm(updated)
    if normUpdated > 0:
        updated = updated / normUpdated
    return updated.tolist()

