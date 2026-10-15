
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "users.db"


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                language TEXT NOT NULL,
                location TEXT DEFAULT ''
            )
        """)


def create_user(user_id, name, phone, language, location=""):
    with get_connection() as connection:
        connection.execute("""
            INSERT INTO users (user_id, name, phone, language, location)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, name, phone, language, location))


def get_user(user_id):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()

        return dict(row) if row else None
