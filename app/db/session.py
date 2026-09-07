from typing import AsyncGenerator
from sqlalchemy import text 
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker 
from app.core.config import settings 
from app.db.base import Base

#1. Async engine 
engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True
)

#2. Session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

#3. Dependency generator for FastAPI routes
async def get_db() -> AsyncGenerator[AsyncSession,None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

#4. Table and pgvector initialiser
async def init_db():
    import app.db.models
    async with engine.begin() as conn:
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "vector";'))
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
        # Safe migration: add created_at to hint cache for existing tables
        await conn.execute(text('ALTER TABLE level_hint_cache ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();'))
        await conn.run_sync(Base.metadata.create_all)