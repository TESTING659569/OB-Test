#!/usr/bin/env python3

import io
import os
import sys
import time
import argparse
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
import pandas as pd
from botocore.config import Config
from botocore.exceptions import ClientError

# ==========================================================
# Configuration
# ==========================================================

MAX_WORKERS = 8
MAX_RETRIES = 3

# ==========================================================
# Colors
# ==========================================================

class Color:
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    RESET = "\033[0m"

def log(message, color=Color.BLUE):
    now = time.strftime("%H:%M:%S")
    print(f"{color}[{now}] {message}{Color.RESET}", flush=True)

# ==========================================================
# Arguments
# ==========================================================

parser = argparse.ArgumentParser()

parser.add_argument(
    "--date",
    required=True,
    help="Date format YYYY-MM-DD"
)

args = parser.parse_args()

try:
    YEAR, MONTH, DAY = args.date.split("-")
except Exception:
    print("Date must be YYYY-MM-DD")
    sys.exit(1)

# ==========================================================
# Environment Variables
# ==========================================================

ACCESS_KEY = os.environ["CF_R2_ACCESS_KEY_ID"]
SECRET_KEY = os.environ["CF_R2_SECRET_ACCESS_KEY"]
ENDPOINT = os.environ["CF_R2_ENDPOINT_URL"]
BUCKET = os.environ["CF_R2_BUCKET_NAME"]

# ==========================================================
# Connect to Cloudflare R2
# ==========================================================

log("Connecting to Cloudflare R2...")

client = boto3.client(
    "s3",
    endpoint_url=ENDPOINT,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    config=Config(
        retries={"max_attempts": 5},
        max_pool_connections=MAX_WORKERS
    )
)

log("Connected.", Color.GREEN)

# ==========================================================
# Statistics
# ==========================================================

stats_lock = threading.Lock()

overall = {
    "files": 0,
    "sheets": 0,
    "total_ads": 0,
    "total_phones": 0,
    "ids": set(),
    "phones": set()
}

categories = defaultdict(
    lambda: {
        "files": 0,
        "sheets": 0,
        "total_ads": 0,
        "total_phones": 0,
        "ids": set(),
        "phones": set()
    }
)

# ==========================================================
# List all excel files
# ==========================================================

def list_excel_files():

    prefix = "4sale-data/"

    continuation = None

    files = []

    log(f"Searching for files for {args.date} ...")

    while True:

        kwargs = {
            "Bucket": BUCKET,
            "Prefix": prefix
        }

        if continuation:
            kwargs["ContinuationToken"] = continuation

        response = client.list_objects_v2(**kwargs)

        for obj in response.get("Contents", []):

            key = obj["Key"]

            if (
                f"year={YEAR}/month={MONTH}/day={DAY}/"
                not in key
            ):
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

# ==========================================================
# Download with retries
# ==========================================================

def download_excel(key):

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            obj = client.get_object(
                Bucket=BUCKET,
                Key=key
            )

            return io.BytesIO(obj["Body"].read())

        except Exception as e:

            if attempt == MAX_RETRIES:
                raise

            log(
                f"Retry {attempt}/{MAX_RETRIES}: {key}",
                Color.YELLOW
            )

            time.sleep(2)

# ==========================================================
# Progress
# ==========================================================

processed_files = 0
processed_lock = threading.Lock()

def print_progress(total):

    with processed_lock:

        global processed_files

        processed_files += 1

        print()

        log(
            f"Completed {processed_files}/{total} files",
            Color.GREEN
        )

        print("------------------------------------------")

        print(f"Files           : {overall['files']}")
        print(f"Sheets          : {overall['sheets']}")

        print()

        print(f"Total Ads       : {overall['total_ads']:,}")
        print(f"Unique Ads      : {len(overall['ids']):,}")

        print()

        print(f"Total Phones    : {overall['total_phones']:,}")
        print(f"Unique Phones   : {len(overall['phones']):,}")

        print("------------------------------------------")

# ==========================================================
# Process one excel file
# ==========================================================

