#!/usr/bin/env python3
"""
Count all objects under R2 prefixes for monitor report.json.

Shared with the Pro1-Os monitor hub — keep in sync when the hub copy changes.

When multiple scrapers share one R2 base path (e.g. boshamlan properties rent/sale/exchange),
pass category_slug so only that category's Excel files and images are counted.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Iterable

_EXCEL_FOLDERS = ("excel files", "excel-files")

# File extension → type (lowercase, with leading ".")
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".svg"}
_JSON_EXTS = {".json"}
_EXCEL_EXTS = {".xlsx", ".xls", ".xlsm"}
_CSV_EXTS = {".csv"}
_PARQUET_EXTS = {".parquet"}

# Flattened output field order (keeps code/exports consistent).
_R2_TYPES: tuple[str, ...] = ("images", "json", "excel", "csv", "parquet", "other")

# r2_base -> list of non-folder objects (cached for shared prefixes like properties/)
_PREFIX_OBJECT_CACHE: dict[str, list[dict[str, int | str]]] = {}


def _normalize_prefix(prefix: str) -> str:
    return prefix.strip("/")


def _date_partition(partition_dt: date | datetime) -> str:
    if isinstance(partition_dt, datetime):
        partition_dt = partition_dt.date()
    return f"year={partition_dt.year}/month={partition_dt.month:02d}/day={partition_dt.day:02d}"


def _list_objects_direct(client, bucket: str, prefix: str) -> list[dict[str, int | str]]:
    """List objects under *prefix* without using the full-prefix cache."""
    objects: list[dict[str, int | str]] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj.get("Key", "")
            if not key.endswith("/"):
                objects.append({"Key": key, "Size": _object_size_bytes(obj)})
    return objects


def _object_size_bytes(obj: dict) -> int:
    size = obj.get("Size", 0)
    try:
        return int(size)
    except (TypeError, ValueError):
        return 0


def category_slug_from_excel_pattern(pattern: str) -> str | None:
    """rent.xlsx -> rent; wildcard patterns -> None (count full prefix)."""
    if not pattern or "{" in pattern:
        return None
    filename = pattern.split("/")[-1].strip()
    lower = filename.lower()
    if lower.endswith(".xlsx"):
        return filename[: -len(".xlsx")].lower()
    return None


def _key_matches_category(key: str, category_slug: str) -> bool:
    """Match category Excel files and images under a shared properties prefix."""
    if key.endswith("/"):
        return False

    slug = category_slug.lower()
    key_lower = key.lower()

    for folder in _EXCEL_FOLDERS:
        # Excel category files are usually named "<slug>.xlsx" under
        # either "excel files/" or "excel-files/".
        if any(
            key_lower.endswith(f"/{folder}/{slug}{ext}")
            for ext in (".xlsx", ".xls", ".xlsm")
        ):
            return True

    # Images are under /images/<slug>/...
    if f"/images/{slug}/" in key_lower:
        return True

    # When a shared prefix contains non-Excel files for multiple categories,
    # restrict them by slug presence to avoid double counting across scrapers.
    # This is constrained to the category slug.
    if f"/{slug}/" in key_lower:
        return True
    for ext in (".json", ".csv", ".parquet"):
        if key_lower.endswith(f"{slug}{ext}"):
            return True

    return False


def _object_matches_category(obj: dict[str, int | str], category_slug: str) -> bool:
    key = str(obj.get("Key", ""))
    return _key_matches_category(key, category_slug)


def _list_objects(client, bucket: str, r2_base: str) -> list[dict[str, int | str]]:
    normalized = _normalize_prefix(r2_base)
    if not normalized:
        return []

    if normalized in _PREFIX_OBJECT_CACHE:
        return _PREFIX_OBJECT_CACHE[normalized]

    objects: list[dict[str, int | str]] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=f"{normalized}/"):
        for obj in page.get("Contents", []):
            key = obj.get("Key", "")
            if not key.endswith("/"):
                objects.append({"Key": key, "Size": _object_size_bytes(obj)})

    _PREFIX_OBJECT_CACHE[normalized] = objects
    return objects


def clear_prefix_cache() -> None:
    """Reset cached listings (useful in tests)."""
    _PREFIX_OBJECT_CACHE.clear()


def _file_type_from_key(key: str) -> str:
    """Deduce file type from object key extension."""
    key_lower = key.lower()
    # Avoid misclassifying directory marker objects.
    if key_lower.endswith("/"):
        return "other"

    for ext in _IMAGE_EXTS:
        if key_lower.endswith(ext):
            return "images"
    for ext in _JSON_EXTS:
        if key_lower.endswith(ext):
            return "json"
    for ext in _EXCEL_EXTS:
        if key_lower.endswith(ext):
            return "excel"
    for ext in _CSV_EXTS:
        if key_lower.endswith(ext):
            return "csv"
    for ext in _PARQUET_EXTS:
        if key_lower.endswith(ext):
            return "parquet"
    return "other"


def _inventory_aggregate_by_type(objects: Iterable[dict[str, int | str]]) -> dict[str, int]:
    """Return counts + byte totals split by file type."""
    result: dict[str, int] = {f"{t}_count": 0 for t in _R2_TYPES} | {f"{t}_bytes": 0 for t in _R2_TYPES}
    result["total_count"] = 0
    result["total_bytes"] = 0

    for obj in objects:
        key = str(obj.get("Key", ""))
        size_bytes = _object_size_bytes(obj)
        t = _file_type_from_key(key)
        result[f"{t}_count"] += 1
        result[f"{t}_bytes"] += size_bytes
        result["total_count"] += 1
        result["total_bytes"] += size_bytes

    return result


def count_r2_inventory_by_type(client, bucket: str, r2_prefix: str) -> dict[str, int]:
    """Count objects and sum bytes under *r2_prefix*, split by file type."""
    normalized = _normalize_prefix(r2_prefix)
    if not normalized:
        return {f"{t}_count": 0 for t in _R2_TYPES} | {f"{t}_bytes": 0 for t in _R2_TYPES} | {
            "total_count": 0,
            "total_bytes": 0,
        }

    objects = _list_objects(client, bucket, normalized)
    return _inventory_aggregate_by_type(objects)


def count_daily_r2_inventory_by_type(
    client,
    bucket: str,
    r2_prefix: str,
    partition_dt: date | datetime,
) -> dict[str, int]:
    """Count objects and sum bytes in one daily partition folder."""
    normalized = _normalize_prefix(r2_prefix)
    if not normalized:
        return {f"{t}_count": 0 for t in _R2_TYPES} | {f"{t}_bytes": 0 for t in _R2_TYPES} | {
            "total_count": 0,
            "total_bytes": 0,
        }

    daily_prefix = f"{normalized}/{_date_partition(partition_dt)}/"
    objects = _list_objects_direct(client, bucket, daily_prefix)
    return _inventory_aggregate_by_type(objects)


def count_scraper_r2_inventory_by_type(
    client,
    bucket: str,
    r2_base: str,
    partition_dt: date | datetime | None = None,
    category_slug: str | None = None,
) -> dict[str, int]:
    """
    Scraper attribution version of inventory-by-type.

    - When partition_dt is None: counts/sums for the full scraper prefix (cached).
    - When partition_dt is provided: counts/sums for one daily partition folder.
    - When category_slug is provided: restricts objects to that category (keeps
      existing shared-prefix behavior for Excel/images scrapers).
    """
    normalized = _normalize_prefix(r2_base)
    if not normalized:
        return {f"{t}_count": 0 for t in _R2_TYPES} | {f"{t}_bytes": 0 for t in _R2_TYPES} | {
            "total_count": 0,
            "total_bytes": 0,
        }

    if partition_dt is None:
        objects = _list_objects(client, bucket, normalized)
    else:
        daily_prefix = f"{normalized}/{_date_partition(partition_dt)}/"
        objects = _list_objects_direct(client, bucket, daily_prefix)

    if category_slug:
        objects = [obj for obj in objects if _object_matches_category(obj, category_slug)]

    return _inventory_aggregate_by_type(objects)


def count_site_r2_inventory_by_type(
    client,
    bucket: str,
    r2_prefix: str,
    partition_dt: date | datetime | None = None,
) -> dict[str, int]:
    """Site inventory-by-type. Includes monitor/ artifacts (same scope as old counters)."""
    normalized = _normalize_prefix(r2_prefix)
    if not normalized:
        return {f"{t}_count": 0 for t in _R2_TYPES} | {f"{t}_bytes": 0 for t in _R2_TYPES} | {
            "total_count": 0,
            "total_bytes": 0,
        }

    if partition_dt is None:
        objects = _list_objects(client, bucket, normalized)
    else:
        daily_prefix = f"{normalized}/{_date_partition(partition_dt)}/"
        objects = _list_objects_direct(client, bucket, daily_prefix)

    return _inventory_aggregate_by_type(objects)


def count_scraper_r2_files(
    client,
    bucket: str,
    r2_base: str,
    category_slug: str | None = None,
) -> int:
    """Count objects for one scraper — full prefix, or one category when shared."""
    objects = _list_objects(client, bucket, r2_base)
    if category_slug:
        return sum(1 for obj in objects if _object_matches_category(obj, category_slug))
    return len(objects)


def count_scraper_r2_size_bytes(
    client,
    bucket: str,
    r2_base: str,
    category_slug: str | None = None,
) -> int:
    """Sum object sizes for one scraper — full prefix, or one category when shared."""
    objects = _list_objects(client, bucket, r2_base)
    if category_slug:
        return sum(_object_size_bytes(obj) for obj in objects if _object_matches_category(obj, category_slug))
    return sum(_object_size_bytes(obj) for obj in objects)


def count_scraper_r2_daily_size_bytes(
    client,
    bucket: str,
    r2_base: str,
    partition_dt: date | datetime,
    category_slug: str | None = None,
) -> int:
    """Sum object sizes for one scraper partition (year=/month=/day=)."""
    normalized = _normalize_prefix(r2_base)
    if not normalized:
        return 0

    daily_prefix = f"{normalized}/{_date_partition(partition_dt)}/"
    objects = _list_objects_direct(client, bucket, daily_prefix)
    if category_slug:
        return sum(
            _object_size_bytes(obj)
            for obj in objects
            if _object_matches_category(obj, category_slug)
        )
    return sum(_object_size_bytes(obj) for obj in objects)


def count_site_r2_files(client, bucket: str, r2_prefix: str) -> int:
    """Count every object under the site R2 prefix (includes monitor/ artifacts)."""
    return len(_list_objects(client, bucket, r2_prefix))


def count_site_r2_size_bytes(client, bucket: str, r2_prefix: str) -> int:
    """Sum object sizes under the site R2 prefix (includes monitor/ artifacts)."""
    return sum(_object_size_bytes(obj) for obj in _list_objects(client, bucket, r2_prefix))


def count_site_r2_daily_size_bytes(
    client,
    bucket: str,
    r2_prefix: str,
    partition_dt: date | datetime,
) -> int:
    """Sum object sizes under the site prefix for one date partition."""
    normalized = _normalize_prefix(r2_prefix)
    if not normalized:
        return 0

    partition_needle = f"/{_date_partition(partition_dt)}/"
    return sum(
        _object_size_bytes(obj)
        for obj in _list_objects(client, bucket, normalized)
        if partition_needle in str(obj.get("Key", ""))
    )
