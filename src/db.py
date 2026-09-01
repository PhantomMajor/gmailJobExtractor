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


# ---------------------------------------------------------------------------
# Query & Web API Helpers (Added for Web Interface & CLI Integration)
# ---------------------------------------------------------------------------

def get_existing_message_ids() -> set:
    """Get all message IDs already stored in DB for fast in-memory deduplication during extraction."""
    conn = get_connection()
    cursor = conn.execute("SELECT message_id FROM jobs")
    # Return as a set for O(1) membership checks in the extractor
    ids = {row[0] for row in cursor.fetchall()}
    conn.close()
    return ids


def get_jobs(company: Optional[str] = None, interested_only: bool = False) -> List[Dict[str, Any]]:
    """
    Fetch jobs with optional filters for the web interface and API.
    
    Supports case-insensitive partial company search and filtering by interested status.
    Uses parameterized queries to prevent SQL injection.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row  # Access columns by name

    # Base query: 1=1 allows dynamic AND clauses to be appended cleanly
    query = "SELECT id, message_id, sender, date, role, company, location, experience, interested FROM jobs WHERE 1=1"
    params = []

    # Optional filter: partial match on company name (e.g., 'Google' matches 'Google Inc')
    if company:
        query += " AND company LIKE ?"
        params.append(f"%{company}%")

    # Optional filter: only show bookmarked / interested jobs
    if interested_only:
        query += " AND interested = 1"

    # Always show most recently extracted jobs first
    query += " ORDER BY extracted_at DESC"

    cursor = conn.execute(query, params)
    jobs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jobs


def get_stats() -> Dict[str, Any]:
    """
    Compute aggregate summary metrics for the dashboard header.
    
    Returns total jobs count, distinct company count, interested count,
    and the top 5 companies by posting volume.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row

    # Aggregate counts across the entire jobs table
    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    companies = conn.execute("SELECT COUNT(DISTINCT company) FROM jobs").fetchone()[0]
    interested = conn.execute("SELECT COUNT(*) FROM jobs WHERE interested = 1").fetchone()[0]

    # Top 5 companies by number of job postings
    top_companies = conn.execute("""
        SELECT company, COUNT(*) as count
        FROM jobs
        GROUP BY company
        ORDER BY count DESC
        LIMIT 5
    """).fetchall()

    conn.close()

    return {
        "total_jobs": total,
        "unique_companies": companies,
        "interested_count": interested,
        "top_companies": [dict(row) for row in top_companies]
    }


def toggle_interested(job_id: int) -> Optional[int]:
    """
    Cycle through interested states: NULL -> 1 -> 0 -> 1 -> 0 -> ...

    Once a user touches a job (first click from NULL), it never returns to NULL.
    It toggles between 1 (interested) and 0 (not interested).

    Returns:
        1: Job marked interested
        0: Job marked not interested
        None: Job ID not found
    """
    conn = get_connection()

    # Verify job exists before updating
    cursor = conn.execute("SELECT interested FROM jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    # Cycle: NULL -> 1, then toggle between 1 and 0
    current = row[0]
    if current is None:
        new_state = 1  # NULL (untouched) -> 1 (interested)
    elif current == 1:
        new_state = 0  # 1 (interested) -> 0 (not interested)
    else:  # current == 0
        new_state = 1  # 0 (not interested) -> 1 (interested)

    conn.execute(
        "UPDATE jobs SET interested = ? WHERE id = ?",
        (new_state, job_id)
    )
    conn.commit()
    conn.close()

    return new_state