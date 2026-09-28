"""
Local multi-time ad count runner for CFl_data scrapers.

Scrapes properties + offices without uploading to Cloudflare R2.
Saves only local summaries so you can compare how many ads appear
at different times of day.

Examples (PowerShell, from repo root):

  # Run once now
  python CFl_data/local_multi_count.py

  # Schedule several runs today (waits until each time)
  python CFl_data/local_multi_count.py --times 00:00,06:00,12:00,18:00

  # Properties only / offices only
  python CFl_data/local_multi_count.py --only properties
  python CFl_data/local_multi_count.py --only offices

  # Print comparison table from previous runs
  python CFl_data/local_multi_count.py --compare
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
CFL = Path(__file__).resolve().parent
PROPERTIES_DIR = CFL / "properties"
OFFICES_DIR = CFL / "offices"
OUTPUT_DIR = CFL / "local_counts"
HISTORY_FILE = OUTPUT_DIR / "runs_history.json"
# Repo-root files used by the GitHub Actions workflow (committed for comparison)
CI_LATEST_FILE = ROOT / "count_times_latest.json"
CI_HISTORY_FILE = ROOT / "count_times_history.json"

# Ensure imports resolve the same way as the existing mains
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(CFL))
sys.path.insert(0, str(PROPERTIES_DIR))
sys.path.insert(0, str(OFFICES_DIR))


def _now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _load_history() -> List[Dict[str, Any]]:
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_history(history: List[Dict[str, Any]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def _save_run_snapshot(summary: Dict[str, Any]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"run_{stamp}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return path


async def scrape_properties() -> Dict[str, Any]:
    from CategoryScraper import CategoryScraper

    scraper = CategoryScraper()
    # Keep category Excel/JSON under local_counts, not CFl_data/properties/scraped_data
    scrape_dir = OUTPUT_DIR / "properties" / datetime.now().strftime("%Y%m%d_%H%M%S")
    scrape_dir.mkdir(parents=True, exist_ok=True)
    scraper.output_dir = str(scrape_dir)

    started = datetime.now()
    await scraper.scrape_all_categories()
    elapsed = max(1, int((datetime.now() - started).total_seconds()))

    by_category: Dict[str, Any] = {}
    total_ads = 0
    for category_name, category_data in (scraper.last_scraped_data or {}).items():
        subcats = {}
        cat_total = 0
        for subcat_name, items in (category_data or {}).items():
            count = len(items) if items else 0
            subcats[subcat_name] = count
            cat_total += count
        by_category[category_name] = {"total_ads": cat_total, "subcategories": subcats}
        total_ads += cat_total

    return {
        "success": True,
        "total_ads": total_ads,
        "by_category": by_category,
        "duration_sec": elapsed,
        "local_dir": str(scrape_dir),
        "request_metrics": scraper.get_request_metrics(),
    }


async def scrape_offices() -> Dict[str, Any]:
    from OfficeScraper import OfficeScraper

    scraper = OfficeScraper()
    started = datetime.now()
    offices = await scraper.scrape_all_offices()
    elapsed = max(1, int((datetime.now() - started).total_seconds()))

    offices = offices or []
    # Date-filtered listings (yesterday onwards) — same metric as pipeline summary
    filtered_listings = sum(len(o.get("listings") or []) for o in offices)
    # Site-reported total ads across offices (ads_number / numberOfItems)
    site_ads_total = sum(int(o.get("ads_number") or 0) for o in offices)

    per_office = [
        {
            "name": o.get("name", "Unknown"),
            "ads_number": int(o.get("ads_number") or 0),
            "filtered_listings": len(o.get("listings") or []),
            "url": o.get("url", ""),
        }
        for o in offices
    ]

    return {
        "success": True,
        "offices_count": len(offices),
        "filtered_listings": filtered_listings,
        "site_ads_total": site_ads_total,
        "per_office": per_office,
        "duration_sec": elapsed,
        "request_metrics": scraper.get_request_metrics(),
    }


async def run_once(only: str = "all", ci: bool = False) -> Dict[str, Any]:
    print("\n" + "=" * 80)
    print(f"LOCAL COUNT RUN (no Cloudflare) — {_now_stamp()}")
    print("=" * 80)

    summary: Dict[str, Any] = {
        "scraped_at": datetime.now().isoformat(timespec="seconds"),
        "scraped_at_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "local_only": True,
        "upload_to_cloudflare": False,
        "properties": None,
        "offices": None,
    }

    if only in ("all", "properties"):
        print("\n>>> Scraping PROPERTIES (local only)...")
        try:
            summary["properties"] = await scrape_properties()
        except Exception as e:
            summary["properties"] = {"success": False, "error": f"{type(e).__name__}: {e}"}
            print(f"Properties scrape failed: {e}")

    if only in ("all", "offices"):
        print("\n>>> Scraping OFFICES (local only)...")
        try:
            summary["offices"] = await scrape_offices()
        except Exception as e:
            summary["offices"] = {"success": False, "error": f"{type(e).__name__}: {e}"}
            print(f"Offices scrape failed: {e}")

    _print_summary(summary)

    snapshot = _save_run_snapshot(summary)
    history_row = {
        "scraped_at": summary["scraped_at"],
        "scraped_at_utc": summary.get("scraped_at_utc"),
        "properties_ads": (summary.get("properties") or {}).get("total_ads"),
        "offices_filtered_listings": (summary.get("offices") or {}).get("filtered_listings"),
        "offices_site_ads_total": (summary.get("offices") or {}).get("site_ads_total"),
        "offices_count": (summary.get("offices") or {}).get("offices_count"),
        "snapshot": str(snapshot),
    }
    if ci:
        history_row["run_id"] = os.environ.get("GITHUB_RUN_ID")
        history_row["run_number"] = os.environ.get("GITHUB_RUN_NUMBER")
        history_row["workflow"] = os.environ.get("GITHUB_WORKFLOW")

    history = _load_history()
    history.append(history_row)
    _save_history(history)

    if ci:
        _save_ci_outputs(summary, history_row)
        _write_github_step_summary(summary, history)

    print(f"\nSaved snapshot: {snapshot}")
    print(f"History file:   {HISTORY_FILE}")
    return summary


def _print_summary(summary: Dict[str, Any]) -> None:
    print("\n" + "=" * 80)
    print("AD COUNT SUMMARY")
    print("=" * 80)
    print(f"Time: {summary.get('scraped_at')}")
    print("Cloudflare upload: NO (local only)")

    props = summary.get("properties") or {}
    if props:
        if props.get("success"):
            print(f"\nProperties ads (yesterday+today filter): {props.get('total_ads', 0)}")
            for cat, info in (props.get("by_category") or {}).items():
                print(f"  - {cat}: {info.get('total_ads', 0)}")
                for sub, n in (info.get("subcategories") or {}).items():
                    if n:
                        print(f"      {sub}: {n}")
        else:
            print(f"\nProperties: FAILED — {props.get('error')}")

    offices = summary.get("offices") or {}
    if offices:
        if offices.get("success"):
            print(f"\nOffices count: {offices.get('offices_count', 0)}")
            print(f"Offices filtered listings (yesterday+today): {offices.get('filtered_listings', 0)}")
            print(f"Offices site ads_number sum (all live ads): {offices.get('site_ads_total', 0)}")
        else:
            print(f"\nOffices: FAILED — {offices.get('error')}")

    print("=" * 80)


def _compact_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Drop bulky per-office lists for the committed latest file."""
    out = {
        "scraped_at": summary.get("scraped_at"),
        "scraped_at_utc": summary.get("scraped_at_utc"),
        "upload_to_cloudflare": False,
        "properties": None,
        "offices": None,
    }
    props = summary.get("properties") or {}
    if props:
        out["properties"] = {
            "success": props.get("success"),
            "total_ads": props.get("total_ads"),
            "by_category": props.get("by_category"),
            "duration_sec": props.get("duration_sec"),
            "error": props.get("error"),
        }
    offices = summary.get("offices") or {}
    if offices:
        out["offices"] = {
            "success": offices.get("success"),
            "offices_count": offices.get("offices_count"),
            "filtered_listings": offices.get("filtered_listings"),
            "site_ads_total": offices.get("site_ads_total"),
            "duration_sec": offices.get("duration_sec"),
            "error": offices.get("error"),
        }
    return out