def process_excel(key, total_files):

    category = key.split("/")[1]

    log(f"Processing {key}", Color.CYAN)

    try:

        data = download_excel(key)

    except Exception as e:

        log(f"Download failed: {e}", Color.RED)

        return

    try:

        excel = pd.ExcelFile(data)

    except Exception as e:

        log(f"Invalid Excel: {key}", Color.RED)

        return

    local_ids = set()
    local_phones = set()

    local_total_ads = 0
    local_total_phones = 0
    local_sheets = 0

    # ======================================================
    # Process every sheet
    # ======================================================

    for sheet in excel.sheet_names:

        local_sheets += 1

        log(
            f"   Reading sheet: {sheet}",
            Color.BLUE
        )

        try:

            df = pd.read_excel(
                excel,
                sheet_name=sheet
            )

        except Exception as e:

            log(
                f"   Cannot read sheet {sheet}: {e}",
                Color.YELLOW
            )

            continue

        if df.empty:
            log(
                "   Sheet is empty.",
                Color.YELLOW
            )
            continue

        # Normalize column names
        columns = {
            str(c).strip().lower(): c
            for c in df.columns
        }

        id_aliases = [
            "id",
            "ad_id",
            "ads_id",
            "listing_id",
            "listingid"
            ]


        phone_aliases = [
            "phone",
            "phones",
            "mobile",
            "mobile_number",
            "phone_number",
            "contact_number",
            "contact_numbers",
            "telephone",
            "tel"
            ]


        id_column = None
        phone_column = None


        for alias in id_aliases:
            if alias in columns:
                id_column = columns[alias]
                break


        for alias in phone_aliases:
            if alias in columns:
                phone_column = columns[alias]
                break



        if id_column is None:

            log(
                "   Missing ID column.",
                Color.YELLOW
            )

            continue



        if phone_column is None:

            log(
                "   Missing phone column.",
                Color.YELLOW
            )

            continue



        log(
            f"   ID column detected: {id_column}",
            Color.CYAN
            )


        log(
            f"   Phone column detected: {phone_column}",
            Color.CYAN
            )

        # Remove nulls
        ids = (
            df[id_column]
            .dropna()
            .astype(str)
            .str.strip()
        )

        phones = (
            df[phone_column]
            .dropna()
            .astype(str)
            .str.strip()
        )

        ids = ids[ids != ""]
        phones = phones[phones != ""]

        local_total_ads += len(ids)
        local_total_phones += len(phones)

        local_ids.update(ids.tolist())
        local_phones.update(phones.tolist())

        log(
            f"      Rows           : {len(df):,}",
            Color.GREEN
        )

        log(
            f"      IDs            : {len(ids):,}",
            Color.GREEN
        )

        log(
            f"      Phones         : {len(phones):,}",
            Color.GREEN
        )

    # ======================================================
    # Update global statistics
    # ======================================================

    with stats_lock:

        overall["files"] += 1
        overall["sheets"] += local_sheets

        overall["total_ads"] += local_total_ads
        overall["total_phones"] += local_total_phones

        overall["ids"].update(local_ids)
        overall["phones"].update(local_phones)

        categories[category]["files"] += 1
        categories[category]["sheets"] += local_sheets

        categories[category]["total_ads"] += local_total_ads
        categories[category]["total_phones"] += local_total_phones

        categories[category]["ids"].update(local_ids)
        categories[category]["phones"].update(local_phones)

    print_progress(total_files)

# ==========================================================
# Run all files using threads
# ==========================================================

def run():

    files = list_excel_files()

    if not files:

        log(
            "No Excel files found.",
            Color.RED
        )

        return

    total_files = len(files)

    log(
        f"Starting {MAX_WORKERS} worker threads...",
        Color.GREEN
    )

    start = time.time()

    futures = []

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        for key in files:

            futures.append(

                executor.submit(
                    process_excel,
                    key,
                    total_files
                )

            )

        for future in as_completed(futures):

            try:

                future.result()

            except Exception as e:

                log(
                    f"Worker crashed: {e}",
                    Color.RED
                )

    elapsed = time.time() - start

    log(
        f"Finished in {elapsed:.2f} seconds.",
        Color.GREEN
    )

# ==========================================================
# ==========================================================
# Final Summary
# ==========================================================

def print_summary():

    print()

    print("=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)

    print()

    print(f"Date              : {args.date}")

    print()

    print("FILES")
    print("------------------------------")
    print(f"Files processed   : {overall['files']:,}")
    print(f"Sheets processed  : {overall['sheets']:,}")

    print()

    print("ADS")
    print("------------------------------")
    print(f"Total Ads         : {overall['total_ads']:,}")
    print(f"Unique Ads        : {len(overall['ids']):,}")

    print()

    print("PHONES")
    print("------------------------------")
    print(f"Total Phones      : {overall['total_phones']:,}")
    print(f"Unique Phones     : {len(overall['phones']):,}")

    print()

    print("=" * 70)
    print("PER CATEGORY")
    print("=" * 70)


    for category in sorted(categories.keys()):

        data = categories[category]

        print()

        print(category)
        print("-" * len(category))

        print(
            f"Files             : {data['files']:,}"
        )

        print(
            f"Sheets            : {data['sheets']:,}"
        )

        print(
            f"Total Ads         : {data['total_ads']:,}"
        )

        print(
            f"Unique Ads        : {len(data['ids']):,}"
        )

        print(
            f"Total Phones      : {data['total_phones']:,}"
        )

        print(
            f"Unique Phones     : {len(data['phones']):,}"
        )


    print()

    print("=" * 70)

    print("DONE")
    print("=" * 70)


# ==========================================================
# Main Entry Point
# ==========================================================

if __name__ == "__main__":

    try:

        log(
            "Starting R2 Excel Counter",
            Color.CYAN
        )

        print()

        run()

        print_summary()


    except KeyboardInterrupt:

        print()

        log(
            "Stopped by user.",
            Color.RED
        )

        sys.exit(1)


    except Exception as e:

        print()

        log(
            f"Fatal error: {e}",
            Color.RED
        )

        sys.exit(1)