#!/usr/bin/env python
"""
Simple script to run the Flask app
"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# pyrefly: ignore [missing-import]
from app import app

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
