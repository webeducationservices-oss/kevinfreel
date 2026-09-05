#!/usr/bin/env python3
"""
apply_neighborhood_review.py — Read Kevin's notes on a neighborhood.

Kevin sends NOTES, not finished copy: corrections, the things only he knows from
selling there, who really buys. This surfaces them so they can be written up
into the page. It deliberately does NOT paste his notes onto the site, because
they arrive as fragments and bullet points.

    python3 scripts/apply_neighborhood_review.py             # read pending notes
    python3 scripts/apply_neighborhood_review.py --slug soho # just one
    python3 scripts/apply_neighborhood_review.py --done soho # mark handled

The flow:
    1. Run this to read what he sent.
    2. Write his knowledge into that neighborhood's `kevin` block in
       data/south-tampa-neighborhoods.json (take / expect / investment /
       best_for), in his voice, using his facts.
    3. python3 scripts/build_neighborhoods.py
    4. Mark it handled with --done <slug>, then commit and push.

The page then renders those sections under "Kevin's take" with his byline. That
is honest: the expertise, the claims and the local knowledge are his.
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

NOTE_FIELDS = ("wrong", "missing", "buyers", "guidance")
PAGE_FIELDS = ("take", "expect", "investment", "best_for")

PROMPTS = {
    "wrong": "What we got wrong",
    "missing": "What we were missing",
    "buyers": "Who actually buys here",
    "guidance": "Anything else",
}


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
    ap.add_argument("--slug", help="only this neighborhood")
    ap.add_argument("--done", metavar="SLUG",
                    help="mark this neighborhood's notes as handled")
    args = ap.parse_args()

    data = json.loads(DATA.read_text())
    rows = fetch_reviews()

    pending = []
    for row in rows:
        raw = row.get("raw_data") or {}
        slug = raw.get("neighborhood_slug")
        if not slug or slug not in data["neighborhoods"]:
            continue
        if (row.get("notes") or "").startswith("handled:"):
            continue
        pending.append((row, slug, raw))

    if args.done:
        marked = 0
        for row, slug, _ in pending:
            if slug != args.done:
                continue
            api(f"leads?id=eq.{row['id']}", method="PATCH",
                body={"notes": f"handled:{slug}", "status": "won"})
            marked += 1
        print(f"Marked {marked} submission(s) handled for {args.done}."
              if marked else f"Nothing pending for {args.done}.")
        return 0

    if args.slug:
        pending = [x for x in pending if x[1] == args.slug]

    if not pending:
        print("No notes waiting.")
        return 0

    # Newest per neighborhood wins.
    seen: set[str] = set()
    latest = []
    for row, slug, raw in pending:
        if slug in seen:
            continue
        seen.add(slug)
        latest.append((row, slug, raw))

    print(f"{len(latest)} neighborhood(s) with notes from Kevin\n")
    for row, slug, raw in latest:
        n = data["neighborhoods"][slug]
        print("=" * 72)
        print(f"{n['name']}   ({slug})   submitted {row['created_at'][:16]}")
        print("=" * 72)
        said_something = False
        for f in NOTE_FIELDS:
            v = (raw.get(f) or "").strip()
            if not v:
                continue
            said_something = True
            print(f"\n  ── {PROMPTS[f]} ──")
            for line in v.splitlines():
                print(f"     {line}")
        if not said_something:
            print("\n  (submitted with every field blank)")
        print()
        print(f"  Currently published: {'Kevin' if n.get('kevin') else 'baseline framing'}")
        print(f"  Write into: data/south-tampa-neighborhoods.json -> "
              f"neighborhoods.{slug}.kevin")
        print(f"  Then: python3 scripts/build_neighborhoods.py && "
              f"python3 scripts/apply_neighborhood_review.py --done {slug}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
