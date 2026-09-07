import uuid
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, ConfigDict, Field

class GenerateLevelRequest(BaseModel):
    user_id: uuid.UUID
    requested_difficulty: Optional[float] = None
    grid_size: int = 10


class LevelResponse(BaseModel):
    level_id: uuid.UUID
    target_difficulty: float
    grid: List[List[str]]
    placed_words: List[Dict[str, Any]]
    clues: List[Dict[str, Any]]


class HintRequest(BaseModel):
    user_id: uuid.UUID
    level_id: uuid.UUID
    slot_id: str


class HintResponse(BaseModel):
    level_id: uuid.UUID
    slot_id: str
    hint_text: str
    tier: int
    type: str
    cost_charged: int
    free_hints_remaining: int
    premium_hints_remaining: int
    hints_left_for_slot: int


class MovieHintUsage(BaseModel):
    imdb_id: str
    hints_revealed: int = 0
    deepest_tier: int = 0


class SubmitTelemetryRequest(BaseModel):
    user_id: uuid.UUID
    session_id: uuid.UUID
    level_id: uuid.UUID
    imdb_ids: Optional[List[str]] = None
    time_taken_seconds: int = Field(..., ge=1)
    free_hints_used: int = Field(default=0, ge=0)
    premium_hints_used: int = Field(default=0, ge=0)
    cell_error_count: int = Field(default=0, ge=0)
    is_completed: bool = True
    hint_usage: Optional[List[MovieHintUsage]] = None


class TelemetryResponse(BaseModel):
    user_id: uuid.UUID
    session_id: uuid.UUID
    previous_skill_level: float
    new_skill_level: float
    skill_delta: float