def _save_ci_outputs(summary: Dict[str, Any], history_row: Dict[str, Any]) -> None:
    compact = _compact_summary(summary)
    with open(CI_LATEST_FILE, "w", encoding="utf-8") as f:
        json.dump(compact, f, ensure_ascii=False, indent=2)

    ci_history: List[Dict[str, Any]] = []
    if CI_HISTORY_FILE.exists():
        try:
            with open(CI_HISTORY_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, list):
                ci_history = loaded
        except (json.JSONDecodeError, OSError):
            ci_history = []
    # Store row without local snapshot path
    row = {k: v for k, v in history_row.items() if k != "snapshot"}
    ci_history.append(row)
    with open(CI_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(ci_history, f, ensure_ascii=False, indent=2)

    print(f"CI latest:  {CI_LATEST_FILE}")
    print(f"CI history: {CI_HISTORY_FILE}")


def _write_github_step_summary(summary: Dict[str, Any], history: List[Dict[str, Any]]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return

    props = summary.get("properties") or {}
    offices = summary.get("offices") or {}
    lines = [
        "## Ad count summary (no Cloudflare upload)",
        "",
        f"- **Time:** {summary.get('scraped_at')} (`{summary.get('scraped_at_utc')}`)",
        f"- **Properties ads:** {props.get('total_ads', '—')}",
        f"- **Offices filtered listings:** {offices.get('filtered_listings', '—')}",
        f"- **Offices site ads total:** {offices.get('site_ads_total', '—')}",
        f"- **Offices count:** {offices.get('offices_count', '—')}",
        "",
        "### Recent runs",
        "",
        "| scraped_at_utc | properties | offices_filtered | offices_site | offices |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in history[-20:]:
        lines.append(
            f"| {row.get('scraped_at_utc') or row.get('scraped_at')} "
            f"| {row.get('properties_ads', '—')} "
            f"| {row.get('offices_filtered_listings', '—')} "
            f"| {row.get('offices_site_ads_total', '—')} "
            f"| {row.get('offices_count', '—')} |"
        )
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def print_compare(ci: bool = False) -> None:
    history = []
    if ci and CI_HISTORY_FILE.exists():
        try:
            with open(CI_HISTORY_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, list):
                history = loaded
        except (json.JSONDecodeError, OSError):
            history = []
    if not history:
        history = _load_history()
    if not history:
        print("No local runs yet. Run without --compare first.")
        return

    print("\n" + "=" * 80)
    print("COMPARISON OF LOCAL RUNS")
    print("=" * 80)
    header = f"{'scraped_at':<22} {'props':>8} {'off_filt':>10} {'off_site':>10} {'offices':>8}"
    print(header)
    print("-" * len(header))
    for row in history:
        print(
            f"{str(row.get('scraped_at') or row.get('scraped_at_utc') or ''):<22} "
            f"{str(row.get('properties_ads', '-')):>8} "
            f"{str(row.get('offices_filtered_listings', '-')):>10} "
            f"{str(row.get('offices_site_ads_total', '-')):>10} "
            f"{str(row.get('offices_count', '-')):>8}"
        )
    print("=" * 80)
    print(f"History: {CI_HISTORY_FILE if ci else HISTORY_FILE}")


def _parse_times(times_arg: str) -> List[datetime]:
    """Parse HH:MM list into datetimes for today (or tomorrow if already passed)."""
    now = datetime.now()
    targets: List[datetime] = []
    for part in times_arg.split(","):
        part = part.strip()
        if not part:
            continue
        hour, minute = map(int, part.split(":"))
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target = target + timedelta(days=1)
        targets.append(target)
    return sorted(targets)


async def run_scheduled(times_arg: str, only: str, ci: bool = False) -> None:
    targets = _parse_times(times_arg)
    if not targets:
        print("No valid times in --times")
        return

    print("Scheduled local count runs (no Cloudflare):")
    for t in targets:
        print(f"  - {t.strftime('%Y-%m-%d %H:%M')}")

    for i, target in enumerate(targets, 1):
        wait_sec = max(0, (target - datetime.now()).total_seconds())
        if wait_sec > 0:
            print(f"\n[{i}/{len(targets)}] Waiting until {target.strftime('%Y-%m-%d %H:%M')} "
                  f"({int(wait_sec // 60)} min)...")
            # Sleep in chunks so Ctrl+C is responsive
            end = time.time() + wait_sec
            while time.time() < end:
                await asyncio.sleep(min(30, end - time.time()))

        print(f"\n[{i}/{len(targets)}] Starting run at {_now_stamp()}")
        await run_once(only=only, ci=ci)

    print("\nAll scheduled runs finished.")
    print_compare(ci=ci)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run CFl_data scrapers locally at one or more times; count ads; no Cloudflare upload."
    )
    parser.add_argument(
        "--times",
        help="Comma-separated HH:MM times to run today/tomorrow, e.g. 00:00,06:00,12:00,18:00",
    )
    parser.add_argument(
        "--only",
        choices=["all", "properties", "offices"],
        default="all",
        help="Which scrapers to run (default: all)",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Only print comparison table from previous local runs",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="CI mode: write count_times_latest.json + count_times_history.json at repo root",
    )
    args = parser.parse_args()

    if args.compare:
        print_compare(ci=args.ci)
        return

    if args.times:
        asyncio.run(run_scheduled(args.times, args.only, ci=args.ci))
    else:
        asyncio.run(run_once(only=args.only, ci=args.ci))
        print_compare(ci=args.ci)


if __name__ == "__main__":
    main()
