"""
Database operations for job extraction and web queries.
Backend: local SQLite or Turso cloud (configured via DB_TYPE env var).

Configuration:
  DB_TYPE=sqlite (default): Use local SQLite database (jobs.db)
  DB_TYPE=turso: Use Turso cloud database (requires TURSO_DATABASE_URL and TURSO_AUTH_TOKEN)
"""

import sqlite3
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

DB_FILE = "jobs.db"

# Configuration
DB_TYPE = os.getenv("DB_TYPE", "sqlite").lower()
if DB_TYPE not in ("sqlite", "turso"):
    raise ValueError(f"Invalid DB_TYPE: {DB_TYPE}. Use 'sqlite' or 'turso'")

if DB_TYPE == "turso":
    url = os.getenv("TURSO_DATABASE_URL")
    token = os.getenv("TURSO_AUTH_TOKEN")
    if not url or not token:
        raise ValueError("DB_TYPE=turso requires TURSO_DATABASE_URL and TURSO_AUTH_TOKEN env vars")

# Lazy imports for optional Turso support
_turso_client = None

def _get_turso_client():
    """Lazily initialize and cache Turso client."""
    global _turso_client
    if _turso_client is None:
        from libsql_client import create_client_sync  # pyrefly: ignore [missing-import]
        url = os.getenv("TURSO_DATABASE_URL")
        token = os.getenv("TURSO_AUTH_TOKEN")
        if not url or not token:
            raise ValueError("TURSO_DATABASE_URL and TURSO_AUTH_TOKEN must be set")
        # Use HTTP-based Hrana instead of WebSocket: some libsql-client
        # versions fail the WS handshake (400 Invalid response status)
        # against Turso's current server protocol version.
        http_url = url.replace("libsql://", "https://")
        _turso_client = create_client_sync(url=http_url, auth_token=token)
    return _turso_client


def get_connection():
    """Get or create database connection."""
    return sqlite3.connect(DB_FILE)


