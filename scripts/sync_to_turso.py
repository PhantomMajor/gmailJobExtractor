"""
Sync extracted jobs from local SQLite to Turso (cloud).
Implements insert-if-new + last-write-wins update strategy.

Usage:
  python scripts/sync_to_turso.py
"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
# pyrefly: ignore [missing-import]
import db  # Database module (supports both local and Turso)

load_dotenv(dotenv_path='.env')


def sync_to_turso():
    """
    Sync jobs from local DB to Turso.

    Strategy:
    1. For new rows (not in Turso): INSERT with interested=NULL
    2. For existing rows: last-write-wins on interested via updated_at
       - If local's updated_at > Turso's, push (interested, updated_at)
       - Otherwise, skip (keep cloud version)

    This ensures:
    - Local changes eventually reach the cloud
    - Cloud-side toggles made on the dashboard are never clobbered
    """
    print("Starting sync to Turso...")

    try:
        # Get all jobs from local DB
        local_conn = db.get_connection()
        local_conn.row_factory = __import__("sqlite3").Row
        local_jobs = local_conn.execute("""
            SELECT id, message_id, role, company, location, interested, updated_at
            FROM jobs
            ORDER BY updated_at DESC
        """).fetchall()
        local_conn.close()

        print(f"Found {len(local_jobs)} jobs in local DB")

        # Get Turso client
        turso_client = db._get_turso_client()

        # Build a map of Turso jobs by (message_id, role, company)
        turso_jobs_result = turso_client.execute("""
            SELECT message_id, role, company, interested, updated_at
            FROM jobs
        """)

        turso_map = {}
        for row in turso_jobs_result.rows:
            key = (row[0], row[1], row[2])  # (message_id, role, company)
            turso_map[key] = {
                "interested": row[3],
                "updated_at": row[4]
            }

        print(f"Found {len(turso_map)} jobs in Turso")

        # Sync logic
        new_count = 0
        updated_count = 0
        skipped_count = 0

        for local_job in local_jobs:
            msg_id = local_job["message_id"]
            role = local_job["role"]
            company = local_job["company"]
            location = local_job["location"]
            interested = local_job["interested"]
            updated_at = local_job["updated_at"]

            key = (msg_id, role, company)

            if key not in turso_map:
                # New job: insert with interested=NULL
                turso_client.execute("""
                    INSERT INTO jobs (message_id, role, company, location, interested, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, [msg_id, role, company, location, None, updated_at])
                new_count += 1
            else:
                # Existing job: check if local is newer
                turso_updated_at = turso_map[key]["updated_at"]

                # Compare timestamps (string comparison works for ISO format)
                if updated_at and turso_updated_at and updated_at > turso_updated_at:
                    # Local is newer: push interested + updated_at
                    turso_client.execute("""
                        UPDATE jobs SET interested = ?, updated_at = ? WHERE message_id = ? AND role = ? AND company = ?
                    """, [interested, updated_at, msg_id, role, company])
                    updated_count += 1
                else:
                    # Cloud is newer or equal: skip
                    skipped_count += 1

        print(f"\nSync complete:")
        print(f"  New jobs inserted: {new_count}")
        print(f"  Jobs updated (local newer): {updated_count}")
        print(f"  Jobs skipped (cloud newer): {skipped_count}")

    except Exception as e:
        print(f"Sync failed: {e}")
        raise


if __name__ == "__main__":
    sync_to_turso()
