#!/usr/bin/env python3
"""
Refresh neighborhood pricing data for Kevin Freel's Tampa Bay neighborhood
report page.

Runs monthly on the 1st via .github/workflows/refresh-neighborhoods.yml.

Strategy:
  1. Try to fetch median home values from Zillow Research's public ZHVI
     time-series CSV (Zillow Home Value Index, smoothed, seasonally
     adjusted, ZIP-code level).
     - https://files.zillowstatic.com/research/public_csvs/zhvi/...
  2. For each neighborhood, map it to one or more representative ZIP
     codes and average their latest ZHVI values.
  3. Compute the 5-year trend by comparing the latest value to the
     value from 60 months ago.
  4. Update data/neighborhood-prices.json — preserving avg_days_on_market
     and avg_sqft (since Zillow Research's ZIP-level CSV doesn't carry
     those numbers; they are stable enough month to month).
  5. If the Zillow CSV fetch fails, log a warning and exit non-zero so
     the GitHub Action surfaces it without committing stale data.

Run locally:
  python3 scripts/refresh_neighborhood_data.py
"""

import csv
import io
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_FILE = os.path.join(ROOT, "data", "neighborhood-prices.json")

# Zillow Research — ZHVI: Zillow Home Value Index, smoothed, seasonally adjusted,
# all homes, time series, monthly, ZIP-code level. This CSV is the canonical,
# publicly downloadable Zillow dataset.
# See https://www.zillow.com/research/data/ for documentation.
ZHVI_URL = (
    "https://files.zillowstatic.com/research/public_csvs/zhvi/"
    "Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"
)

UA = "KevinFreelRealEstate/1.0 (https://kevinfreel.com)"

# Each neighborhood maps to one or more representative ZIP codes.
# The ZIPs are dominant residential ZIPs in that neighborhood; we average
# their ZHVI to smooth single-ZIP volatility.
ZIPS_BY_SLUG = {
    "south-tampa": ["33606", "33611", "33629"],          # Hyde Park / Bayshore / Davis Islands
    "hyde-park": ["33606"],                              # Hyde Park core
    "tampa-heights": ["33602", "33603"],                 # Tampa Heights + Riverside Heights
    "seminole-heights": ["33603", "33604"],              # Old + South + Southeast Seminole Heights
    "westchase": ["33626"],                              # Westchase
    "carrollwood": ["33618", "33624"],                   # Original Carrollwood + Northdale
    "wesley-chapel": ["33543", "33544", "33545"],        # Wesley Chapel proper
    "st-petersburg": ["33701", "33704", "33705"],        # Downtown + Old NE + Northshore
    "clearwater-beach": ["33767"],                       # Clearwater Beach / Sand Key
    "indian-rocks-beach": ["33785", "33786"],            # Indian Rocks Beach + Belleair Beach
    "odessa": ["33556"],                                 # Odessa / Keystone
    "dunedin": ["34698", "34689"],                       # Dunedin
}


def fetch_zhvi_csv(timeout=60):
    """Download the ZHVI CSV and return parsed rows + the date columns."""
    print(f"Downloading ZHVI CSV: {ZHVI_URL}")
    req = urllib.request.Request(ZHVI_URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8")
    reader = csv.reader(io.StringIO(body))
    header = next(reader)
    rows = list(reader)
    # Identify all date columns (YYYY-MM-DD format), sorted asc.
    date_cols = [
        (i, col) for i, col in enumerate(header)
        if len(col) == 10 and col[4] == "-" and col[7] == "-"
    ]
    print(f"  rows: {len(rows)}, date columns: {len(date_cols)}")
    return header, rows, date_cols


def build_zip_index(header, rows):
    """Return a dict: {zip_code: row_array}."""
    try:
        regionname_idx = header.index("RegionName")
    except ValueError:
        regionname_idx = 2  # fallback common position
    idx = {}
    for row in rows:
        # ZIP codes are stored as strings or ints depending on dataset; normalize.
        z = row[regionname_idx].strip() if len(row) > regionname_idx else ""
        if z.isdigit() and len(z) == 5:
            idx[z] = row
        elif z.isdigit() and len(z) < 5:
            # pad short codes
            idx[z.zfill(5)] = row
    return idx


def latest_and_5yr_for_zip(row, date_cols):
    """Return (latest_value, value_60mo_ago) for a row, skipping empty cells."""
    if not row:
        return None, None
    # date_cols already sorted ascending; iterate from end.
    latest = None
    for i, _d in reversed(date_cols):
        try:
            v = float(row[i])
            if v > 0:
                latest = v
                break
        except (ValueError, IndexError):
            continue

    # 5 years ago = ~60 months back from latest non-empty
    if latest is None:
        return None, None

    # find the index of the date column we used for `latest`
    used_idx = None
    for j, (i, _d) in enumerate(date_cols):
        try:
            v = float(row[i])
        except (ValueError, IndexError):
            continue
        if v > 0:
            used_idx = j  # keep updating; ends on the latest
    if used_idx is None or used_idx < 60:
        return latest, None

    older = None
    target_j = used_idx - 60
    # walk backwards from target to find first valid
    for j in range(target_j, -1, -1):
        i, _d = date_cols[j]
        try:
            v = float(row[i])
            if v > 0:
                older = v
                break
        except (ValueError, IndexError):
            continue
    return latest, older


def round_to_thousand(n: float) -> int:
    """Round to nearest $5,000 for cleaner display."""
    return int(round(n / 5000.0) * 5000)


def refresh_data(existing: dict) -> dict:
    header, rows, date_cols = fetch_zhvi_csv()
    if not date_cols:
        raise RuntimeError("No date columns parsed from ZHVI CSV")
    zip_idx = build_zip_index(header, rows)

    updated = json.loads(json.dumps(existing))  # deep copy
    updated["updated_at"] = datetime.utcnow().strftime("%Y-%m-%d")
    changes = []
    misses = []

    for slug, info in updated["neighborhoods"].items():
        zips = ZIPS_BY_SLUG.get(slug, [])
        latest_vals = []
        older_vals = []
        for z in zips:
            row = zip_idx.get(z) or zip_idx.get(z.zfill(5))
            if not row:
                continue
            latest, older = latest_and_5yr_for_zip(row, date_cols)
            if latest is not None:
                latest_vals.append(latest)
            if older is not None:
                older_vals.append(older)

        if not latest_vals:
            misses.append(slug)
            continue

        avg_latest = sum(latest_vals) / len(latest_vals)
        new_price = round_to_thousand(avg_latest)

        if older_vals:
            avg_older = sum(older_vals) / len(older_vals)
            trend = round(((avg_latest - avg_older) / avg_older) * 100.0)
        else:
            trend = info.get("trend_pct_5yr")

        old_price = info.get("median_price")
        if new_price != old_price:
            changes.append(f"{slug}: ${old_price:,} -> ${new_price:,}")

        info["median_price"] = new_price
        if trend is not None:
            info["trend_pct_5yr"] = trend

    print(f"  changes: {len(changes)}")
    for c in changes:
        print(f"    {c}")
    if misses:
        print(f"  misses (no ZIP match): {misses}")

    return updated


def main():
    if not os.path.exists(DATA_FILE):
        print(f"ERROR: data file not found: {DATA_FILE}", file=sys.stderr)
        return 2

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        existing = json.load(f)

    try:
        updated = refresh_data(existing)
    except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError) as e:
        print(f"ERROR: refresh failed: {e}", file=sys.stderr)
        return 3

    if updated == existing:
        print("No changes — data is current.")
        return 0

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(updated, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Wrote {DATA_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
