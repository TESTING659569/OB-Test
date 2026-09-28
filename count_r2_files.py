import os
import boto3
import argparse
from botocore.config import Config

BUCKET = os.environ["CF_R2_BUCKET_NAME"]
ENDPOINT = os.environ["CF_R2_ENDPOINT_URL"]

client = boto3.client(
    "s3",
    endpoint_url=ENDPOINT,
    aws_access_key_id=os.environ["CF_R2_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["CF_R2_SECRET_ACCESS_KEY"],
    config=Config(signature_version="s3v4"),
    region_name="auto",
)


def count_files(prefix):
    paginator = client.get_paginator("list_objects_v2")
    total = 0

    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        total += len(page.get("Contents", []))

    # Ignore folder marker if present
    if total > 0:
        total -= 1

    return total


parser = argparse.ArgumentParser()
parser.add_argument(
    "--folder",
    help="Folder/prefix to count (e.g. 4sale-data or 4sale-data/)",
)
args = parser.parse_args()

if args.folder:
    prefix = args.folder.rstrip("/") + "/"
    total = count_files(prefix)

    print(f"\nFolder: {prefix}")
    print(f"Total files: {total:,}")
else:
    response = client.list_objects_v2(
        Bucket=BUCKET,
        Delimiter="/",
    )

    folders = [p["Prefix"] for p in response.get("CommonPrefixes", [])]

    grand_total = 0

    print(f"{'Folder':40} {'Files':>12}")
    print("-" * 55)

    for folder in folders:
        total = count_files(folder)
        grand_total += total
        print(f"{folder:40} {total:12,}")

    print("-" * 55)
    print(f"{'TOTAL':40} {grand_total:12,}")