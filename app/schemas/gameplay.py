import uuid
from typing import List,Dict,Any,Optional
from pydantic import BaseModel, ConfigDict

class GenerateLevelRequest(BaseModel):
    user_id: uuid.UUID
    requested_difficulty: Optional[float] = None
    grid_size: int=10


class LevelResponse(BaseModel):
    level_id:uuid.UUID
    topology_id: str
    target_difficulty: float
    grid: List[List[str]]
    placed_words: List[Dict[str,Any]]
    clues: List[Dict[str,Any]]


class SubmitTelemetryRequest(BaseModel):
    user_id: uuid.UUID
    session_id: uuid.UUID
    level_id: uuid.UUID
    imdb_id: Optional[str] = None
    time_taken_seconds: int
    free_hints_used: int = 0
    cell_error_count: int=0
    is_completed: bool= True


class TelemetryResponse(BaseModel):
    user_id: uuid.UUID
    session_id: uuid.UUID
    previous_skill_level: float
    new_skill_level: float
    skill_delta: float
    