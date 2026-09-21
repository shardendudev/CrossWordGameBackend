import uuid
from typing import Optional
from pydantic import BaseModel,Field, ConfigDict

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=32, pattern=r'^[a-zA-Z0-9_]+$')
    user_id: str = Field(..., min_length=1, max_length=128)
    email: Optional[str] = Field(default=None, max_length=255)

class UserResponse(BaseModel):
    user_id: str
    username: str
    email:Optional[str] = None
    current_skill_level: float
    total_games_played: int
    levels_generated: int = 0
    premium_hints_balance: int

    model_config = ConfigDict(from_attributes=True)

