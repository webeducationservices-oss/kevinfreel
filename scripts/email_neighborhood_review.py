#!/usr/bin/env python3
"""
email_neighborhood_review.py — The weekly loop.

Picks the next South Tampa neighborhood Kevin hasn't written up, drafts a take
with Claude, saves that draft into data/south-tampa-neighborhoods.json, and
emails Kevin a link to the review form.

Kevin edits the draft at /neighborhood-review/?n=<slug> and submits. His answers
land in Supabase `leads` as form_type `neighborhood-review`, and
scripts/apply_neighborhood_review.py merges them back in as the published copy.

    python3 scripts/email_neighborhood_review.py            # draft + send
    python3 scripts/email_neighborhood_review.py --dry-run  # draft + print, no email
    python3 scripts/email_neighborhood_review.py --slug palma-ceia

Environment:
    ANTHROPIC_API_KEY   drafting
    RESEND_API_KEY      delivery
    REVIEW_TO           override recipient (default kevinfreel@c21be.com)

IMPORTANT: the draft this writes is never published as-is. It exists so Kevin has
something to react to instead of a blank page. Only text Kevin submits through
the form is rendered on the public site — see scripts/build_neighborhoods.py.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "south-tampa-neighborhoods.json"
PRICES = ROOT / "data" / "neighborhood-prices.json"

SITE = "https://www.kevinfreel.com"
FROM = "Kevin Freel Neighborhoods <forms@sitenotifications.org>"
DEFAULT_TO = "kevinfreel@c21be.com"

MODEL = "claude-opus-5"


class NeighborhoodDraft(BaseModel):
    """The four fields the review form asks Kevin to confirm or rewrite."""

    take: str = Field(
        description=(
            "2-3 short paragraphs, separated by a blank line. Who actually buys "
            "here, what the streets feel like, and one honest drawback."
        )
    )
    expect: str = Field(
        description=(
            "1-2 paragraphs on practical realities: flood zone and insurance, "
            "parking, traffic, noise, lot sizes, teardown activity, schools."
        )
    )
    investment: str = Field(
        description=(
            "1-2 paragraphs on the investment picture: appreciation, who is "
            "buying and why, teardown/land value dynamics, what to watch out for."
        )
    )
    best_for: str = Field(
        description="One sentence. 'Buyers who want X without giving up Y.'"
    )


SYSTEM = """You draft neighborhood profiles for Kevin Freel, a Tampa Realtor who has \
sold South Tampa since 1985. Kevin reviews and rewrites everything you draft before \
any of it is published, so your job is to give him a strong, specific starting point \
to react to — not to be safe or vague.

Write the way Kevin talks: first person, plain, direct, no marketing gloss. He names \
real drawbacks out loud, because that is what earns trust. Reference concrete Tampa \
things — Bayshore, Plant High, the flood maps, the teardown wave, MacDill commuters, \
Gasparilla — where they genuinely apply.

Rules:
- Never invent a specific statistic, price, school rating, or date. Speak in ranges \
and directional terms ("north of a million", "moves fast", "insurance is the line \
item that surprises people") rather than inventing precision Kevin would have to \
correct.
- If you are unsure whether something is true of this specific neighborhood, write \
the sentence so Kevin can confirm or strike it, rather than asserting it flatly.
- No em dashes. No emoji. No "nestled", "boasts", "hidden gem", "charming enclave".
- Do not open with the neighborhood name. Start with the observation."""


def build_prompt(slug: str, n: dict, data: dict, prices: dict) -> str:
    district = next(
        (d for d in data["districts"] if d["id"] == n.get("district")), {}
    )
    vibes = {v["id"]: v["label"] for v in data["vibes"]}
    vibe_labels = ", ".join(vibes.get(v, v) for v in n.get("vibes", []))

    market = ""
    zips = n.get("zips") or []
    by_zip = prices.get("by_zip") or {}
    hits = [by_zip[z] for z in zips if z in by_zip]
    if hits:
        med = round(sum(h["median_price"] for h in hits) / len(hits))
        market = (
            f"\nZIP-area market context (Zillow ZHVI, {prices.get('updated_at')}): "
            f"median value about ${med:,} across ZIP {', '.join(zips)}. "
            f"That ZIP also covers {hits[0].get('covers', 'other neighborhoods')}, "
            f"so it is area context, not a per-street number."
        )

    return f"""Draft the profile for **{n['name']}** in South Tampa.

District: {district.get('name', 'South Tampa')} — {district.get('blurb', '')}
Character tags: {vibe_labels}
Kevin's own one-line personality (already published, match this register):
"{n['personality']}"{market}

