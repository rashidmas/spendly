import sqlite3
from pathlib import Path

from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database" / "spendly.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT,
                expense_date TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def seed_db():
    init_db()
    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            ("nitish@example.com",),
        ).fetchone()

        if user is None:
            conn.execute(
                """
                INSERT INTO users (name, email, password)
                VALUES (?, ?, ?)
                """,
                (
                    "Nitish Kumar",
                    "nitish@example.com",
                    generate_password_hash("demo1234"),
                ),
            )
            user_id = conn.execute(
                "SELECT id FROM users WHERE email = ?",
                ("nitish@example.com",),
            ).fetchone()["id"]

            sample_expenses = [
                (user_id, "Groceries", "Food", 420.0, "Weekly supermarket run", "2026-03-05"),
                (user_id, "Rent", "Bills", 18000.0, "Monthly apartment rent", "2026-03-01"),
                (user_id, "Bus Pass", "Transport", 600.0, "Monthly travel pass", "2026-03-10"),
            ]
            conn.executemany(
                """
                INSERT INTO expenses (user_id, title, category, amount, description, expense_date)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                sample_expenses,
            )

        conn.commit()
    finally:
        conn.close()
