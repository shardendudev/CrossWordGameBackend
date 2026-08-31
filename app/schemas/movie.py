from typing import Optional
from pydantic import BaseModel, ConfigDict

class MovieResponse(BaseModel):
    imdb_id:str
    title:str
    clean_title:str
    year:int
    genres:Optional[str] = None
    director: Optional[str] = None
    actors: Optional[str] = None
    content_rating: Optional[str] = None
    poster_url: Optional[str] = None
    imdb_rating: Optional[float] = None


    #Hint fields for gameplay clues 
    character_hints:Optional[str] = None
    plot_hints: Optional[str] = None
    trivia_hints: Optional[str] = None
    theme_hints: Optional[str] = None
    famous_props_macguffins: Optional[str] = None
    cultural_impact_legacy: Optional[str] = None
    iconic_dialogue: Optional[str] = None


    #convert SQLAlchemy ORM objects directly into Pydantic models
    model_config = ConfigDict(from_attributes=True)
    
