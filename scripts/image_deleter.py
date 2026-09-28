"""Delete Boshamlan images from S3 or Cloudflare R2."""

from __future__ import annotations

import io
import re
from datetime import date, datetime, timedelta
from typing import Iterable
from urllib.parse import urlparse

import pandas as pd
from botocore.exceptions import ClientError

from storage_client import StorageBackend

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".svg"}
_EXCEL_FOLDERS = ("excel files", "excel-files")

# Excel columns that store uploaded image URIs.
_IMAGE_PATH_COLUMNS = (
    "image_s3_path",
    "image_r2_path",
    "S3 Image Path",
    "s3_image_url",
    "R2 Image Path",
    "r2_image_url",
)

_DATASETS = {
    "properties": "boshamlan-data/properties",
    "offices": "boshamlan-data/offices",
}


def date_partition(partition_dt: date | datetime) -> str:
    if isinstance(partition_dt, datetime):
        partition_dt = partition_dt.date()
    return f"year={partition_dt.year}/month={partition_dt.month:02d}/day={partition_dt.day:02d}"


def uri_to_key(uri: str, bucket: str) -> str | None:
    """Convert s3:// or r2:// URI to object key."""
    if not uri or not isinstance(uri, str):
        return None
    uri = uri.strip()
    if uri.startswith("s3://") or uri.startswith("r2://"):
        parsed = urlparse(uri)
        if parsed.netloc and parsed.netloc != bucket:
            return None
        key = parsed.path.lstrip("/")
        return key or None
    return None


def is_image_key(key: str) -> bool:
    key_lower = key.lower()
    return any(key_lower.endswith(ext) for ext in _IMAGE_EXTS)


def list_objects(client, bucket: str, prefix: str) -> list[dict]:
    objects: list[dict] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj.get("Key", "")
            if key and not key.endswith("/"):
                objects.append({"Key": key, "Size": int(obj.get("Size", 0))})
    return objects


def list_image_keys(client, bucket: str, prefix: str) -> list[str]:
    return [obj["Key"] for obj in list_objects(client, bucket, prefix) if is_image_key(obj["Key"])]


def list_date_partitions(client, bucket: str, base_path: str) -> list[str]:
    """Return sorted date partition strings under a dataset base path."""
    prefix = f"{base_path.rstrip('/')}/"
    partitions: set[str] = set()
    pattern = re.compile(r"year=(\d{4})/month=(\d{2})/day=(\d{2})")

    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj.get("Key", "")
            match = pattern.search(key)
            if match:
                partitions.add(match.group(0))

    return sorted(partitions)


def partition_to_date(partition: str) -> date | None:
    match = re.match(r"year=(\d{4})/month=(\d{2})/day=(\d{2})", partition)
    if not match:
        return None
    year, month, day = map(int, match.groups())
    return date(year, month, day)


def download_excel_keys(client, bucket: str, prefix: str) -> list[str]:
    """List Excel object keys under a prefix."""
    keys = []
    for obj in list_objects(client, bucket, prefix):
        key = obj["Key"]
        key_lower = key.lower()
        if any(f"/{folder}/" in key_lower for folder in _EXCEL_FOLDERS):
            if key_lower.endswith((".xlsx", ".xls", ".xlsm")):
                keys.append(key)
    return keys


def read_excel_from_s3(client, bucket: str, key: str) -> dict[str, pd.DataFrame]:
    response = client.get_object(Bucket=bucket, Key=key)
    data = response["Body"].read()
    excel_file = pd.ExcelFile(io.BytesIO(data))
    return {sheet: excel_file.parse(sheet) for sheet in excel_file.sheet_names}


def extract_referenced_image_keys(
    client,
    bucket: str,
    base_path: str,
    partition: str,
) -> set[str]:
    """Collect image keys referenced in Excel files for one date partition."""
    prefix = f"{base_path.rstrip('/')}/{partition}/"
    referenced: set[str] = set()

    for excel_key in download_excel_keys(client, bucket, prefix):
        try:
            sheets = read_excel_from_s3(client, bucket, excel_key)
        except Exception as exc:
            print(f"  WARNING: Could not read {excel_key}: {exc}")
            continue

        for sheet_name, df in sheets.items():
            for col in _IMAGE_PATH_COLUMNS:
                if col not in df.columns:
                    continue
                for value in df[col].dropna().astype(str):
                    key = uri_to_key(value, bucket)
                    if key:
                        referenced.add(key)

    return referenced


def _delete_one(client, bucket: str, key: str) -> None:
    client.delete_object(Bucket=bucket, Key=key)


