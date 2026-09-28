#!/usr/bin/env python3
"""
Scan R2 Excel exports for a date and classify phone numbers as valid / invalid.

Usage:
    python -m validation.validate_phones --date 2026-08-15
    python -m validation.validate_phones --date 2026-08-15 --prefix boshamlan-data/
    python -m validation.validate_phones --date 2026-08-15 --show-invalid 50

Report is uploaded to R2 by default:
    {prefix}/validation/{date}/report.json
    e.g. boshamlan-data/validation/2026-08-15/report.json
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import boto3
import pandas as pd
from botocore.config import Config

from validation.phone_validator import find_phone_column, validate_phone

MAX_WORKERS = 8
MAX_RETRIES = 3
SKIP_SHEETS = frozenset({"info", "no data"})


class Color:
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    RESET = "\033[0m"


def log(message: str, color: str = Color.BLUE) -> None:
    now = time.strftime("%H:%M:%S")
    print(f"{color}[{now}] {message}{Color.RESET}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate phone numbers in R2 Excel exports"
    )
    parser.add_argument(
        "--date",
        required=True,
        help="Partition date YYYY-MM-DD",
    )
    parser.add_argument(
        "--prefix",
        default="boshamlan-data/",
        help="R2 key prefix to scan (default: boshamlan-data/)",
    )
    parser.add_argument(
        "--show-invalid",
        type=int,
        default=30,
        help="How many unique invalid samples to print (0 = none)",
    )
    parser.add_argument(
        "--show-outside",
        type=int,
        default=30,
        help="How many unique outside-country samples to print (0 = none)",
    )
    parser.add_argument(
        "--show-valid",
        type=int,
        default=0,
        help="How many unique valid samples to print (0 = none)",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional local path to also write the JSON report",
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Skip uploading the report to R2 under {prefix}/validation/{date}/",
    )
    parser.add_argument(
        "--fail-on-invalid",
        action="store_true",
        help="Exit with code 1 if any invalid phones are found",
    )
    return parser.parse_args()


def make_client():
    required = [
        "CF_R2_ACCESS_KEY_ID",
        "CF_R2_SECRET_ACCESS_KEY",
        "CF_R2_ENDPOINT_URL",
        "CF_R2_BUCKET_NAME",
    ]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"Missing environment variables: {', '.join(missing)}")
        sys.exit(1)

    return boto3.client(
        "s3",
        endpoint_url=os.environ["CF_R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["CF_R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["CF_R2_SECRET_ACCESS_KEY"],
        config=Config(
            retries={"max_attempts": 5},
            max_pool_connections=MAX_WORKERS,
        ),
    ), os.environ["CF_R2_BUCKET_NAME"]


def list_excel_files(client, bucket: str, prefix: str, year: str, month: str, day: str):
    partition = f"year={year}/month={month}/day={day}/"
    files: list[str] = []
    continuation = None

    log(f"Searching under {prefix} for {partition} ...")

    while True:
        kwargs: dict[str, Any] = {"Bucket": bucket, "Prefix": prefix}
        if continuation:
            kwargs["ContinuationToken"] = continuation

        response = client.list_objects_v2(**kwargs)
        for obj in response.get("Contents", []):
            key = obj["Key"]
            if partition not in key:
                continue
            if not key.lower().endswith((".xlsx", ".xls")):
                continue
            files.append(key)

        if response.get("IsTruncated"):
            continuation = response["NextContinuationToken"]
        else:
            break

    log(f"Found {len(files)} Excel files.", Color.GREEN)
    return files


def download_excel(client, bucket: str, key: str) -> io.BytesIO:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            obj = client.get_object(Bucket=bucket, Key=key)
            return io.BytesIO(obj["Body"].read())
        except Exception:
            if attempt == MAX_RETRIES:
                raise
            log(f"Retry {attempt}/{MAX_RETRIES}: {key}", Color.YELLOW)
            time.sleep(2)
    raise RuntimeError(f"Failed to download {key}")


def process_file(client, bucket: str, key: str) -> dict[str, Any]:
    result = {
        "key": key,
        "sheets": 0,
        "phone_cells": 0,
        "valid": 0,
        "invalid": 0,
        "outside_country": 0,
        "empty": 0,
        "valid_phones": set(),
        "invalid_phones": {},  # label -> reason
        "outside_country_phones": {},  # label -> reason
        "reason_counts": Counter(),
        "missing_phone_column": False,
        "error": None,
    }

    try:
        data = download_excel(client, bucket, key)
        sheets = pd.read_excel(data, sheet_name=None, dtype=object)
    except Exception as exc:
        result["error"] = str(exc)
        return result

    for sheet_name, df in sheets.items():
        if str(sheet_name).strip().lower() in SKIP_SHEETS:
            continue
        if df is None or df.empty:
            continue

        result["sheets"] += 1
        phone_col = find_phone_column(list(df.columns))
        if phone_col is None:
            result["missing_phone_column"] = True
            continue

        for value in df[phone_col].tolist():
            check = validate_phone(value)
            result["phone_cells"] += 1
            result["reason_counts"][check.reason] += 1
            label = check.normalized or check.raw or "(blank)"

            if check.category == "empty":
                result["empty"] += 1
                continue
            if check.category == "valid":
                result["valid"] += 1
                result["valid_phones"].add(label)
            elif check.category == "outside_country":
                result["outside_country"] += 1
                result["outside_country_phones"][label] = check.reason
            else:
                result["invalid"] += 1
                result["invalid_phones"][label] = check.reason

    return result


def merge_sets(target: set, values: set) -> None:
    target.update(values)


def print_summary(args: argparse.Namespace, overall: dict[str, Any]) -> None:
    print()
    print("=" * 70)
    print("PHONE VALIDATION SUMMARY")
    print("=" * 70)
    print(f"Date              : {args.date}")
    print(f"Prefix            : {args.prefix}")
    print()
    print("FILES")
    print("------------------------------")
    print(f"Files processed   : {overall['files']:,}")
    print(f"Sheets processed  : {overall['sheets']:,}")
    print(f"Download errors   : {overall['errors']:,}")
    print(f"No phone column   : {overall['missing_phone_column']:,}")
    print()
    print("PHONE CELLS")
    print("------------------------------")
    print(f"Total cells       : {overall['phone_cells']:,}")
    print(f"Valid (KW 965)    : {overall['valid']:,}")
    print(f"Invalid           : {overall['invalid']:,}")
    print(f"Outside country   : {overall['outside_country']:,}")
    print(f"Empty/missing     : {overall['empty']:,}")
    print()
    print("UNIQUE NUMBERS")
    print("------------------------------")
    print(f"valid_phones      : {len(overall['valid_phones']):,}")
    print(f"invalid_phones    : {len(overall['invalid_phones']):,}")
    print(f"outside_country   : {len(overall['outside_country_phones']):,}")
    print()

    if overall["reason_counts"]:
        print("REASONS")
        print("------------------------------")
        for reason, count in overall["reason_counts"].most_common():
            print(f"  {count:>8,}  {reason}")
        print()

    if args.show_valid > 0 and overall["valid_phones"]:
        print(f"VALID SAMPLES (up to {args.show_valid})")
        print("------------------------------")
        for phone in sorted(overall["valid_phones"])[: args.show_valid]:
            print(f"  {phone}")
        print()

    if args.show_invalid > 0 and overall["invalid_phones"]:
        print(f"INVALID SAMPLES (up to {args.show_invalid})")
        print("------------------------------")
        items = sorted(overall["invalid_phones"].items(), key=lambda x: x[0])
        for phone, reason in items[: args.show_invalid]:
            print(f"  {phone!r:40}  {reason}")
        print()

    if args.show_outside > 0 and overall["outside_country_phones"]:
        print(f"OUTSIDE-COUNTRY SAMPLES (up to {args.show_outside})")
        print("------------------------------")
        items = sorted(overall["outside_country_phones"].items(), key=lambda x: x[0])
        for phone, reason in items[: args.show_outside]:
            print(f"  {phone!r:40}  {reason}")
        print()

    print("=" * 70)


def build_report(args: argparse.Namespace, overall: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": args.date,
        "prefix": args.prefix,
        "files": overall["files"],
        "sheets": overall["sheets"],
        "errors": overall["errors"],
        "missing_phone_column": overall["missing_phone_column"],
        "phone_cells": overall["phone_cells"],
        "valid_phones": len(overall["valid_phones"]),
        "invalid_phones": len(overall["invalid_phones"]),
        "outside_country_phones": len(overall["outside_country_phones"]),
        "empty_cells": overall["empty"],
        "unique_valid": sorted(overall["valid_phones"]),
        "unique_invalid": [
            {"phone": phone, "reason": reason}
            for phone, reason in sorted(overall["invalid_phones"].items())
        ],
        "unique_outside_country": [
            {"phone": phone, "reason": reason}
            for phone, reason in sorted(overall["outside_country_phones"].items())
        ],
        "reason_counts": dict(overall["reason_counts"]),
    }


def write_local_report(path: str, payload: dict[str, Any]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"Wrote local report: {out}", Color.GREEN)


def upload_report_to_r2(
    client,
    bucket: str,
    prefix: str,
    date: str,
    payload: dict[str, Any],
) -> str:
    """Upload report to {prefix}/validation/{date}/report.json."""
    base = prefix.strip("/")
    key = f"{base}/validation/{date}/report.json"
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType="application/json",
    )
    log(f"Report uploaded → r2://{bucket}/{key}", Color.GREEN)
    return key


def save_reports(
    args: argparse.Namespace,
    overall: dict[str, Any],
    client,
    bucket: str,
) -> None:
    payload = build_report(args, overall)
    if not args.no_upload:
        upload_report_to_r2(client, bucket, args.prefix, args.date, payload)
    if args.output:
        write_local_report(args.output, payload)


def main() -> int:
    args = parse_args()
    try:
        year, month, day = args.date.split("-")
    except ValueError:
        print("Date must be YYYY-MM-DD")
        return 1

    client, bucket = make_client()
    files = list_excel_files(client, bucket, args.prefix.rstrip("/") + "/", year, month, day)

    overall: dict[str, Any] = {
        "files": 0,
        "sheets": 0,
        "errors": 0,
        "missing_phone_column": 0,
        "phone_cells": 0,
        "valid": 0,
        "invalid": 0,
        "outside_country": 0,
        "empty": 0,
        "valid_phones": set(),
        "invalid_phones": {},
        "outside_country_phones": {},
        "reason_counts": Counter(),
    }

    if not files:
        log("No Excel files found for that date.", Color.YELLOW)
        print_summary(args, overall)
        save_reports(args, overall, client, bucket)
        return 1 if args.fail_on_invalid else 0

    start = time.time()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_file, client, bucket, key): key for key in files
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                log(f"Worker crashed on {key}: {exc}", Color.RED)
                overall["errors"] += 1
                continue

            overall["files"] += 1
            overall["sheets"] += result["sheets"]
            overall["phone_cells"] += result["phone_cells"]
            overall["valid"] += result["valid"]
            overall["invalid"] += result["invalid"]
            overall["outside_country"] += result["outside_country"]
            overall["empty"] += result["empty"]
            overall["reason_counts"].update(result["reason_counts"])
            merge_sets(overall["valid_phones"], result["valid_phones"])
            overall["invalid_phones"].update(result["invalid_phones"])
            overall["outside_country_phones"].update(result["outside_country_phones"])

            if result["error"]:
                overall["errors"] += 1
                log(f"Error {key}: {result['error']}", Color.RED)
            if result["missing_phone_column"]:
                overall["missing_phone_column"] += 1

            bad = result["invalid"] + result["outside_country"]
            status = Color.GREEN if bad == 0 and not result["error"] else Color.YELLOW
            log(
                f"{key} | cells={result['phone_cells']} "
                f"valid={result['valid']} invalid={result['invalid']} "
                f"outside={result['outside_country']}",
                status,
            )

    log(f"Finished in {time.time() - start:.2f}s", Color.GREEN)
    print_summary(args, overall)
    save_reports(args, overall, client, bucket)

    if args.fail_on_invalid and overall["invalid"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
