import urllib.parse
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "movie_crossword_db"

    EMBEDDING_MODEL_NAME: str = "BAAI/bge-m3"
    ALLOWED_ORIGINS: str = "*"


    @property
    def ASYNC_DATABASE_URL(self) -> str:
        # URL-encode the password to safely handle special characters like @, #, ?, etc.
        safe_password = urllib.parse.quote_plus(self.POSTGRES_PASSWORD)
        if self.POSTGRES_SERVER.startswith("/cloudsql/"):
            return f'postgresql+asyncpg://{self.POSTGRES_USER}:{safe_password}@/{self.POSTGRES_DB}?host={self.POSTGRES_SERVER}'
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{safe_password}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=True
    )

settings = Settings()
