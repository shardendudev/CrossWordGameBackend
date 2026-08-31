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
    expectedTimeSeconds: float = 60.0,
    freeHints: int = 0,
    premiumHints: int = 0,
    errors: int = 0
) -> float:
    """
    Evaluates player solve performance P_level.
    - P_level > 1.0: Player solved quickly with few hints.
    - P_level < 1.0: Player took long or used many hints.
    """
    tActual = max(timeTakenSeconds, 5.0)
    timeFactor = expectedTimeSeconds / tActual
    penaltyFactor = 1.0 / (1.0 + (0.25 * freeHints) + (1.20 * premiumHints) + (0.15 * errors))
    
    return float(timeFactor * penaltyFactor)


def updateUserSkill(
    currentSkill: float,
    pLevel: float,
    alpha: float = 0.2,
    gamma: float = 0.1
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
    """
    Updates player movie taste vector u using weighted running average.
    """
    if solvedMovieVector is None:
        return currentVector
    
    vSolved = np.array(solvedMovieVector, dtype=np.float32)
    if currentVector is None:
        norm = np.linalg.norm(vSolved)
        return (vSolved / norm).tolist() if norm > 0 else vSolved.tolist()
    
    uCurr = np.array(currentVector, dtype=np.float32)
    updated = beta * uCurr + (1.0 - beta) * vSolved
    norm = np.linalg.norm(updated)
    if norm > 0:
        updated = updated / norm
    return updated.tolist()
