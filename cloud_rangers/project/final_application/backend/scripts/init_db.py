#!/usr/bin/env python3
"""
Initialize PostgreSQL schema via Alembic/SQLAlchemy.

Usage:
    python scripts/init_db.py
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from lps.shared.db.postgres import init_db  # noqa: E402


def main() -> int:
    init_db()
    print("Database schema initialized.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
