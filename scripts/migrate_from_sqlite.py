import os
import sys
import sqlite3
import asyncio
import re
from pathlib import Path


#add project root directory to sys.path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from app.core.config import settings
from app.db.session import AsyncSessionLocal, init_db
from app.db.models.movie import Movie
from app.engine.difficulty import calculateBaseDifficulty
from app.engine.embeddings import MovieEmbeddingEngine

def cleanTitleForGrid(title:str) -> str:
    title = re.sub(r'[^A-Z0-9]','',str(title).upper())
    return title

def inspectSqliteTable(sqlite_path:str, requested_table:str)-> tuple[str,list[str]]:
    if not os.path.exists(sqlite_path):
        print(f"Warning: SQLite database not found at {sqlite_path}")
        return None,[]
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    cursor.execute(f"SELECT name from sqlite_master WHERE type='table';")
    tables= [t[0] for t in cursor.fetchall()]
    if not tables:
        conn.close()
        return None,[]
    
    table_name = requested_table if requested_table in tables else tables[0]
    cursor.execute(f"PRAGMA table_info('{requested_table}')")
    columns = cursor.fetchall()
    conn.close()

    return table_name, columns


async def stage1_copy_raw_data(sqlite_path:str, target_table:str):
    await init_db()

    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {target_table};")
    async with AsyncSessionLocal() as session:
        migrated_count=0
        for row in cursor:
            row_dict = dict(row)

            #extract id and titles safely
            imdb_id = row_dict.get("imdb_id")
            title = row_dict.get("title")
            clean_title = cleanTitleForGrid(title)


            #Map SQLite dict to PostgreSQL Movie ORM object
            movie = Movie(
                imdb_id = str(imdb_id),
                title = str(title),
                clean_title = clean_title,
                year = int(row_dict.get("year") or 2024),
                genres = row_dict.get("genres"),
                director = row_dict.get("director"),
                actors = row_dict.get("actors"),
                content_rating = row_dict.get("content_rating"),
                poster_url = row_dict.get("poster_url"),
                budget = int(row_dict.get("budget") or 0),
                revenue = int(row_dict.get("revenue") or 0),
                imdb_rating = float(row_dict.get("imdb_rating") or 7.0),
                imdb_votes = int(row_dict.get("imdb_votes") or 10000),

                #Hint fields
                character_hints = row_dict.get("character_hints"),
                plot_hints = row_dict.get("plot_hints"),
                famous_scene_hints = row_dict.get("famous_scene_hints"),
                trivia_hints = row_dict.get("trivia_hints"),
                theme_hints = row_dict.get("theme_hints"),
                famous_props_macguffins = row_dict.get("famous_props_macguffins"),
                cultural_impact_legacy = row_dict.get("cultural_impact_legacy"),
                iconic_dialogue = row_dict.get("iconic_dialogue"),
                awards_summary = row_dict.get("awards_summary"),
                era_buckets = row_dict.get("era_buckets")

            )

            await session.merge(movie)
            migrated_count+=1
        await session.commit()

    conn.close()
    print(f"--> Stage 1 Complete: Successfully copied {migrated_count} movies into PostgreSQL")
    return migrated_count

async def stage_2_calculate_difficulty_and_embeddings():
    print("\n--> Stage 2: Calculating D_base difficulty and generating vector embeddings...")
    embedding_engine = MovieEmbeddingEngine()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Movie))
        movies = result.scalars().all()

        updated_count = 0
        for m in movies:

            #1. Calculate logarithmic base difficulty
            m.base_difficulty = calculateBaseDifficulty(imdbVotes=m.imdb_votes)

            #2. Build dictionary and generate 1024-dim bge-m3 embedding
            movie_dict = {
                "title":m.title,
                "genres":m.genres,
                "character_hints":m.character_hints,
                "plot_hints":m.plot_hints,
                "theme_hints":m.theme_hints,
                "trivia_hints":m.trivia_hints,
                "famous_props_macguffins":m.famous_props_macguffins,
                "cultural_impact_legacy":m.cultural_impact_legacy
            }

            m.semantic_embedding = embedding_engine.generateMovieVector(movie_dict)
            updated_count +=1

        await session.commit()
        print(f"--> Stage 2 Complete: Updated difficulty and embeddings for {updated_count} movies")


async def main():
    print("SQLite to PostgreSQL Movie data migration")

    sqlite_path = settings.SQLITE_DB_PATH
    target_table = settings.SQLITE_TABLE_NAME

    count = await stage1_copy_raw_data(sqlite_path,target_table)
    if count > 0:
        await stage_2_calculate_difficulty_and_embeddings()

        print("\n Migration completed successfully")


if __name__=="__main__":
    asyncio.run(main())