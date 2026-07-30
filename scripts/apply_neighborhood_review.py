#!/usr/bin/env python3
"""
apply_neighborhood_review.py — Merge Kevin's submitted review into the data file.

Reads pending `neighborhood-review` submissions from the shared Supabase `leads`
table, writes them into data/south-tampa-neighborhoods.json under the
neighborhood's `kevin` key, and marks each lead applied so it isn't reapplied.

    python3 scripts/apply_neighborhood_review.py            # list what's pending
    python3 scripts/apply_neighborhood_review.py --apply    # merge them in
    python3 scripts/apply_neighborhood_review.py --apply --slug palma-ceia

Then rebuild and deploy:

    python3 scripts/build_neighborhoods.py && git add -A && git commit && git push

Only the fields Kevin actually filled in are written. A blank field is left
absent, which means that section simply doesn't render — see build_neighborhoods.py.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "south-tampa-neighborhoods.json"

SUPABASE = "https://sqeegvibwqkiugiwomqd.supabase.co"
SITE_ID = "e52c801e-cbb7-41a2-ab62-090a210572d4"  # kevin-freel

FIELDS = ("take", "expect", "investment", "best_for")


def service_key() -> str:
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        raise SystemExit(
            "SUPABASE_SERVICE_ROLE_KEY not set — "
            "source /Users/justinbabcock/Desktop/Websites/.env.keys first"
        )
    return key


def api(path: str, *, method: str = "GET", body: dict | list | None = None) -> list:
    key = service_key()
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{SUPABASE}/rest/v1/{path}",
        data=data,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    return json.loads(raw) if raw else []


def fetch_reviews() -> list[dict]:
    q = urllib.parse.urlencode(
        {
            "site_id": f"eq.{SITE_ID}",
            "form_type": "eq.neighborhood-review",
            "select": "id,created_at,raw_data,notes",
            "order": "created_at.desc",
        }
    )
    return api(f"leads?{q}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the changes")
    ap.add_argument("--slug", help="only apply this neighborhood")
    args = ap.parse_args()

    data = json.loads(DATA.read_text())
    rows = fetch_reviews()

    pending = []
    for row in rows:
        raw = row.get("raw_data") or {}
        slug = raw.get("neighborhood_slug")
        if not slug or slug not in data["neighborhoods"]:
            continue
        if args.slug and slug != args.slug:
            continue
        if (row.get("notes") or "").startswith("applied:"):
            continue
        pending.append((row, slug, raw))

    if not pending:
        print("Nothing pending.")
        return 0

    # Newest submission per neighborhood wins.
    seen: set[str] = set()
    latest = []
    for row, slug, raw in pending:
        if slug in seen:
            continue
        seen.add(slug)
        latest.append((row, slug, raw))

    print(f"{len(latest)} review(s) pending:\n")
    for row, slug, raw in latest:
        n = data["neighborhoods"][slug]
        filled = [f for f in FIELDS if (raw.get(f) or "").strip()]
        print(f"  {n['name']}  ({row['created_at'][:10]})")
        print(f"    fields: {', '.join(filled) if filled else '(none — nothing to publish)'}")
        if (raw.get("corrections") or "").strip():
            print(f"    ⚠ corrections: {raw['corrections'].strip()[:200]}")
        print()

    if not args.apply:
        print("Re-run with --apply to write these in.")
        return 0

    applied = 0
    for row, slug, raw in latest:
        kevin = {f: raw[f].strip() for f in FIELDS if (raw.get(f) or "").strip()}
        if not kevin:
            print(f"  skipped {slug}: every field blank")
            continue
        data["neighborhoods"][slug]["kevin"] = kevin
        # Once Kevin has written it up, it deserves its own page.
        data["neighborhoods"][slug]["tier"] = 1
        api(
            f"leads?id=eq.{row['id']}",
            method="PATCH",
            body={"notes": f"applied:{slug}", "status": "won"},
        )
        print(f"  applied {data['neighborhoods'][slug]['name']} ({len(kevin)} field(s))")
        applied += 1

    if applied:
        DATA.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        print(f"\nWrote {DATA.relative_to(ROOT)}")
        print("Next: python3 scripts/build_neighborhoods.py && git add -A && git commit && git push")
    return 0


if __name__ == "__main__":
    sys.exit(main())
