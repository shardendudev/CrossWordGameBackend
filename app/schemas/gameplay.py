import uuid
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class GenerateLevelRequest(BaseModel):
    user_id: uuid.UUID
    requested_difficulty: Optional[float] = None
    exclude_imdb_ids: Optional[List[str]] = Field(default=None, max_length=500, description="Optional list of played IMDb IDs from client Dexie store to exclude from candidate selection")



class ClueItem(BaseModel):
    slot_id: str
    number: Optional[int] = None
    direction: str
    row: int
    col: int
    length: int
    word_lengths: Optional[List[int]] = Field(default=None, description="Lengths of individual words in movie title, e.g. [3, 6]")
    word_pattern: Optional[str] = Field(default=None, description="Formatted word lengths pattern, e.g. '(3,6)'")
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
    level_number: int
    target_difficulty: float
    free_hints_remaining: int = 2
    premium_hints_remaining: int = 5
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
    level_number: Optional[int] = Field(default=None, description="Sequential level number assigned at generation")
    imdb_ids: Optional[List[str]] = Field(default=None, description="Optional list of movie IMDb IDs in the level")
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
    level_number: Optional[int] = 1
    user_id: str
    status: str
    target_difficulty: Optional[float] = None
    movies: List[Dict[str, Any]]
    puzzle_data: Dict[str, Any]
    telemetry: Dict[str, Any]
    time_taken_seconds: Optional[int] = None
    created_at: str
    completed_at: Optional[str] = None