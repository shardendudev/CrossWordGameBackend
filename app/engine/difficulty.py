import math
import re
import numpy as np

def calculateBaseDifficulty(
    imdbVotes: int = 0,
    imdbRating: float = 0.0,
    budget: int = 0,
    revenue: int = 0,
    year: int = 2000,
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
    rev = revenue or 0
    bud = budget or 0
    commercial = rev if rev > 0 else bud

    #select era ceiling by release year
    if year < 1980:
        era_ceiling = 150000000
    elif year < 2000:
        era_ceiling = 800000000
    else:
        era_ceiling = 2500000000

    b_era = math.log10(commercial + 1)/math.log10(era_ceiling + 1)

    profit_multiplier = 1.0
    if rev > 0 and bud > 0:
        ratio = rev/bud

        #Bounded between 0.85 (-15% flop discount) and 1.15 (+15% hit reward)
        profit_multiplier = max(0.85,min(1.15, 1.0 + 0.15 * math.log10(ratio)))

    b_norm = min(1.0, max(0.0, b_era * profit_multiplier))

    # 3. Critical Acclaim (R_norm)
    r_norm = min(1.0, max(0.0, (imdbRating or 0.0) / 10.0))

    # 4. Awards & Cultural Legacy Bonus (A_bonus)
    a_bonus = 0.00
    if awardsSummary:

        text_lower = awardsSummary.lower()
        #check for oscar/academy award wins with count
        oscar_win = re.search(r"won\s+(\d+)?\s*(?:academy\s+award|oscar|palme\s+d'or)", text_lower)
        
        if oscar_win:
            count = int(oscar_win.group(1)) if oscar_win.group(1) else 1
            a_bonus = min(1.0,0.70 + (count - 1) * 0.05)

        elif "national film registry" in text_lower:
            a_bonus = 0.80

        #e.g. "Nominated for 3 academy awards"
        oscar_nom = re.search(r"nominat\w*\s+(?:for\s+)?(\d+)?\s*(?:academy\s+award|oscar)", text_lower)
        
        if oscar_nom:
            count = int(oscar_nom.group(1)) if oscar_nom.group(1) else 1
            a_bonus = max(a_bonus,min(0.60, 0.35 + (count - 1) * 0.05))

        # BAFTA / Golden Globe wins
        if any(kw in text_lower for kw in ["won a bafta", "won bafta", "golden globe winner","won golden globe"]):
            a_bonus = max(a_bonus, 0.50)
        
        elif any(kw in text_lower for kw in ["bafta", "golden globe"]):
            a_bonus = max(a_bonus, 0.30)

        
        #e.g "Received 5 wins and 10 nominations" or "Another 12 wins"

        generic_wins = re.search(r"(\d+)\s+win", text_lower)

        if generic_wins:
            w_count = int(generic_wins.group(1))

            a_bonus = max(a_bonus, min(0.25,0.10 + w_count * 0.01))


        """top_win_patterns = [
            r"won\s+.*?(?:academy\s+award|oscar|palme\s+d'or)",
            r"(?:academy\s+award|oscar|palme\s+d'or)\s+winner",
        ]
        nomination_patterns = [r"nominat", r"golden\s+globe", r"bafta"]
        if any(re.search(p, text_lower) for p in top_win_patterns):
            a_bonus = 1.0
        elif any(re.search(p, text_lower) for p in nomination_patterns):
            a_bonus = 0.5 """

    # 5. Low Context Penalty (P_context)
    p_context = 0.15 if lowContext else 0.00

    # Parameter Weights
    w_v = 0.45
    w_b = 0.25
    w_r = 0.15
    w_a = 0.15

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
    tActual = max(float(timeTakenSeconds), 5.0)
    timeFactor = expectedTimeSeconds / tActual
 

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

