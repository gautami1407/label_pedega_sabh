"""
Regulatory data quality audit utilities.

Identifies and isolates questionable records that must not be served
to users without human verification.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path


QUARANTINE_REASONS = {
    "synthetic_additive": "Synthetic placeholder additive (SA-xxx pattern)",
    "variant_placeholder": "Synthetic variant placeholder record",
    "fssai_prohibited_synthetic": "FSSAI Prohibited synthetic entry",
    "missing_identity": "Missing both E-number and additive name",
    "suspicious_authority": "Non-standard regulatory authority reference",
}

SYNTHETIC_SA_PATTERN = re.compile(r"synthetic additive sa-\d+", re.IGNORECASE)
VARIANT_PATTERN = re.compile(r"\bvariant\s+\d+\b", re.IGNORECASE)
FSSAI_SYNTHETIC_PATTERN = re.compile(r"^fssai prohibited$", re.IGNORECASE)


@dataclass
class AuditResult:
    verified_rows: list[dict]
    quarantined_rows: list[dict]
    quarantine_reasons: dict[str, int]

    @property
    def verified_count(self) -> int:
        return len(self.verified_rows)

    @property
    def quarantined_count(self) -> int:
        return len(self.quarantined_rows)


def classify_row(row: dict) -> str | None:
    """
    Return quarantine reason key if row should be isolated, else None.
    """
    additive_name = (
        row.get("Additive_name")
        or row.get("Additive_Name")
        or ""
    ).strip()
    e_number = (
        row.get("E_number")
        or row.get("E_Number")
        or ""
    ).strip()
    authority = (row.get("Regulatory_authority") or "").strip()
    status = (row.get("Status") or "").strip()

    if not e_number and not additive_name:
        return "missing_identity"

    name_lower = additive_name.lower()

    if SYNTHETIC_SA_PATTERN.search(name_lower):
        return "synthetic_additive"

    if VARIANT_PATTERN.search(name_lower):
        return "variant_placeholder"

    if FSSAI_SYNTHETIC_PATTERN.match(authority) and "synthetic" in name_lower:
        return "fssai_prohibited_synthetic"

    if authority.lower() == "fssai prohibited" and status.lower().startswith("banned"):
        if "synthetic" in name_lower or re.search(r"sa-\d+", name_lower):
            return "fssai_prohibited_synthetic"

    return None


def audit_regulatory_csv(csv_path: Path) -> AuditResult:
    """Split a regulatory CSV into verified and quarantined record sets."""
    verified: list[dict] = []
    quarantined: list[dict] = []
    reason_counts: dict[str, int] = {}

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []

        for row in reader:
            reason = classify_row(row)
            if reason:
                row_copy = dict(row)
                row_copy["_quarantine_reason"] = reason
                quarantined.append(row_copy)
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
            else:
                verified.append(row)

    return AuditResult(
        verified_rows=verified,
        quarantined_rows=quarantined,
        quarantine_reasons=reason_counts,
    )


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    """Write rows to CSV, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_audit(
    source: Path,
    verified_dest: Path,
    quarantine_dest: Path,
) -> AuditResult:
    """Execute audit and write verified + quarantined output files."""
    result = audit_regulatory_csv(source)

    with source.open("r", encoding="utf-8", newline="") as handle:
        fieldnames = list(csv.DictReader(handle).fieldnames or [])

    write_csv(verified_dest, result.verified_rows, fieldnames)

    quarantine_fields = fieldnames + ["_quarantine_reason"]
    write_csv(quarantine_dest, result.quarantined_rows, quarantine_fields)

    return result
