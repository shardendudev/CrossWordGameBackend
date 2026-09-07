import uuid
from pydantic import BaseModel,Field, ConfigDict

class UserCreate(BaseModel):
    username:str = Field(...,min_length=3,max_length=32,pattern=r'[a-zA-Z0-9_]+$')

class UserResponse(BaseModel):
    user_id: uuid.UUID
    username: str
    current_skill_level: float
    total_games_played: int
    premium_hints_balance: int

    model_config = ConfigDict(from_attributes=True)

