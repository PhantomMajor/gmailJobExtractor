"""
Database operations for job extraction.
Handles SQLite schema initialization and CRUD operations.
"""

import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

DB_FILE = "jobs.db"


def get_connection():
    """Get or create database connection."""
    return sqlite3.connect(DB_FILE)


def init_db():
    """Initialize database schema if not exists."""
    conn = get_connection()
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT NOT NULL,
            sender TEXT NOT NULL,
            date TEXT,

            role TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT,
            experience TEXT,

            interested INTEGER,
            metadata TEXT,

            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(message_id, role, company)
        );

        CREATE INDEX IF NOT EXISTS idx_company ON jobs(company);
        CREATE INDEX IF NOT EXISTS idx_interested ON jobs(interested);
    """)
    conn.commit()
    conn.close()


def upsert_job(record: Dict[str, Any]) -> None:
    """Insert or replace a job record (by message_id, role, company combination)."""
    conn = get_connection()
    conn.execute("PRAGMA foreign_keys = ON")

    conn.execute("""
        INSERT INTO jobs (
            message_id, sender, date, role, company, location, experience, interested, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(message_id, role, company) DO UPDATE SET
            sender = excluded.sender,
            date = excluded.date,
            location = excluded.location,
            experience = excluded.experience,
            updated_at = CURRENT_TIMESTAMP
    """, (
        record.get("message_id"),
        record.get("sender"),
        record.get("date"),
        record.get("role"),
        record.get("company"),
        record.get("location", ""),
        record.get("experience", ""),
        None,  # interested defaults to NULL (not reviewed)
        None,  # metadata (can be populated later)
    ))

    conn.commit()
    conn.close()


def load_jobs_for_export() -> List[Dict[str, Any]]:
    """Fetch all jobs as list of dicts (for JSON export or display)."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row

    cursor = conn.execute("""
        SELECT message_id, sender, date, role, company, location, experience, interested
        FROM jobs
        ORDER BY extracted_at DESC
    """)

    jobs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jobs


def export_to_json(output_file: str) -> None:
    """Export all jobs to JSON file."""
    jobs = load_jobs_for_export()
    Path(output_file).write_text(
        json.dumps(jobs, indent=2, ensure_ascii=False)
    )


def get_existing_message_ids() -> set:
    """Get all message IDs already in DB (for dedup)."""
    conn = get_connection()
    cursor = conn.execute("SELECT message_id FROM jobs")
    ids = {row[0] for row in cursor.fetchall()}
    conn.close()
    return ids