import aiosqlite
import json
import datetime
from pathlib import Path
from typing import Optional,List,Dict,Any,Set

class HistoryStore:
    def __init__(self, db_path: str  = "data/history.db"):
        self.db_path = db_path
        #convert string to a path object 
        path_obj = Path(self.db_path)

        #automatically create the parent directory ('data/') if it doesn't exist
        path_obj.parent.mkdir(parents=True, exist_ok=True)

    async def init_db(self):
        SCHEMA = """
        CREATE TABLE IF NOT EXISTS user_profiles(
        user_id TEXT PRIMARY KEY,
        played_movie_ids TEXT DEFAULT '[]',
        stats TEXT DEFAULT '{}',
        last_active_at TEXT);
        
        CREATE TABLE IF NOT EXISTS user_levels(
        level_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        status TEXT DEFAULT 'in_progress',
        target_difficulty REAL,
        movies TEXT NOT NULL,
        puzzle_data TEXT NOT NULL,
        telemetry TEXT DEFAULT '{}',
        time_taken_seconds INTEGER,
        created_at TEXT NOT NULL,
        completed_at TEXT);


        CREATE INDEX IF NOT EXISTS idx_user_levels_user_id ON user_levels(user_id);
        """

        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(SCHEMA)
            await db.commit()
    
    async def get_played_movie_ids(self, user_id: str) -> set[str]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT played_movie_ids FROM user_profiles WHERE user_id=?",(user_id,)) as cursor:
                row = await cursor.fetchone()
                if row and row["played_movie_ids"]:
                    return set(json.loads(row["played_movie_ids"]))
                return set()

    async def get_user_history(self, user_id:str, limit:int=20, offset: int=0) -> List[Dict[str,Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            query = """SELECT level_id, user_id, status, target_difficulty, movies, puzzle_data, telemetry, time_taken_seconds, created_at, completed_at FROM user_levels WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ? """

            async with db.execute(query, (user_id, limit, offset)) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        "level_id": row["level_id"],
                        "user_id": row["user_id"],
                        "status": row["status"],
                        "target_difficulty": row["target_difficulty"],
                        "movies": json.loads(row["movies"]),
                        "puzzle_data": json.loads(row["puzzle_data"]),
                        "telemetry": json.loads(row["telemetry"]),
                        "time_taken_seconds": row["time_taken_seconds"],
                        "created_at": row["created_at"],
                        "completed_at": row["completed_at"]
                    }
                    for row in rows
                ]

    async def save_generated_level(self,user_id:str, level_id: str, target_difficulty: float, movies: List[Dict[str,Any]], puzzle_data: Dict[str,Any]):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        new_imdb_ids = [m.get("imdb_id") for m in movies if m.get("imdb_id")]

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("""INSERT INTO user_levels (
                level_id, user_id, status, target_difficulty, movies, puzzle_data, created_at
            ) VALUES (?,?,'in_progress',?,?,?,?)""",(
                level_id,
                user_id,
                target_difficulty,
                json.dumps(movies),
                json.dumps(puzzle_data),
                now
            ))
        
            async with db.execute("SELECT played_movie_ids FROM user_profiles WHERE user_id=?",(user_id,)) as cursor:
                row = await cursor.fetchone()
            current_ids = json.loads(row["played_movie_ids"]) if (row and row["played_movie_ids"]) else []
            updated_ids = list(set(current_ids).union(new_imdb_ids))

            await db.execute("""
                INSERT INTO user_profiles (user_id, played_movie_ids, last_active_at)
                VALUES (?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET
                played_movie_ids = excluded.played_movie_ids,
                last_active_at = excluded.last_active_at            
            """,(user_id,json.dumps(updated_ids),now))

            await db.commit()


    async def record_level_completion(self,user_id: str,level_id: str,time_taken_seconds: int,telemetry: Optional[Dict[str,Any]] = None):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        telemetry_json = json.dumps(telemetry or {})

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
            UPDATE user_levels
            SET status = 'completed',
            time_taken_seconds = ?,
            telemetry = ?,
            completed_at = ?
            WHERE level_id = ? AND user_id = ?
            """,(time_taken_seconds, telemetry_json, now, level_id, user_id))

            await db.execute(""" 
            UPDATE user_profiles
            SET last_active_at = ?
            WHERE user_id = ?
            """,(now,user_id))

            await db.commit()

    async def get_level(self, level_id: str) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM user_levels WHERE level_id = ?", (level_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "level_id": row["level_id"],
                        "user_id": row["user_id"],
                        "status": row["status"],
                        "target_difficulty": row["target_difficulty"],
                        "movies": json.loads(row["movies"]),
                        "puzzle_data": json.loads(row["puzzle_data"]),
                        "telemetry": json.loads(row["telemetry"]),
                        "time_taken_seconds": row["time_taken_seconds"],
                        "created_at": row["created_at"],
                        "completed_at": row["completed_at"]
                    }
                return None


history_store = HistoryStore()

