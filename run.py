#!/usr/bin/env python
"""
Simple script to run the Flask app
"""

import sys
import os
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Parse arguments BEFORE importing app (so DB_TYPE is set early)
parser = argparse.ArgumentParser(description="Run the Job Dashboard Flask app")
parser.add_argument("--db", choices=["sqlite", "turso"], help="Override DB_TYPE env var (sqlite or turso)")
args = parser.parse_args()

if args.db:
    os.environ["DB_TYPE"] = args.db

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# pyrefly: ignore [missing-import]
from app import app

if __name__ == "__main__":
    db_type = os.getenv("DB_TYPE", "sqlite")
    print(f"🚀 Starting dashboard with DB_TYPE={db_type}")
    app.run(debug=True, host="127.0.0.1", port=5000)
