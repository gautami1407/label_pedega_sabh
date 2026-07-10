"""
Barcode validation utilities.
"""
from __future__ import annotations

import re


_BARCODE_PATTERN = re.compile(r"^\d{8,14}$")


def normalize_barcode(value: str) -> str:
    return "".join(ch for ch in str(value or "").strip() if ch.isdigit())


def validate_ean13_checksum(barcode: str) -> bool:
    if len(barcode) != 13 or not barcode.isdigit():
        return False
    digits = [int(d) for d in barcode]
    checksum = digits[-1]
    total = sum(d * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits[:-1]))
    return (10 - (total % 10)) % 10 == checksum


def validate_upc_a_checksum(barcode: str) -> bool:
    if len(barcode) != 12 or not barcode.isdigit():
        return False
    digits = [int(d) for d in barcode]
    checksum = digits[-1]
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(digits[:-1]))
    return (10 - (total % 10)) % 10 == checksum


def validate_barcode(value: str) -> tuple[bool, str]:
    """
    Validate barcode format and checksum where applicable.

    Returns (is_valid, reason_if_invalid).
    """
    barcode = normalize_barcode(value)
    if not barcode:
        return False, "Barcode is empty."
    if not _BARCODE_PATTERN.match(barcode):
        return False, "Barcode must contain 8 to 14 digits."

    if len(barcode) == 13 and not validate_ean13_checksum(barcode):
        return False, "Invalid EAN-13 checksum."
    if len(barcode) == 12 and not validate_upc_a_checksum(barcode):
        return False, "Invalid UPC-A checksum."
    if len(barcode) == 8:
        # EAN-8 checksum uses same weighting as EAN-13 on 7 digits
        padded = barcode.zfill(13)
        if not validate_ean13_checksum(padded):
            return False, "Invalid EAN-8 checksum."

    return True, ""
