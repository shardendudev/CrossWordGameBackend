import uuid
from pydantic import BaseModel, ConfigDict

class UserCreate(BaseModel):
    username:str

class UserResponse(BaseModel):
    user_id: uuid.UUID
    username: str
    current_skill_level: float
    total_games_played: int
    premium_hints_balance: int

    model_config = ConfigDict(from_attributes=True)

