import math
import numpy as np

def calculateBaseDifficulty(imdbVotes: int, minVotes: int = 500, maxVotes: int = 2500000) -> float:
    """
    Calculates movie difficulty score D_base (0.0 to 1.0) based on IMDb votes.
    - Famous movies with 2.5M+ votes -> D_base ~ 0.0 (Easy)
    - Obscure movies with <500 votes -> D_base ~ 1.0 (Hard)
    """
    votesClamped = max(minVotes, min(maxVotes, imdbVotes))
    logVotes = math.log10(votesClamped + 1)
    logMin = math.log10(minVotes + 1)
    logMax = math.log10(maxVotes + 1)
    
    dBase = 1.0 - ((logVotes - logMin) / (logMax - logMin))
    return round(float(np.clip(dBase, 0.0, 1.0)), 3)


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
    """
    Updates player movie taste vector u using weighted running average.
    - Addresses Code Review 3.7: Reduced beta from 0.85 to 0.70 so taste adapts quickly to recent games.
    """
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

