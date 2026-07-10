#!/usr/bin/env python3
"""
Import verified regulatory CSV records into MongoDB ingredients collection.

Usage:
    python scripts/import_ingredients_to_mongo.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from lps.shared.db.mongo import get_mongo_db, mongo_ping  # noqa: E402


def build_ingredient_doc(name: str, e_number: str, records: list[dict]) -> dict:
    regulatory_status = {}
    aliases = []
    if e_number:
        aliases.append(e_number)
    aliases.append(name)

    for record in records:
        country = record.get("country") or "Unknown"
        regulatory_status[country] = {
            "status": record.get("status", "Unknown"),
            "authority": record.get("authority", ""),
            "reason": record.get("reason", ""),
            "risk_level": record.get("risk_level", "Low"),
            "category": record.get("category", ""),
        }

    slug = (e_number or name).lower().replace(" ", "-").replace("/", "-")
    return {
        "_id": slug,
        "name": name,
        "aliases": list(dict.fromkeys(aliases)),
        "e_number": e_number,
        "purpose": records[0].get("category", ""),
        "simple_explanation": records[0].get("reason", "") or f"Food additive: {name}",
        "regulatory_status": regulatory_status,
        "data_quality": "verified",
        "source": "regulatory_database_verified.csv",
    }


def main() -> int:
    if not mongo_ping():
        print("ERROR: MongoDB is not reachable. Start docker-compose first.")
        return 1

    verified_csv = BACKEND_DIR / "data" / "regulatory_database_verified.csv"
    if not verified_csv.exists():
        print(f"ERROR: Verified CSV not found: {verified_csv}")
        return 1

    grouped: dict[str, dict] = {}
    with verified_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            name = (row.get("Additive_name") or row.get("Additive_Name") or "").strip()
            e_number = (row.get("E_number") or row.get("E_Number") or "").strip()
            if not name and not e_number:
                continue
            key = (e_number or name).lower()
            if key not in grouped:
                grouped[key] = {"name": name or e_number, "e_number": e_number, "records": []}
            grouped[key]["records"].append({
                "country": (row.get("Country") or row.get("Region") or "").strip(),
                "status": (row.get("Status") or "").strip(),
                "reason": (row.get("Reason") or row.get("Ban_Reason") or "").strip(),
                "authority": (row.get("Regulatory_authority") or "").strip(),
                "risk_level": (row.get("Risk_Level") or "Low").strip(),
                "category": (row.get("Category") or row.get("Functional_Class") or "").strip(),
            })

    db = get_mongo_db()
    collection = db["ingredients"]
    docs = [build_ingredient_doc(g["name"], g["e_number"], g["records"]) for g in grouped.values()]

    if docs:
        for doc in docs:
            collection.replace_one({"_id": doc["_id"]}, doc, upsert=True)

    collection.create_index("name")
    collection.create_index("e_number")
    collection.create_index("aliases")

    print(f"Imported {len(docs)} ingredients into MongoDB collection 'ingredients'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
