#!/usr/bin/env python3
"""
Delete Boshamlan images already stored in AWS S3 or Cloudflare R2.

Examples:
  # Delete ALL Boshamlan images (properties + offices)
  python scripts/delete_images.py --storage aws --mode all --execute --confirm-all

  # Preview images for one date (dry run is default)
  python scripts/delete_images.py --storage aws --mode list --date 2026-01-15

  # Delete all images for one date partition
  python scripts/delete_images.py --storage aws --mode partition --date 2026-01-15 --execute

  # Delete orphan images not referenced in Excel for that date
  python scripts/delete_images.py --storage aws --mode orphans --date 2026-01-15 --execute

  # Delete images older than 90 days
  python scripts/delete_images.py --storage aws --mode older-than --days 90 --execute
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Allow imports from scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent))

from image_deleter import ImageDeleter, date_partition
from storage_client import create_storage_client, get_bucket_name, verify_bucket_access


def parse_date(value: str):
    return datetime.strptime(value, "%Y-%m-%d").date()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Delete Boshamlan images from S3 or Cloudflare R2.",
    )
    parser.add_argument(
        "--storage",
        choices=["aws", "r2"],
        default="aws",
        help="Storage backend (default: aws)",
    )
    parser.add_argument(
        "--mode",
        choices=["all", "list", "partition", "orphans", "older-than"],
        default="all",
        help="Deletion mode (default: all images)",
    )
    parser.add_argument(
        "--dataset",
        choices=["properties", "offices", "both"],
        default="both",
        help="Which dataset to target (default: both)",
    )
    parser.add_argument(
        "--date",
        help="Target date YYYY-MM-DD (required for list/partition/orphans)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Retention days for older-than mode (default: 90)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete objects (default is dry run)",
    )
    parser.add_argument(
        "--confirm-all",
        action="store_true",
        help="Required safety flag when --mode all",
    )
    return parser


def datasets_from_arg(value: str) -> list[str]:
    if value == "both":
        return ["properties", "offices"]
    return [value]


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    dry_run = not args.execute
    datasets = datasets_from_arg(args.dataset)

    if args.mode in {"list", "partition", "orphans"} and not args.date:
        parser.error(f"--date is required for --mode {args.mode}")

    if args.mode == "all" and args.execute and not args.confirm_all:
        parser.error("--mode all with --execute requires --confirm-all")

    partition = date_partition(parse_date(args.date)) if args.date else None

    print("=" * 72)
    print("BOSHAMLAN IMAGE DELETION")
    print("=" * 72)
    print(f"Storage:   {args.storage.upper()}")
    print(f"Mode:      {args.mode}")
    print(f"Datasets:  {', '.join(datasets)}")
    if partition:
        print(f"Partition: {partition}")
    print(f"Dry run:   {dry_run}")
    print("=" * 72)

    client = create_storage_client(args.storage)
    bucket = get_bucket_name(args.storage)

    if not verify_bucket_access(client, bucket):
        return 1

    deleter = ImageDeleter(client, bucket, backend=args.storage)
    totals = {"requested": 0, "deleted": 0, "failed": 0}

    if args.mode == "list":
        for dataset in datasets:
            keys = deleter.list_images(dataset, partition)
            print(f"\n[{dataset}] {len(keys)} image(s) under {partition}")
            for key in keys[:20]:
                print(f"  - {deleter.scheme}://{bucket}/{key}")
            if len(keys) > 20:
                print(f"  ... and {len(keys) - 20} more")
        return 0

    if args.mode == "partition":
        for dataset in datasets:
            result = deleter.delete_partition_images(dataset, partition, dry_run=dry_run)
            totals["requested"] += result["requested"]
            totals["deleted"] += result["deleted"]
            totals["failed"] += result.get("failed", 0)

    elif args.mode == "orphans":
        for dataset in datasets:
            result = deleter.delete_orphan_images(dataset, partition, dry_run=dry_run)
            totals["requested"] += result["requested"]
            totals["deleted"] += result["deleted"]
            totals["failed"] += result.get("failed", 0)

    elif args.mode == "older-than":
        for dataset in datasets:
            result = deleter.delete_older_than(dataset, args.days, dry_run=dry_run)
            totals["requested"] += result["requested"]
            totals["deleted"] += result["deleted"]
            totals["failed"] += result.get("failed", 0)

    elif args.mode == "all":
        result = deleter.delete_all_images(datasets, dry_run=dry_run)
        totals = result

    print("\n" + "=" * 72)
    action = "Would delete" if dry_run else "Deleted"
    print(f"{action}: {totals['deleted']}/{totals['requested']} image(s)")
    if totals.get("failed"):
        print(f"Failed: {totals['failed']}")
    if dry_run:
        print("No objects were deleted. Re-run with --execute to apply changes.")
    print("=" * 72)

    return 1 if totals.get("failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
