from dataclasses import dataclass
from typing import Final


#1. Era Benchmark ceilings

ERA_CEILINGS:  Final[dict[int,int]] = {
    1980: 150_000_000, 
    2000: 800_000_000,
    9999: 2_500_000_000
}

def get_era_ceiling(year: int) -> int:
    if year < 1980:
        return ERA_CEILINGS[1980]
    
    if year < 2000:
        return ERA_CEILINGS[2000]

    return ERA_CEILINGS[9999]


# difficulty weights and constants
@dataclass(frozen=True)
class DifficultyWeights:
    WEIGHT_VOTES: float = 0.45
    WEIGHT_COMMERCIAL: float = 0.25
    WEIGHT_RATING: float = 0.15
    WEIGHT_AWARDS: float = 0.15
    LOW_CONTEXT_PENALTY: float = 0.15


    #Vote scaling bounds
    MIN_VOTES: int = 100
    MAX_VOTES: int = 2_500_000


    #Expected time baseline
    TIME_PER_WORD_SECONDS: float = 15


difficulty_config = DifficultyWeights()