def delete_objects_batch(
    client,
    bucket: str,
    keys: Iterable[str],
    dry_run: bool = True,
) -> dict[str, int]:
    keys = list(keys)
    if not keys:
        return {"requested": 0, "deleted": 0, "failed": 0}

    deleted = 0
    failed = 0
    batch_size = 1000

    for start in range(0, len(keys), batch_size):
        batch = keys[start : start + batch_size]
        if dry_run:
            deleted += len(batch)
            continue

        remaining = list(batch)
        try:
            # Quiet=False is required: R2/S3 omit the Deleted list in quiet mode,
            # which made this script report 0/N even when objects were removed.
            response = client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": [{"Key": key} for key in batch], "Quiet": False},
            )
            deleted_keys = {
                item["Key"] for item in response.get("Deleted", []) if item.get("Key")
            }
            errors = response.get("Errors") or []
            error_keys = {err.get("Key") for err in errors if err.get("Key")}
            for err in errors:
                print(
                    f"  ERROR deleting {err.get('Key')}: "
                    f"{err.get('Code')} {err.get('Message')}"
                )
            deleted += len(deleted_keys)
            failed += len(errors)
            remaining = [
                key for key in batch if key not in deleted_keys and key not in error_keys
            ]
            if remaining:
                print(
                    f"  Batch API did not confirm {len(remaining)} object(s); "
                    "retrying individually..."
                )
        except ClientError as exc:
            print(f"  ERROR batch delete failed: {exc}")
            print("  Retrying this batch with individual deletes...")

        for key in remaining:
            try:
                _delete_one(client, bucket, key)
                deleted += 1
            except ClientError as exc:
                error = exc.response.get("Error", {})
                print(
                    f"  ERROR deleting {key}: "
                    f"{error.get('Code', '')} {error.get('Message', exc)}"
                )
                failed += 1

    return {"requested": len(keys), "deleted": deleted, "failed": failed}


class ImageDeleter:
    def __init__(self, client, bucket: str, backend: StorageBackend = "aws"):
        self.client = client
        self.bucket = bucket
        self.backend = backend
        self.scheme = "r2" if backend == "r2" else "s3"

    def images_prefix(self, dataset: str, partition: str) -> str:
        base = _DATASETS[dataset]
        return f"{base}/{partition}/images/"

    def list_images(self, dataset: str, partition: str) -> list[str]:
        prefix = self.images_prefix(dataset, partition)
        return list_image_keys(self.client, self.bucket, prefix)

    def delete_partition_images(
        self,
        dataset: str,
        partition: str,
        dry_run: bool = True,
    ) -> dict:
        keys = self.list_images(dataset, partition)
        print(f"\n[{dataset}] {partition}: found {len(keys)} image(s)")
        if keys[:5]:
            for key in keys[:5]:
                print(f"  - {self.scheme}://{self.bucket}/{key}")
            if len(keys) > 5:
                print(f"  ... and {len(keys) - 5} more")

        result = delete_objects_batch(self.client, self.bucket, keys, dry_run=dry_run)
        if not dry_run:
            remaining = self.list_images(dataset, partition)
            result["remaining"] = len(remaining)
            result["deleted"] = max(0, result["requested"] - len(remaining))
            if remaining:
                result["failed"] = len(remaining)
                print(f"  WARNING: {len(remaining)} image(s) still present after delete")
        action = "Would delete" if dry_run else "Deleted"
        print(f"  {action}: {result['deleted']}/{result['requested']}")
        return result

    def delete_orphan_images(
        self,
        dataset: str,
        partition: str,
        dry_run: bool = True,
    ) -> dict:
        base_path = _DATASETS[dataset]
        prefix = self.images_prefix(dataset, partition)
        all_keys = set(list_image_keys(self.client, self.bucket, prefix))
        referenced = extract_referenced_image_keys(
            self.client, self.bucket, base_path, partition
        )
        orphans = sorted(all_keys - referenced)

        print(f"\n[{dataset}] {partition} orphan cleanup:")
        print(f"  Images in storage: {len(all_keys)}")
        print(f"  Referenced in Excel: {len(referenced)}")
        print(f"  Orphans to remove: {len(orphans)}")

        result = delete_objects_batch(self.client, self.bucket, orphans, dry_run=dry_run)
        action = "Would delete" if dry_run else "Deleted"
        print(f"  {action}: {result['deleted']}/{result['requested']}")
        return result

    def delete_older_than(
        self,
        dataset: str,
        days: int,
        dry_run: bool = True,
    ) -> dict:
        base_path = _DATASETS[dataset]
        cutoff = date.today() - timedelta(days=days)
        partitions = list_date_partitions(self.client, self.bucket, base_path)

        totals = {"requested": 0, "deleted": 0, "failed": 0, "partitions": 0}
        print(f"\n[{dataset}] Deleting images older than {days} day(s) (before {cutoff})")

        for partition in partitions:
            partition_date = partition_to_date(partition)
            if partition_date is None or partition_date >= cutoff:
                continue

            result = self.delete_partition_images(dataset, partition, dry_run=dry_run)
            totals["requested"] += result["requested"]
            totals["deleted"] += result["deleted"]
            totals["failed"] += result["failed"]
            totals["partitions"] += 1

        print(
            f"\n[{dataset}] Summary: {totals['partitions']} partition(s), "
            f"{totals['deleted']}/{totals['requested']} image(s)"
        )
        return totals

    def delete_all_images(
        self,
        datasets: list[str],
        dry_run: bool = True,
    ) -> dict:
        """Delete every Boshamlan image under properties and/or offices."""
        totals = {"requested": 0, "deleted": 0, "failed": 0}

        for dataset in datasets:
            base_path = _DATASETS[dataset]
            partitions = list_date_partitions(self.client, self.bucket, base_path)
            print(f"\n[{dataset}] Found {len(partitions)} date partition(s)")

            for partition in partitions:
                result = self.delete_partition_images(dataset, partition, dry_run=dry_run)
                totals["requested"] += result["requested"]
                totals["deleted"] += result["deleted"]
                totals["failed"] += result["failed"]

        print(
            f"\nTotal: {totals['deleted']}/{totals['requested']} image(s) "
            f"({'dry run' if dry_run else 'deleted'})"
        )
        return totals
