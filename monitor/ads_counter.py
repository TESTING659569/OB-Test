#!/usr/bin/env python3
"""
Count unique ads for monitor report.json.

Shared with the Pro1-Os monitor hub — keep in sync when the hub copy changes.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from validation.phone_validator import validate_phone

SKIP_SHEETS = frozenset({"info", "no data"})
ID_COLUMN_ALIASES = frozenset(
    {
        "id",
        "listing id",
        "listing_id",
        "user adv id",
        "user_adv_id",
        "ad id",
        "ad_id",
    }
)
JSON_COUNT_KEYS = ("total_listings", "total_ads", "listings_count")
PHONE_COLUMN_ALIASES = frozenset(
    {
        "mobile number",
        "mobile_number",
        "telephone",
        "phone",
        "phone number",
        "contact number",
        "whatsapp",
    }
)
PUBLISHED_COLUMN_ALIASES = frozenset(
    {
        "date published",
        "date_published",
        "published at",
        "published_at",
    }
)
LEVEL3_COLUMN_ALIASES = frozenset({"level 3", "level_3", "brand", "model"})


def _norm_col(name: Any) -> str:
    if name is None:
        return ""
    return str(name).strip().lower().replace("_", " ")


def _should_skip_sheet(name: str) -> bool:
    lower = name.strip().lower()
    return lower in SKIP_SHEETS or name in ("Info", "No Data")


def _find_id_column(columns: list[Any]) -> str | None:
    for col in columns:
        if _norm_col(col) in ID_COLUMN_ALIASES:
            return col
    return None


def _find_col_by_alias(columns: list[Any], aliases: frozenset[str]) -> str | None:
    for col in columns:
        if _norm_col(col) in aliases:
            return col
    return None


def _classify_phone_buckets(value: Any) -> tuple[str, str]:
    """
    Return (bucket, normalized_label) for a phone cell.

    bucket is one of: valid | invalid | outside_country
    Empty cells return ("", "").
    """
    result = validate_phone(value)
    if result.category == "empty":
        return "", ""
    label = result.normalized or result.raw
    if result.category == "valid":
        return "valid", label
    if result.category == "outside_country":
        return "outside_country", label
    return "invalid", label


def _extract_hour(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return int(value.hour)
    if hasattr(value, "hour") and isinstance(getattr(value, "hour", None), int):
        return int(value.hour)

    text = str(value).strip()
    if not text:
        return None

    # Fast path for HH:MM(:SS) patterns without pandas parsing overhead.
    import re

    m = re.search(r"\b([01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?\b", text)
    if m:
        return int(m.group(1))

    # Try explicit known formats first to avoid parser warnings/noise.
    for fmt in (
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ):
        parsed = pd.to_datetime(text, format=fmt, errors="coerce")
        if not pd.isna(parsed):
            return int(parsed.hour)

    # Fallback for other parsable variants. dayfirst=True matches dd-mm-yyyy data.
    parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return None
    return int(parsed.hour)


def _peak_from_hourly(hourly: dict[int, int]) -> tuple[int | None, int]:
    if not hourly:
        return None, 0
    peak_hour = min(hourly.keys())
    peak_ads = -1
    for hour, count in hourly.items():
        if count > peak_ads or (count == peak_ads and hour < peak_hour):
            peak_hour = hour
            peak_ads = count
    return peak_hour, peak_ads


def _period_from_hour(hour: int) -> str:
    if 0 <= hour <= 3:
        return "00-04 (12am-4am)"
    if 4 <= hour <= 7:
        return "04-08 (4am-8am)"
    if 8 <= hour <= 11:
        return "08-12 (8am-12pm)"
    if 12 <= hour <= 15:
        return "12-16 (12pm-4pm)"
    if 16 <= hour <= 19:
        return "16-20 (4pm-8pm)"
    return "20-24 (8pm-12am)"


def _empty_phone_bucket_sets() -> dict[str, set[str]]:
    return {
        "valid": set(),
        "invalid": set(),
        "outside_country": set(),
    }


def _phone_bucket_counts(buckets: dict[str, set[str]]) -> dict[str, int]:
    valid = len(buckets["valid"])
    invalid = len(buckets["invalid"])
    outside = len(buckets["outside_country"])
    return {
        "valid_phones": int(valid),
        "invalid_phones": int(invalid),
        "outside_country_phones": int(outside),
        # Backward-compatible total of all classified unique numbers
        "unique_phones": int(valid + invalid + outside),
    }


def _count_from_excel_files(
    excel_downloads: list[tuple[str, bytes]],
) -> dict:
    """Return ad/phone/hierarchy metrics from Excel bytes."""
    all_ids: set[str] = set()
    phone_buckets = _empty_phone_bucket_sets()
    total_rows = 0
    saw_id_column = False
    subcategory_breakdown: list[dict[str, Any]] = []
    scraper_hourly: dict[int, int] = {}

    for _key, raw in excel_downloads:
        try:
            sheets = pd.read_excel(BytesIO(raw), sheet_name=None, engine="openpyxl")
        except Exception:
            continue

        for sheet_name, df in sheets.items():
            if _should_skip_sheet(sheet_name):
                continue
            if df is None or df.empty:
                continue

            n = len(df)
            total_rows += n

            columns = list(df.columns)
            id_col = _find_id_column(columns)
            phone_col = _find_col_by_alias(columns, PHONE_COLUMN_ALIASES)
            date_col = _find_col_by_alias(columns, PUBLISHED_COLUMN_ALIASES)
            level3_col = _find_col_by_alias(columns, LEVEL3_COLUMN_ALIASES)

            sheet_ids: set[str] = set()
            if id_col is not None:
                saw_id_column = True
                for val in df[id_col].dropna():
                    text = str(val).strip()
                    if text:
                        sheet_ids.add(text)
                        all_ids.add(text)

            sheet_buckets = _empty_phone_bucket_sets()
            if phone_col is not None:
                for val in df[phone_col].dropna():
                    bucket, label = _classify_phone_buckets(val)
                    if not bucket:
                        continue
                    sheet_buckets[bucket].add(label)
                    phone_buckets[bucket].add(label)

            sheet_phone_counts = _phone_bucket_counts(sheet_buckets)

            sheet_hourly: dict[int, int] = {}
            if date_col is not None:
                for val in df[date_col].dropna():
                    hour = _extract_hour(val)
                    if hour is None:
                        continue
                    sheet_hourly[hour] = sheet_hourly.get(hour, 0) + 1
                    scraper_hourly[hour] = scraper_hourly.get(hour, 0) + 1

            level3_breakdown: list[dict[str, Any]] = []
            if level3_col is not None:
                level3_series = df[level3_col].fillna("").astype(str).str.strip()
                for level3 in sorted({v for v in level3_series.tolist() if v}):
                    mask = level3_series == level3
                    lvl_rows = int(mask.sum())
                    if lvl_rows <= 0:
                        continue
                    if id_col is not None:
                        lvl_ads = (
                            df.loc[mask, id_col].dropna().astype(str).str.strip().replace("", pd.NA).dropna().nunique()
                        )
                        ads_count = int(lvl_ads) if lvl_ads else lvl_rows
                    else:
                        ads_count = lvl_rows
                    level3_breakdown.append(
                        {
                            "level_3": level3,
                            "ads_count": ads_count,
                            "sheet_rows": lvl_rows,
                            "sheets_count": 1,
                        }
                    )

            sheet_unique_ads = len(sheet_ids) if sheet_ids else n
            peak_hour, peak_ads = _peak_from_hourly(sheet_hourly)
            subcategory_breakdown.append(
                {
                    "subcategory": str(sheet_name),
                    "ads_count": int(sheet_unique_ads),
                    "sheet_rows": int(n),
                    "sheets_count": 1,
                    "unique_phones": sheet_phone_counts["unique_phones"],
                    "valid_phones": sheet_phone_counts["valid_phones"],
                    "invalid_phones": sheet_phone_counts["invalid_phones"],
                    "outside_country_phones": sheet_phone_counts["outside_country_phones"],
                    "peak_hour": peak_hour,
                    "peak_ads": int(peak_ads),
                    "level_3_breakdown": level3_breakdown,
                }
            )

    if saw_id_column and all_ids:
        ads_source = "excel_ids"
        unique_ads = len(all_ids)
    elif total_rows > 0:
        ads_source = "excel_rows"
        unique_ads = total_rows
    else:
        ads_source = "none"
        unique_ads = 0

    scraper_peak_hour, scraper_peak_ads = _peak_from_hourly(scraper_hourly)
    hourly_ads = [
        {"hour": h, "ads_count": int(scraper_hourly[h])}
        for h in sorted(scraper_hourly.keys())
    ]
    phone_counts = _phone_bucket_counts(phone_buckets)
    return {
        "unique_ads": int(unique_ads),
        "total_rows": int(total_rows),
        "ads_source": ads_source,
        **phone_counts,
        "subcategory_breakdown": subcategory_breakdown,
        "hourly_ads": hourly_ads,
        "peak_hour": scraper_peak_hour,
        "peak_ads": int(scraper_peak_ads),
    }


def _extract_count_from_json(data: dict) -> int | None:
    for key in JSON_COUNT_KEYS:
        val = data.get(key)
        if isinstance(val, (int, float)) and val >= 0:
            return int(val)

    subcats = data.get("subcategories") or data.get("categories") or []
    if not isinstance(subcats, list) or not subcats:
        return None

    total = 0
    found = False
    for item in subcats:
        if not isinstance(item, dict):
            continue
        for key in ("listings_count", "count", "total"):
            val = item.get(key)
            if isinstance(val, (int, float)) and val >= 0:
                total += int(val)
                found = True
                break
    return total if found else None


def _list_json_keys(client, bucket: str, prefix: str) -> list[str]:
    keys: list[str] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.lower().endswith(".json"):
                keys.append(key)
    return keys


def _count_from_json_summaries(
    client,
    bucket: str,
    r2_base: str,
    partition_dt: datetime,
) -> int | None:
    partition = (
        f"year={partition_dt.year}/month={partition_dt.month:02d}/day={partition_dt.day:02d}"
    )
    prefixes = [
        f"{r2_base}/{partition}/json-files/",
        f"{r2_base}/{partition}/json files/",
    ]

    counts: list[int] = []
    for prefix in prefixes:
        for key in _list_json_keys(client, bucket, prefix):
            try:
                resp = client.get_object(Bucket=bucket, Key=key)
                data = json.loads(resp["Body"].read())
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            count = _extract_count_from_json(data)
            if count is not None:
                counts.append(count)

    if not counts:
        return None
    return sum(counts)


def count_scraper_ads(
    r2_client,
    bucket: str,
    r2_base: str,
    partition_dt: datetime,
    excel_downloads: list[tuple[str, bytes]],
    scraper_name: str | None = None,
) -> dict:
    """
    Count unique ads for one scraper partition.

    Priority: excel_ids → json_summary → excel_rows → none
    """
    excel_stats = _count_from_excel_files(excel_downloads)

    def _phone_fields(stats: dict[str, Any]) -> dict[str, int]:
        return {
            "unique_phones": int(stats.get("unique_phones") or 0),
            "valid_phones": int(stats.get("valid_phones") or 0),
            "invalid_phones": int(stats.get("invalid_phones") or 0),
            "outside_country_phones": int(stats.get("outside_country_phones") or 0),
        }

    def _finalize(stats: dict[str, Any], ads_source: str) -> dict[str, Any]:
        finalized = dict(stats)
        finalized["ads_source"] = ads_source
        phones = _phone_fields(finalized)
        finalized.update(phones)

        if not finalized.get("subcategory_breakdown") and (finalized.get("unique_ads") or 0) > 0:
            fallback_subcategory = f"{scraper_name} (all listings)" if scraper_name else "(all listings)"
            finalized["subcategory_breakdown"] = [
                {
                    "subcategory": fallback_subcategory,
                    "ads_count": int(finalized.get("unique_ads") or 0),
                    "sheet_rows": int(finalized.get("total_rows") or 0),
                    "sheets_count": 0,
                    "unique_phones": phones["unique_phones"],
                    "valid_phones": phones["valid_phones"],
                    "invalid_phones": phones["invalid_phones"],
                    "outside_country_phones": phones["outside_country_phones"],
                    "peak_hour": finalized.get("peak_hour"),
                    "peak_ads": int(finalized.get("peak_ads") or 0),
                    "level_3_breakdown": [],
                    "source": "fallback",
                }
            ]

        if not finalized.get("hourly_ads") and (finalized.get("unique_ads") or 0) > 0:
            # Preserve chart continuity when summaries exist but per-hour timestamps are unavailable.
            fallback_hour = 12
            fallback_ads = int(finalized.get("unique_ads") or 0)
            finalized["hourly_ads"] = [
                {"hour": fallback_hour, "ads_count": fallback_ads, "source": "fallback"}
            ]
            if finalized.get("peak_hour") is None:
                finalized["peak_hour"] = fallback_hour
            if int(finalized.get("peak_ads") or 0) <= 0:
                finalized["peak_ads"] = fallback_ads

        period_totals: dict[str, int] = {}
        for row in finalized.get("hourly_ads") or []:
            hour = row.get("hour")
            count = int(row.get("ads_count") or 0)
            if hour is None:
                continue
            period = _period_from_hour(int(hour))
            period_totals[period] = period_totals.get(period, 0) + count
        finalized["period_ads"] = [
            {"period": p, "ads_count": int(period_totals[p])}
            for p in sorted(period_totals.keys())
        ]

        # Compatibility aliases for downstream flatteners that still use legacy keys.
        finalized["ads_by_subcategory"] = finalized.get("subcategory_breakdown") or []
        finalized["ads_by_hour"] = finalized.get("hourly_ads") or []
        finalized["ads_by_period"] = finalized.get("period_ads") or []

        return finalized

    if excel_stats["ads_source"] == "excel_ids":
        return _finalize(
            {
                "unique_ads": excel_stats["unique_ads"],
                "total_rows": excel_stats["total_rows"],
                **_phone_fields(excel_stats),
                "subcategory_breakdown": excel_stats["subcategory_breakdown"],
                "hourly_ads": excel_stats["hourly_ads"],
                "peak_hour": excel_stats["peak_hour"],
                "peak_ads": excel_stats["peak_ads"],
            },
            "excel_ids",
        )

    json_count = _count_from_json_summaries(r2_client, bucket, r2_base, partition_dt)
    if json_count is not None:
        return _finalize(
            {
                "unique_ads": json_count,
                "total_rows": excel_stats["total_rows"] or json_count,
                **_phone_fields(excel_stats),
                "subcategory_breakdown": excel_stats["subcategory_breakdown"],
                "hourly_ads": excel_stats["hourly_ads"],
                "peak_hour": excel_stats["peak_hour"],
                "peak_ads": excel_stats["peak_ads"],
            },
            "json_summary",
        )

    if excel_stats["ads_source"] == "excel_rows":
        return _finalize(
            {
                "unique_ads": excel_stats["unique_ads"],
                "total_rows": excel_stats["total_rows"],
                **_phone_fields(excel_stats),
                "subcategory_breakdown": excel_stats["subcategory_breakdown"],
                "hourly_ads": excel_stats["hourly_ads"],
                "peak_hour": excel_stats["peak_hour"],
                "peak_ads": excel_stats["peak_ads"],
            },
            "excel_rows",
        )

    return _finalize(
        {
            "unique_ads": 0,
            "total_rows": 0,
            "unique_phones": 0,
            "valid_phones": 0,
            "invalid_phones": 0,
            "outside_country_phones": 0,
            "subcategory_breakdown": [],
            "hourly_ads": [],
            "peak_hour": None,
            "peak_ads": 0,
        },
        "none",
    )
