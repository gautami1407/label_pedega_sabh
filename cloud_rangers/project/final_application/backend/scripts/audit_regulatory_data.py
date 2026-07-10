#!/usr/bin/env python3
"""
One-time regulatory data audit script.

Splits regulatory_database.csv into:
  - data/regulatory_database_verified.csv  (production use)
  - data/quarantined_regulatory_records.csv (admin review)

Usage:
    python scripts/audit_regulatory_data.py
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from lps.shared.regulatory_audit import run_audit  # noqa: E402


def main() -> int:
    source = BACKEND_DIR / "regulatory_database.csv"
    data_dir = BACKEND_DIR / "data"
    verified = data_dir / "regulatory_database_verified.csv"
    quarantine = data_dir / "quarantined_regulatory_records.csv"

    if not source.exists():
        print(f"ERROR: Source file not found: {source}")
        return 1

    result = run_audit(source, verified, quarantine)

    print("Regulatory Data Audit Complete")
    print(f"  Source:     {source}")
    print(f"  Verified:   {result.verified_count} records -> {verified}")
    print(f"  Quarantined: {result.quarantined_count} records -> {quarantine}")
    if result.quarantine_reasons:
        print("  Quarantine breakdown:")
        for reason, count in sorted(result.quarantine_reasons.items()):
            print(f"    - {reason}: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
