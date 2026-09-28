#!/usr/bin/env python3
"""
Classify phone numbers for Kuwait scraper data.

Buckets
-------
valid_phones            Kuwait 965 + 8 digits; local first digit in 2/4/5/6/9
invalid_phones          Fake/malformed (bad length, bad local prefix, etc.)
outside_country_phones  Wrong country code (not 965)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal, Optional

Category = Literal["valid", "invalid", "outside_country", "empty"]

_NON_DIGIT_RE = re.compile(r"[^\d+]")
_LEADING_PLUS_RE = re.compile(r"^\++")

# Kuwait national number: 8 digits, first digit in 2/4/5/6/9
_KW_LOCAL = re.compile(r"^[24569]\d{7}$")
_KW_E164 = re.compile(r"^965[24569]\d{7}$")

PHONE_COLUMN_ALIASES = frozenset(
    {
        "phone",
        "phones",
        "mobile",
        "mobile number",
        "mobile_number",
        "phone number",
        "phone_number",
        "contact number",
        "contact_number",
        "contact_numbers",
        "telephone",
        "tel",
        "whatsapp",
        "contact",
    }
)


@dataclass(frozen=True)
class PhoneValidationResult:
    raw: str
    normalized: str
    category: Category
    reason: str
    valid: bool  # True only when category == "valid"

    def as_dict(self) -> dict[str, Any]:
        return {
            "raw": self.raw,
            "normalized": self.normalized,
            "category": self.category,
            "reason": self.reason,
            "valid": self.valid,
        }


def _norm_col(name: Any) -> str:
    if name is None:
        return ""
    return str(name).strip().lower().replace("_", " ")


def find_phone_column(columns: list[Any]) -> Optional[Any]:
    """Return the first column whose name matches a known phone alias."""
    for col in columns:
        if _norm_col(col) in PHONE_COLUMN_ALIASES:
            return col
    return None


def normalize_digits(value: Any) -> str:
    """
    Strip formatting. Local Kuwait 8-digit numbers get a 965 prefix.

    Returns digits only (no leading '+'). Empty string if nothing usable.
    """
    if value is None:
        return ""

    # Excel sometimes stores phones as floats (e.g. 96550000000.0).
    if isinstance(value, float):
        if value != value:  # NaN
            return ""
        if value.is_integer():
            value = int(value)
        else:
            value = str(value)

    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "-", "n/a", "na"}:
        return ""

    # Drop trailing .0 from stringified floats.
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".", 1)[0]

    text = _NON_DIGIT_RE.sub("", text)
    text = _LEADING_PLUS_RE.sub("", text)

    # International dialing prefix 00… (only when a full country number remains)
    if text.startswith("00") and len(text) >= 12:
        text = text[2:]

    # Local Kuwait 8-digit → add 965
    if _KW_LOCAL.fullmatch(text):
        return "965" + text

    return text


def validate_phone(value: Any) -> PhoneValidationResult:
    """
    Classify a phone value into valid / invalid / outside_country / empty.
    """
    raw = "" if value is None else str(value).strip()
    digits = normalize_digits(value)

    if not digits:
        return PhoneValidationResult(
            raw=raw,
            normalized="",
            category="empty",
            reason="empty or missing",
            valid=False,
        )

    if len(set(digits)) == 1:
        return PhoneValidationResult(
            raw=raw,
            normalized=digits,
            category="invalid",
            reason="all identical digits",
            valid=False,
        )

    if _KW_E164.fullmatch(digits):
        return PhoneValidationResult(
            raw=raw,
            normalized="+" + digits,
            category="valid",
            reason="valid Kuwait number",
            valid=True,
        )

    # Explicit Kuwait country code but malformed national part
    if digits.startswith("965"):
        if len(digits) != 11:
            return PhoneValidationResult(
                raw=raw,
                normalized=digits,
                category="invalid",
                reason=f"Kuwait number has {len(digits)} digits (expected 11)",
                valid=False,
            )
        return PhoneValidationResult(
            raw=raw,
            normalized=digits,
            category="invalid",
            reason="Kuwait number has bad local prefix (expected 2/4/5/6/9)",
            valid=False,
        )

    # Another country code (typical E.164 lengths) — not Kuwait
    if 10 <= len(digits) <= 15:
        return PhoneValidationResult(
            raw=raw,
            normalized=digits,
            category="outside_country",
            reason="wrong country code (not 965)",
            valid=False,
        )

    # Local 8-digit with bad prefix, or other short garbage
    if len(digits) == 8:
        return PhoneValidationResult(
            raw=raw,
            normalized=digits,
            category="invalid",
            reason="Kuwait local number has bad prefix (expected 2/4/5/6/9)",
            valid=False,
        )

    return PhoneValidationResult(
        raw=raw,
        normalized=digits,
        category="invalid",
        reason="malformed phone number",
        valid=False,
    )


# Back-compat alias used by older call sites
classify_phone = validate_phone
