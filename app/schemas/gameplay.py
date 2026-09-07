import uuid
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class GenerateLevelRequest(BaseModel):
    user_id: uuid.UUID
    requested_difficulty: Optional[float] = None
    # grid_size is fixed at 10 and not wired through the solver — removed to avoid misleading API contract


class ClueItem(BaseModel):
    slot_id: str
    direction: str
    row: int
    col: int
    length: int
    imdb_id: Optional[str] = None
    display_title: str
    difficulty: Optional[float] = None
    hint: str
    hint_tier: int
    hint_type: str
    hints_available: int
    post_solve_trivia: str



class LevelResponse(BaseModel):
    level_id: uuid.UUID
    target_difficulty: float
    grid: List[List[str]]
    clues: List[ClueItem]


class HintRequest(BaseModel):
    user_id: uuid.UUID
    level_id: uuid.UUID
    slot_id: str = Field(..., max_length=32, pattern=r'^S\d+$')


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
    session_id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4)
    level_id: uuid.UUID
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


class LevelHistoryItem(BaseModel):
    """Schema for a single level entry returned by GET /history/{user_id}."""
    model_config = ConfigDict(extra="ignore")

    level_id: str
    user_id: str
    status: str
    target_difficulty: Optional[float] = None
    movies: List[Dict[str, Any]]
    puzzle_data: Dict[str, Any]
    telemetry: Dict[str, Any]
    time_taken_seconds: Optional[int] = None
    created_at: str
    completed_at: Optional[str] = None