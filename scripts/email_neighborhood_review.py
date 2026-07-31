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
    """
    The baseline framing that publishes immediately, and that Kevin later
    rewrites in his own voice through the weekly review form.
    """

    take: str = Field(
        description=(
            "2-3 short paragraphs separated by a blank line. What the streets "
            "are actually like, who the housing suits, and one honest tradeoff. "
            "Third person, no 'I', no opinions attributed to Kevin."
        )
    )
    expect: str = Field(
        description=(
            "1-2 paragraphs on practical realities: flood exposure and "
            "insurance, lot sizes, parking, traffic and noise, how much new "
            "construction is going in. Third person."
        )
    )
    investment: str = Field(
        description=(
            "1-2 paragraphs on the market position: where it sits relative to "
            "South Tampa overall, whether homes trade on the house or the land, "
            "and what a buyer should look into. No invented numbers. Third person."
        )
    )
    best_for: str = Field(
        description=(
            "One sentence beginning 'Buyers who'. No 'I'. States the tradeoff "
            "plainly."
        )
    )


SYSTEM = """You write neighborhood framing for a South Tampa real estate guide. This \
copy publishes immediately as the site's baseline description, so it must be \
accurate and defensible on a licensed agent's website. Kevin Freel, who has sold \
here since 1985, later rewrites each one in his own first-person voice; your job is \
to make the page genuinely useful before he gets to it.

VOICE: neutral, editorial, third person. This is the guide speaking, not Kevin. \
Never write "I", "me", "my", and never attribute an opinion to Kevin. Write "the \
streets here are", not "I love the streets here". Confident and specific, but \
observational rather than personal.

Be concrete about this specific neighborhood. Generic copy that would fit any \
neighborhood is a failure. Use real Tampa anchors where they genuinely apply: \
Bayshore Boulevard, Hyde Park Village, MacDill commuters, the brick streets, the \
oak canopy, Gandy, the marina, Picnic Island, Gasparilla.

HARD RULES:
- Never invent a statistic, price, percentage, school rating, or date. The only \
numbers you may reference are ones given to you in the prompt. Otherwise speak \
directionally: "well above the South Tampa median", "moves quickly", "insurance is \
the line item that surprises people".
- Never claim a specific school rating or a school-district price premium. No \
verified study of a Plant High premium exists.
- If you are not certain something is true of this specific neighborhood, either \
leave it out or phrase it as the general South Tampa condition it is.
- No em dashes. No emoji. No "nestled", "boasts", "hidden gem", "charming enclave", \
"tucked away", "sought-after".
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
        all_meds = [v["median_price"] for v in by_zip.values() if v.get("median_price")]
        lo, hi = min(all_meds), max(all_meds)
        where = (
            "at the top of" if med >= hi * 0.9
            else "toward the lower end of" if med <= lo * 1.15
            else "in the middle of"
        )
        market = (
            f"\n\nMARKET CONTEXT (you may reference this directionally, but do NOT "
            f"quote the dollar figure — the page already shows it in a stat block):\n"
            f"ZIP {', '.join(zips)} has a median home value around ${med:,}, which "
            f"sits {where} the South Tampa range (roughly ${lo:,} to ${hi:,} across "
            f"its ZIPs). That ZIP also covers {hits[0].get('covers', 'other areas')}."
        )

    commercial = ""
    if n.get("is_commercial"):
        commercial = (
            "\n\nIMPORTANT: this is a commercial or institutional district, not a "
            "residential neighborhood. Frame it as somewhere people go, and explain "
            "how it shapes the residential areas around it, rather than describing "
            "it as a place to buy a house."
        )

    return f"""Write the framing for **{n['name']}** in South Tampa.

District: {district.get('name', 'South Tampa')}. {district.get('blurb', '')}
Character tags: {vibe_labels}

Kevin's published one-line personality for this neighborhood. Your copy must be
consistent with it and expand on it, never contradict it:
"{n['personality']}"{market}{commercial}

VERIFIED SOUTH TAMPA CONDITIONS you may draw on where they genuinely apply to this
neighborhood (these are sourced and already published on the guide's index page):
- Most of South Tampa sits in a FEMA Special Flood Hazard Area; flood insurance is
  mandatory with a mortgage. Tampa is a CRS Class 5 community, which earns a 25%
  NFIP premium discount inside flood zones.
- The FEMA 50% rule: if repairs or improvements exceed 50% of the structure's value
  (land excluded, costs accumulating over a rolling 12 months) in an A or V zone,
  the home must be brought up to current floodplain code including elevation. This
  is why many older low-lying homes trade as land rather than as houses.
- South Tampa averages roughly 231 permitted residential demolitions a year and,
  with Central Tampa, accounts for about 88% of the City's residential demolitions.

Apply these only where they fit. A newer elevated waterfront enclave and a 1920s
bungalow street have very different exposure, and saying so is the useful part.

Write the four sections."""


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


def draft_all(data: dict, prices: dict, *, force: bool = False, workers: int = 6) -> int:
    """
    Draft every neighborhood that doesn't have one yet, concurrently.

    Used once to bring the whole guide up to a complete baseline. After that the
    weekly loop is about Kevin replacing these with his own voice, not filling
    blanks.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    todo = [
        (s, n) for s, n in data["neighborhoods"].items()
        if force or not n.get("draft")
    ]
    if not todo:
        print("Every neighborhood already has framing.")
        return 0

    print(f"Drafting {len(todo)} neighborhood(s) with {workers} workers\n")
    done = failed = 0

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(draft_with_claude, s, n, data, prices): (s, n)
            for s, n in todo
        }
        for fut in as_completed(futures):
            slug, n = futures[fut]
            try:
                data["neighborhoods"][slug]["draft"] = fut.result()
                done += 1
                print(f"  [{done + failed}/{len(todo)}] {n['name']}")
            except Exception as e:
                failed += 1
                print(f"  [{done + failed}/{len(todo)}] FAILED {n['name']}: {e}")

    DATA.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"\n{done} drafted, {failed} failed. Saved to {DATA.relative_to(ROOT)}")
    print("Next: python3 scripts/build_neighborhoods.py")
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", help="draft a specific neighborhood instead of the next one")
    ap.add_argument("--dry-run", action="store_true", help="draft and print, don't email or save")
    ap.add_argument("--all", action="store_true", help="draft every neighborhood missing framing, no email")
    ap.add_argument("--force", action="store_true", help="with --all, redraft even if framing exists")
    ap.add_argument("--workers", type=int, default=6, help="concurrency for --all")
    args = ap.parse_args()

    data = json.loads(DATA.read_text())
    prices = json.loads(PRICES.read_text()) if PRICES.exists() else {}

    if args.all:
        return draft_all(data, prices, force=args.force, workers=args.workers)

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
