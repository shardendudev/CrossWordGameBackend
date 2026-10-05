"""
Migration Script: Migrate to V2 Schema (gameplay_levels + user.played_imdb_ids)

Usage:
    ./venv/bin/python scripts/migrate_v2_schema.py

This script:
1. Adds `played_imdb_ids`, `created_at`, `updated_at` to `users` table.
2. Creates `gameplay_levels` table with all indexes (including partial unique index).
3. Backfills `users.played_imdb_ids` from existing `user_movie_telemetry` rows.
4. Keeps existing legacy tables untouched for safe zero-downtime transition.
"""

import sys
from pathlib import Path

# Add project root directory to sys.path so 'app' can be imported directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import logging
from sqlalchemy import text
from app.db.session import engine
from app.db.base import Base
import app.db.models


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migration_v2")


async def run_migration():
    logger.info("Starting V2 database migration...")

    async with engine.begin() as conn:
        # 1. Extensions
        logger.info("Verifying extensions ('vector', 'uuid-ossp')...")
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "vector";'))
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))

        # 2. Additive changes to users table
        logger.info("Applying additive column migrations to 'users' table...")
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS played_imdb_ids VARCHAR(32)[] DEFAULT '{}'::VARCHAR(32)[];"
        ))
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();"
        ))
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();"
        ))

        # 3. Create all tables defined in metadata (includes gameplay_levels and its indexes)
        logger.info("Creating new tables & indexes via SQLAlchemy metadata...")
        await conn.run_sync(Base.metadata.create_all)

        # 4. Explicit index checks for safety
        logger.info("Verifying partial unique index on gameplay_levels...")
        await conn.execute(text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_user_active_level
            ON gameplay_levels (user_id)
            WHERE is_completed = FALSE;
            """
        ))
        await conn.execute(text(
            """
            CREATE INDEX IF NOT EXISTS idx_gameplay_user_history
            ON gameplay_levels (user_id, created_at DESC);
            """
        ))

        # 5. Backfill users.played_imdb_ids from user_movie_telemetry if table exists
        logger.info("Checking for existing user_movie_telemetry to backfill played_imdb_ids...")
        table_check = await conn.execute(text(
            "SELECT to_regclass('public.user_movie_telemetry') IS NOT NULL AS exists;"
        ))
        has_telemetry_table = table_check.scalar()

        if has_telemetry_table:
            logger.info("Backfilling users.played_imdb_ids from user_movie_telemetry...")
            backfill_res = await conn.execute(text(
                """
                UPDATE users u
                SET played_imdb_ids = sub.ids
                FROM (
                    SELECT user_id, array_agg(DISTINCT imdb_id) AS ids
                    FROM user_movie_telemetry
                    GROUP BY user_id
                ) sub
                WHERE u.user_id = sub.user_id
                  AND (u.played_imdb_ids IS NULL OR cardinality(u.played_imdb_ids) = 0);
                """
            ))
            logger.info("Backfill complete. Rows affected: %s", backfill_res.rowcount)
        else:
            logger.info("No legacy user_movie_telemetry table found, skipping backfill.")

    logger.info("✅ V2 Schema migration completed successfully!")


if __name__ == "__main__":
    asyncio.run(run_migration())
