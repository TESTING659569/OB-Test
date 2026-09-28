#!/usr/bin/env python3
"""Quick self-check for phone validation rules (no R2 required)."""

from phone_validator import validate_phone

CASES = [
    # valid — Kuwait 965 + 8 digits, local first digit in 2/4/5/6/9
    ("+96550000001", "valid"),
    ("96561234567", "valid"),
    ("96541234567", "valid"),
    ("50001234", "valid"),
    ("22345678", "valid"),
    (96550001234.0, "valid"),
    # outside_country — not 965
    ("+966501234567", "outside_country"),
    ("971501234567", "outside_country"),
    # invalid — malformed Kuwait / garbage
    ("", "empty"),
    ("123", "invalid"),
    ("96512345678", "invalid"),  # bad KW local prefix (1)
    ("96531234567", "invalid"),  # bad KW local prefix (3)
    ("70001234", "invalid"),  # bad local prefix
    ("00000000", "invalid"),
]


def main() -> int:
    failed = 0
    for raw, expect_category in CASES:
        result = validate_phone(raw)
        ok = result.category == expect_category
        mark = "OK" if ok else "FAIL"
        if not ok:
            failed += 1
        print(
            f"[{mark}] raw={raw!r:20} category={result.category:16} "
            f"reason={result.reason} norm={result.normalized}"
        )
    print(f"\n{len(CASES) - failed}/{len(CASES)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