Write the four sections. Remember Kevin is going to edit this, so be specific and \
opinionated rather than hedged — a draft he can argue with is more useful to him \
than one he has to fill in."""


def draft_with_claude(slug: str, n: dict, data: dict, prices: dict) -> dict:
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        messages=[{"role": "user", "content": build_prompt(slug, n, data, prices)}],
        output_format=NeighborhoodDraft,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Draft refused for {slug}: {response.stop_details}")
    return response.parsed_output.model_dump()


def pick_next(data: dict, slug: str | None) -> tuple[str, dict]:
    nbhs = data["neighborhoods"]
    if slug:
        if slug not in nbhs:
            raise SystemExit(f"Unknown slug: {slug}")
        return slug, nbhs[slug]

    # Tier 1 first (the neighborhoods with real search demand), then the rest.
    for tier in (1, 2):
        for s, n in nbhs.items():
            if n.get("tier") == tier and not n.get("kevin"):
                return s, n
    raise SystemExit("Every neighborhood has Kevin's notes. Nothing to send.")


def send_email(to: str, slug: str, n: dict, draft: dict, remaining: int) -> None:
    key = os.environ.get("RESEND_API_KEY")
    if not key:
        raise SystemExit("RESEND_API_KEY not set")

    link = f"{SITE}/neighborhood-review/?n={slug}"
    preview = (draft.get("take") or "").split("\n\n")[0][:320]

    html = f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;">
  <div style="max-width:600px;margin:0 auto;padding:32px 24px;">
    <div style="border-bottom:3px solid #c41e2a;padding-bottom:14px;margin-bottom:28px;">
      <div style="font-size:20px;font-weight:700;letter-spacing:.5px;color:#111;">KEVIN <span style="color:#c41e2a;">FREEL</span></div>
      <div style="font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#6b7280;margin-top:3px;">Neighborhood of the Week</div>
    </div>

    <h1 style="font-family:Georgia,serif;font-size:28px;line-height:1.2;color:#111;margin:0 0 14px;">{n['name']}</h1>

    <p style="font-size:15px;line-height:1.6;color:#4a4a4a;margin:0 0 22px;">
      Kevin, I took a swing at writing up {n['name']}. Here's how my draft opens:
    </p>

    <div style="background:#fff;border-left:3px solid #c41e2a;border-radius:0 6px 6px 0;padding:16px 20px;margin:0 0 24px;">
      <p style="font-size:14px;line-height:1.65;color:#4a4a4a;margin:0;font-style:italic;">{preview}&hellip;</p>
    </div>

    <p style="font-size:15px;line-height:1.6;color:#4a4a4a;margin:0 0 26px;">
      Tell me what I got wrong. Whatever you write replaces my draft word for word
      on the page, so it ends up in your voice, not mine. Takes about five minutes.
    </p>

    <a href="{link}" style="display:inline-block;background:#c41e2a;color:#fff;text-decoration:none;font-size:15px;font-weight:600;padding:14px 28px;border-radius:6px;">Review {n['name']} &rarr;</a>

    <p style="font-size:13px;line-height:1.6;color:#9ca3af;margin:30px 0 0;padding-top:18px;border-top:1px solid #e5e7eb;">
      {remaining} South Tampa {'neighborhood' if remaining == 1 else 'neighborhoods'} still waiting on your notes.
      Every one you finish goes live at
      <a href="{SITE}/south-tampa-neighborhoods/" style="color:#c41e2a;">kevinfreel.com/south-tampa-neighborhoods</a>.
    </p>
  </div>
</body></html>"""

    payload = json.dumps(
        {
            "from": FROM,
            "to": [to],
            "reply_to": "justin@webeducationservices.com",
            "subject": f"Neighborhood of the week: {n['name']}",
            "html": html,
        }
    ).encode()

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.loads(r.read())
    print(f"  sent to {to} (resend id {body.get('id')})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", help="draft a specific neighborhood instead of the next one")
    ap.add_argument("--dry-run", action="store_true", help="draft and print, don't email or save")
    args = ap.parse_args()

    data = json.loads(DATA.read_text())
    prices = json.loads(PRICES.read_text()) if PRICES.exists() else {}

    slug, n = pick_next(data, args.slug)
    remaining = sum(1 for x in data["neighborhoods"].values() if not x.get("kevin"))
    print(f"Drafting {n['name']} ({slug}) — {remaining} still unreviewed")

    draft = draft_with_claude(slug, n, data, prices)

    print()
    for k, v in draft.items():
        print(f"  ── {k} ──")
        for line in v.split("\n\n"):
            print(f"     {line.strip()[:150]}")
        print()

    if args.dry_run:
        print("(dry run — nothing saved, nothing sent)")
        return 0

    data["neighborhoods"][slug]["draft"] = draft
    DATA.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"  saved draft to {DATA.relative_to(ROOT)}")

    send_email(os.environ.get("REVIEW_TO", DEFAULT_TO), slug, n, draft, remaining)
    print("\nDone. Commit the updated data file so the review form can load the draft.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
