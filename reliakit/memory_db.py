# reliakit/memory_db.py
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional

class MemoryDB:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_db()

    def _ensure_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS llm_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    model_used TEXT NOT NULL,
                    prompt TEXT,
                    response TEXT,
                    status TEXT
                )
            ''')

    def insert_log(self, agent_name: str, model_used: str, prompt: str, response: str, status: str = "SUCCESS"):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO llm_log (timestamp, agent_name, model_used, prompt, response, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (datetime.now().isoformat(), agent_name, model_used, prompt, response, status))

    def has_entries(self) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute('SELECT COUNT(*) FROM llm_log')
            return cur.fetchone()[0] > 0

    def get_last_used_model(self) -> Optional[str]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT model_used FROM llm_log ORDER BY timestamp DESC LIMIT 1")
            result = cursor.fetchone()
            return result[0] if result else None

    def get_all_llm_logs(self) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, timestamp, agent_name, model_used, prompt, response, status FROM llm_log ORDER BY timestamp ASC")
            return [dict(row) for row in cursor.fetchall()]

    def get_total_llm_entries(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM llm_log")
            return cursor.fetchone()[0]