def init_db():
    """Initialize database schema if not exists."""
    if DB_TYPE == "turso":
        client = _get_turso_client()
        client.batch([
            """
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
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_company ON jobs(company)",
            "CREATE INDEX IF NOT EXISTS idx_interested ON jobs(interested)",
        ])
    else:
        # Local SQLite
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


def job_exists(role: str, company: str, location: str = "") -> bool:
    """Check if a job with identical role, company, and location already exists."""
    if DB_TYPE == "turso":
        client = _get_turso_client()
        result = client.execute(
            "SELECT 1 FROM jobs WHERE role = ? AND company = ? AND location = ?",
            [role, company, location]
        )
        return len(result.rows) > 0
    else:
        conn = get_connection()
        cursor = conn.execute(
            "SELECT 1 FROM jobs WHERE role = ? AND company = ? AND location = ?",
            (role, company, location)
        )
        exists = cursor.fetchone() is not None
        conn.close()
        return exists


def update_job_timestamp(role: str, company: str, location: str = "") -> None:
    """Update the updated_at timestamp for a job without changing other fields."""
    if DB_TYPE == "turso":
        client = _get_turso_client()
        client.execute(
            "UPDATE jobs SET updated_at = CURRENT_TIMESTAMP WHERE role = ? AND company = ? AND location = ?",
            [role, company, location]
        )
    else:
        conn = get_connection()
        conn.execute(
            "UPDATE jobs SET updated_at = CURRENT_TIMESTAMP WHERE role = ? AND company = ? AND location = ?",
            (role, company, location)
        )
        conn.commit()
        conn.close()


def upsert_job(record: Dict[str, Any]) -> str:
    """
    Insert or update a job record. Returns 'new' or 'duplicate'.

    - 'new': Job with same (role, company, location) doesn't exist - inserted
    - 'duplicate': Job with same (role, company, location) exists - timestamp updated only
    """
    role = record.get("role")
    company = record.get("company")
    location = record.get("location", "")

    # Check if job already exists by content
    if job_exists(role, company, location):
        update_job_timestamp(role, company, location)
        return "duplicate"

    # New job - try to insert it
    values = (
        record.get("message_id"),
        record.get("sender"),
        record.get("date"),
        record.get("role"),
        record.get("company"),
        record.get("location", ""),
        record.get("experience", ""),
        None,  # interested defaults to NULL (not reviewed)
        None,  # metadata (can be populated later)
    )
    insert_sql = """
        INSERT INTO jobs (
            message_id, sender, date, role, company, location, experience, interested, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    if DB_TYPE == "turso":
        from libsql_client import LibsqlError  # pyrefly: ignore [missing-import]
        client = _get_turso_client()
        try:
            client.execute(insert_sql, list(values))
            return "new"
        except LibsqlError:
            # UNIQUE constraint on (message_id, role, company) violated
            # Treat as duplicate and update timestamp
            update_job_timestamp(role, company, location)
            return "duplicate"
    else:
        conn = get_connection()
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            conn.execute(insert_sql, values)
            conn.commit()
            conn.close()
            return "new"
        except sqlite3.IntegrityError:
            # UNIQUE constraint on (message_id, role, company) violated
            # Treat as duplicate and update timestamp
            conn.close()
            update_job_timestamp(role, company, location)
            return "duplicate"


def load_jobs_for_export() -> List[Dict[str, Any]]:
    """Fetch all jobs as list of dicts (for JSON export or display)."""
    query = """
        SELECT message_id, sender, date, role, company, location, experience, interested
        FROM jobs
        ORDER BY extracted_at DESC
    """
    if DB_TYPE == "turso":
        client = _get_turso_client()
        result = client.execute(query)
        return [dict(zip(result.columns, row)) for row in result.rows]
    else:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(query)
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
    if DB_TYPE == "turso":
        client = _get_turso_client()
        result = client.execute("SELECT message_id FROM jobs")
        return {row[0] for row in result.rows}
    else:
        conn = get_connection()
        cursor = conn.execute("SELECT message_id FROM jobs")
        # Return as a set for O(1) membership checks in the extractor
        ids = {row[0] for row in cursor.fetchall()}
        conn.close()
        return ids


# ---------------------------------------------------------------------------
# Web API Functions
# ---------------------------------------------------------------------------

def get_jobs(company: Optional[str] = None, interested_only: bool = False) -> List[Dict[str, Any]]:
    """Fetch jobs with optional filters for the web interface."""
    if DB_TYPE == "turso":
        client = _get_turso_client()
        query = "SELECT id, message_id, sender, date, role, company, location, experience, interested FROM jobs WHERE 1=1"
        params = []
        if company:
            query += " AND company LIKE ?"
            params.append(f"%{company}%")
        if interested_only:
            query += " AND interested = 1"
        query += " ORDER BY extracted_at DESC"

        result = client.execute(query, params)
        jobs = []
        for row in result.rows:
            jobs.append({
                "id": row[0], "message_id": row[1], "sender": row[2], "date": row[3],
                "role": row[4], "company": row[5], "location": row[6],
                "experience": row[7], "interested": row[8],
            })
        return jobs
    else:
        # Local SQLite
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        query = "SELECT id, message_id, sender, date, role, company, location, experience, interested FROM jobs WHERE 1=1"
        params = []
        if company:
            query += " AND company LIKE ?"
            params.append(f"%{company}%")
        if interested_only:
            query += " AND interested = 1"
        query += " ORDER BY extracted_at DESC"

        cursor = conn.execute(query, params)
        jobs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jobs


def get_stats() -> Dict[str, Any]:
    """Get aggregate job statistics."""
    if DB_TYPE == "turso":
        client = _get_turso_client()

        result = client.execute("""
            SELECT
                COUNT(*),
                COUNT(DISTINCT company),
                SUM(CASE WHEN interested = 1 THEN 1 ELSE 0 END)
            FROM jobs
        """)
        row = result.rows[0]
        total = row[0] or 0
        companies = row[1] or 0
        interested = row[2] or 0

        top_companies_result = client.execute("""
            SELECT company, COUNT(*) as count FROM jobs GROUP BY company ORDER BY count DESC LIMIT 5
        """)
        top_companies = [{"company": row[0], "count": row[1]} for row in top_companies_result.rows]

        return {
            "total_jobs": total,
            "unique_companies": companies,
            "interested_count": interested,
            "top_companies": top_companies
        }
    else:
        # Local SQLite
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        row = conn.execute("""
            SELECT
                COUNT(*),
                COUNT(DISTINCT company),
                SUM(CASE WHEN interested = 1 THEN 1 ELSE 0 END)
            FROM jobs
        """).fetchone()
        total = row[0] or 0
        companies = row[1] or 0
        interested = row[2] or 0
        top_companies = conn.execute("""
            SELECT company, COUNT(*) as count FROM jobs GROUP BY company ORDER BY count DESC LIMIT 5
        """).fetchall()
        conn.close()

        return {
            "total_jobs": total,
            "unique_companies": companies,
            "interested_count": interested,
            "top_companies": [dict(row) for row in top_companies]
        }


def set_interested(job_id: int, new_state: Optional[int]) -> Optional[int]:
    """Set interested state for a job directly."""
    if DB_TYPE == "turso":
        client = _get_turso_client()
        result = client.execute(
            "UPDATE jobs SET interested = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            [new_state, job_id]
        )
        if result.rows_affected == 0:
            return None
        return new_state
    else:
        # Local SQLite
        conn = get_connection()
        cursor = conn.execute(
            "UPDATE jobs SET interested = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_state, job_id)
        )
        conn.commit()
        conn.close()
        if cursor.rowcount == 0:
            return None
        return new_state

