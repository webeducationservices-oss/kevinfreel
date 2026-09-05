#!/usr/bin/env python3
"""
build_neighborhoods.py — Generate the South Tampa neighborhood catalog page and
the per-neighborhood detail pages from data/south-tampa-neighborhoods.json.

Run this after ANY edit to the data file (including after applying one of
Kevin's weekly reviews via scripts/apply_neighborhood_review.py).

    python3 scripts/build_neighborhoods.py
    python3 scripts/build_neighborhoods.py --dry-run

Editorial rule enforced by this script
--------------------------------------
Nothing written by an AI is ever published in Kevin's voice. A detail page
renders "Kevin's take", "What to expect" and "Investment notes" ONLY when the
neighborhood has a `kevin` block, which is populated exclusively from Kevin's
own submissions through /neighborhood-review/. Until then those sections are
absent and the page shows an honest "Kevin is writing this one up" note.

Market data is ZIP-level (Zillow ZHVI via scripts/refresh_neighborhood_data.py).
South Tampa packs ~51 named neighborhoods into ~6 ZIPs, so the figures are
labelled as ZIP-area context rather than implied to be street-level precision.
"""
from __future__ import annotations

import argparse
import json
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "south-tampa-neighborhoods.json"
PRICES = ROOT / "data" / "neighborhood-prices.json"
NAV = ROOT / "partials" / "nav.html"
FOOTER = ROOT / "partials" / "footer.html"
OUT_CATALOG = ROOT / "south-tampa-neighborhoods.html"
OUT_DIR = ROOT / "neighborhoods"

SITE = "https://www.kevinfreel.com"
GTM = "GTM-5PP6R6HL"

VIBE_ICONS = {
    "landmark": '<path d="M3 21h18M5 21V10l7-5 7 5v11M9 21v-6h6v6"/>',
    "sparkle": '<path d="M12 3l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.4z"/>',
    "home": '<path d="M3 12l9-9 9 9"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/>',
    "leaf": '<path d="M11 20A7 7 0 019.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10z"/><path d="M2 21c0-3 1.85-5.36 5.08-6"/>',
    "trees": '<path d="M12 2l4 6h-3l3 5h-3l3 5H8l3-5H8l3-5H8z"/><path d="M12 18v4"/>',
    "anchor": '<circle cx="12" cy="5" r="3"/><path d="M12 22V8M5 12H2a10 10 0 0020 0h-3"/>',
    "waves": '<path d="M2 6c2 0 2 2 4 2s2-2 4-2 2 2 4 2 2-2 4-2 2 2 4 2"/><path d="M2 12c2 0 2 2 4 2s2-2 4-2 2 2 4 2 2-2 4-2 2 2 4 2"/><path d="M2 18c2 0 2 2 4 2s2-2 4-2 2 2 4 2 2-2 4-2 2 2 4 2"/>',
    "building": '<rect x="4" y="2" width="16" height="20" rx="2"/><path d="M9 22v-4h6v4M9 6h.01M15 6h.01M9 10h.01M15 10h.01M9 14h.01M15 14h.01"/>',
    "palm": '<path d="M13 8c0-2.76-2.46-5-5.5-5S2 5.24 2 8h11z"/><path d="M13 8c0-2.76 2.46-5 5.5-5S24 5.24 24 8H13z"/><path d="M13 8v13"/>',
    "handshake": '<path d="M11 17l2 2a1 1 0 001.4 0l2.6-2.6a2 2 0 000-2.8L13 9.6"/><path d="M13 9.6L9.5 6.1a2 2 0 00-2.8 0L4 8.8a2 2 0 000 2.8L7 14.6"/>',
}


def esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def read_partial(p: Path) -> str:
    return p.read_text().strip() if p.exists() else ""


def head_block(title: str, desc: str, canonical: str, *, css_depth: int = 0) -> str:
    """Shared <head>. css_depth is unused (all asset paths are root-absolute)."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">

  <title>{esc(title)}</title>
  <meta name="description" content="{esc(desc)}">
  <link rel="canonical" href="{canonical}">

  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(desc)}">
  <meta property="og:image" content="{SITE}/images/og-image.jpg">
  <meta property="og:url" content="{canonical}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Kevin Freel Real Estate">
  <!-- BEGIN_FAVICONS -->
  <link rel="icon" href="/favicon.ico" sizes="any">
  <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
  <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="96x96" href="/favicon-96x96.png">
  <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
  <link rel="manifest" href="/site.webmanifest">
  <meta name="theme-color" content="#c41e2a">
  <!-- END_FAVICONS -->

  <link rel="preload" as="font" type="font/woff2" href="/fonts/playfair-display.woff2" crossorigin>
  <link rel="preload" as="font" type="font/woff2" href="/fonts/inter.woff2" crossorigin>

  <link rel="stylesheet" href="/fonts/fonts.css">
  <link rel="stylesheet" href="/styles.css">

  <script src="/components.js" defer></script>
  <!-- BEGIN_GTM -->
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('consent', 'default', {{
      'analytics_storage': 'granted',
      'ad_storage': 'denied',
      'ad_user_data': 'denied',
      'ad_personalization': 'denied'
    }});
  </script>
  <script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':
  new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],
  j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
  'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
  }})(window,document,'script','dataLayer','{GTM}');</script>
  <!-- END_GTM -->
  <script src="/mae-edit-loader.js" async></script>
"""


def body_open() -> str:
    return f"""</head>
<body>
  <!-- BEGIN_GTM_NOSCRIPT --><noscript><iframe src="https://www.googletagmanager.com/ns.html?id={GTM}" height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript><!-- END_GTM_NOSCRIPT -->

  <!-- BEGIN_NAV -->
{read_partial(NAV)}
  <!-- END_NAV -->
"""


def tail() -> str:
    return f"""
  <!-- BEGIN_FOOTER -->
{read_partial(FOOTER)}
  <!-- END_FOOTER -->

</body>
</html>
"""


def vibe_chip(vibe: dict, *, as_button: bool = False) -> str:
    icon = VIBE_ICONS.get(vibe.get("icon", ""), VIBE_ICONS["home"])
    svg = (
        f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{icon}</svg>'
    )
    if as_button:
        return (
            f'<button type="button" class="vibe-chip" data-vibe="{vibe["id"]}" '
            f'aria-pressed="false">{svg}<span>{esc(vibe["label"])}</span></button>'
        )
    return f'<span class="vibe-tag">{svg}{esc(vibe["label"])}</span>'


# ──────────────────────────────────────────────────────────────────────
# Market data
# ──────────────────────────────────────────────────────────────────────
def market_for(n: dict, prices: dict) -> dict | None:
    """
    Resolve ZIP-level market context for a neighborhood.

    South Tampa's ~51 named neighborhoods sit inside roughly 6 ZIPs, so this is
    deliberately presented as *area* context, never as a per-street valuation.
    Returns None when we have no verified figure — an empty slot is always
    better than an invented one on a licensed agent's site.
    """
    zips = n.get("zips") or []
    if not zips:
        return None
    by_zip = prices.get("by_zip") or {}
    hits = [by_zip[z] for z in zips if z in by_zip and by_zip[z].get("median_price")]
    if not hits:
        return None
    med = round(sum(h["median_price"] for h in hits) / len(hits))
    trends = [h["trend_pct_5yr"] for h in hits if h.get("trend_pct_5yr") is not None]
    return {
        "median_price": med,
        "trend_pct_5yr": round(sum(trends) / len(trends)) if trends else None,
        "zips": zips,
        "as_of": prices.get("updated_at"),
        # ZIPs come from City of Tampa GIS boundaries intersected with the
        # official address-point layer. A few informal names have no city
        # polygon and straddle a line; say so rather than implying precision.
        "zip_confidence": n.get("zip_confidence", "high"),
    }


# ──────────────────────────────────────────────────────────────────────
# Catalog page
# ──────────────────────────────────────────────────────────────────────
def build_catalog(data: dict, prices: dict) -> str:
    districts = data["districts"]
    vibes = {v["id"]: v for v in data["vibes"]}
    nbhs = data["neighborhoods"]

    total = len(nbhs)
    reviewed = sum(1 for n in nbhs.values() if n.get("kevin"))

    title = f"South Tampa Neighborhoods | A Guide to All {total} | Kevin Freel"
    desc = (
        "Hyde Park to Port Tampa, Palma Ceia to Culbreath Isles. What each South Tampa "
        "neighborhood is actually like, from a Realtor who has sold here since 1985."
    )

    out = [head_block(title, desc, f"{SITE}/south-tampa-neighborhoods/")]

    # Page-specific CSS (site convention: inline for page-scoped styles)
    out.append("""  <style>
  .stn-hero{padding:8rem clamp(1.25rem,4vw,2rem) 3rem;max-width:1100px;margin:0 auto;text-align:center}
  .stn-eyebrow{font-size:.75rem;letter-spacing:.2em;text-transform:uppercase;color:var(--gold);font-weight:600;margin-bottom:.75rem}
  .stn-hero h1{font-family:var(--font-serif);font-size:clamp(2.2rem,5.5vw,3.6rem);line-height:1.08;color:var(--navy);margin:0 0 1rem;font-weight:600}
  .stn-hero p{max-width:60ch;margin:0 auto;color:var(--text-muted);font-size:1.0625rem;line-height:1.65}
  .stn-counts{display:flex;gap:2.5rem;justify-content:center;margin-top:2rem;flex-wrap:wrap}
  .stn-count{text-align:center}
  .stn-count b{display:block;font-family:var(--font-serif);font-size:2rem;color:var(--gold);line-height:1;font-variant-numeric:tabular-nums}
  .stn-count span{font-size:.75rem;letter-spacing:.12em;text-transform:uppercase;color:var(--text-muted)}

  .stn-filters{max-width:1100px;margin:0 auto;padding:0 clamp(1.25rem,4vw,2rem) 2.5rem}
  .stn-filters-head{font-size:.75rem;letter-spacing:.16em;text-transform:uppercase;color:var(--text-muted);font-weight:600;margin-bottom:.9rem;text-align:center}
  .vibe-chips{display:flex;flex-wrap:wrap;gap:.55rem;justify-content:center}
  .vibe-chip{display:inline-flex;align-items:center;gap:.4rem;padding:.5rem .9rem;border:1px solid var(--border);background:var(--white);border-radius:999px;font-size:.8125rem;font-weight:500;color:var(--text);cursor:pointer;transition:all .18s;font-family:inherit}
  .vibe-chip svg{width:15px;height:15px;opacity:.65}
  .vibe-chip:hover{border-color:var(--gold);color:var(--gold)}
  .vibe-chip[aria-pressed="true"]{background:var(--gold);border-color:var(--gold);color:#fff}
  .vibe-chip[aria-pressed="true"] svg{opacity:1}
  .stn-clear{display:block;margin:1rem auto 0;background:none;border:0;color:var(--text-muted);font-size:.8125rem;text-decoration:underline;cursor:pointer;font-family:inherit}
  .stn-clear[hidden]{display:none}

  .stn-district{max-width:1100px;margin:0 auto;padding:0 clamp(1.25rem,4vw,2rem) 3.5rem}
  .stn-district-head{border-top:1px solid var(--border);padding-top:2rem;margin-bottom:1.75rem}
  .stn-district-head h2{font-family:var(--font-serif);font-size:clamp(1.5rem,3.2vw,2.1rem);color:var(--navy);margin:0 0 .5rem;font-weight:600;line-height:1.2}
  .stn-district-head p{color:var(--text-muted);max-width:65ch;margin:0;font-size:.9375rem;line-height:1.6}
  .stn-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:1.25rem}

  .stn-card{background:var(--white);border:1px solid var(--border);border-radius:12px;padding:1.5rem;display:flex;flex-direction:column;gap:.75rem;transition:transform .2s,box-shadow .2s,border-color .2s}
  .stn-card:hover{transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,.07);border-color:#d5d8dd}
  .stn-card[hidden]{display:none}
  .stn-card-top{display:flex;align-items:flex-start;justify-content:space-between;gap:.75rem}
  .stn-card h3{font-family:var(--font-serif);font-size:1.1875rem;color:var(--navy);margin:0;font-weight:600;line-height:1.25}
  .stn-card h3 a{color:inherit;text-decoration:none}
  .stn-card h3 a:hover{color:var(--gold)}
  .stn-badge{flex-shrink:0;font-size:.625rem;letter-spacing:.1em;text-transform:uppercase;font-weight:700;padding:.25rem .5rem;border-radius:3px;white-space:nowrap}
  .stn-badge.reviewed{background:#e8f3ea;color:#2a6d3b}
  .stn-badge.commercial{background:#eef0f3;color:#6b7280}
  .stn-card p.stn-personality{color:var(--text-muted);font-size:.9063rem;line-height:1.6;margin:0;flex:1}
  .stn-card-tags{display:flex;flex-wrap:wrap;gap:.4rem}
  .vibe-tag{display:inline-flex;align-items:center;gap:.3rem;font-size:.6875rem;letter-spacing:.04em;text-transform:uppercase;font-weight:600;color:var(--text-muted);background:var(--bg-alt);border-radius:999px;padding:.25rem .6rem}
  .vibe-tag svg{width:12px;height:12px}
  .stn-card-foot{display:flex;align-items:center;justify-content:space-between;gap:.75rem;border-top:1px solid var(--border);padding-top:.75rem;margin-top:.25rem}
  .stn-zip{font-size:.75rem;color:var(--text-light);font-variant-numeric:tabular-nums}
  .stn-more{font-size:.8125rem;font-weight:600;color:var(--gold);text-decoration:none}
  .stn-more:hover{text-decoration:underline}
  .stn-soon{font-size:.75rem;color:var(--text-light);font-style:italic}

  .stn-empty{text-align:center;padding:3rem 1rem;color:var(--text-muted)}
  .stn-empty[hidden]{display:none}

  .stn-facts{max-width:1100px;margin:0 auto;padding:1rem clamp(1.25rem,4vw,2rem) 3.5rem}
  .stn-facts-inner{border-top:1px solid var(--border);padding-top:2rem}
  .stn-facts h2{font-family:var(--font-serif);font-size:clamp(1.5rem,3.2vw,2.1rem);color:var(--navy);margin:0 0 .6rem;font-weight:600;line-height:1.2}
  .stn-facts-lede{color:var(--text-muted);max-width:65ch;margin:0 0 2rem;font-size:.9375rem;line-height:1.65}
  .stn-fact{background:var(--white);border:1px solid var(--border);border-left:3px solid var(--gold);border-radius:0 10px 10px 0;padding:1.4rem 1.6rem;margin-bottom:1rem}
  .stn-fact h3{font-family:var(--font-serif);font-size:1.1875rem;color:var(--navy);margin:0 0 .6rem;font-weight:600;line-height:1.3}
  .stn-fact p{color:var(--text);font-size:.9375rem;line-height:1.7;margin:0 0 .6rem;max-width:72ch}
  .stn-fact p:last-child{margin-bottom:0}
  .stn-src{font-size:.75rem;color:var(--text-light)}
  .stn-src a{color:var(--text-muted)}

  .stn-note{max-width:1100px;margin:0 auto 4rem;padding:0 clamp(1.25rem,4vw,2rem)}
  .stn-note-inner{background:var(--bg-alt);border-left:3px solid var(--gold);border-radius:0 8px 8px 0;padding:1.5rem 1.75rem}
  .stn-note-inner h3{font-family:var(--font-serif);font-size:1.125rem;color:var(--navy);margin:0 0 .5rem;font-weight:600}
  .stn-note-inner p{color:var(--text-muted);font-size:.875rem;line-height:1.65;margin:0 0 .6rem;max-width:75ch}
  .stn-note-inner p:last-child{margin-bottom:0}
  @media(max-width:640px){.stn-hero{padding-top:6.5rem}.stn-grid{grid-template-columns:1fr}.stn-counts{gap:1.5rem}}
  </style>
""")

    out.append(body_open())
    out.append('  <main>\n')

    # Hero
    out.append(f"""    <section class="stn-hero">
      <p class="stn-eyebrow">The Complete Guide</p>
      <h1>Every Neighborhood in South Tampa</h1>
      <p>South Tampa is not one place. It is {total} of them, and the difference between two streets can be four hundred thousand dollars and an entirely different life. Here is what each one is actually like.</p>
      <div class="stn-counts">
        <div class="stn-count"><b>{total}</b><span>Neighborhoods</span></div>
        <div class="stn-count"><b>{len(districts)}</b><span>Districts</span></div>
        <div class="stn-count"><b>40</b><span>Years Selling Here</span></div>
      </div>
    </section>
""")

    # Vibe filter
    chips = "\n          ".join(vibe_chip(v, as_button=True) for v in data["vibes"])
    out.append(f"""    <section class="stn-filters" aria-label="Filter neighborhoods by character">
      <p class="stn-filters-head">What kind of place are you looking for?</p>
      <div class="vibe-chips" id="vibeChips">
          {chips}
      </div>
      <button type="button" class="stn-clear" id="clearVibes" hidden>Clear filters</button>
    </section>

    <p class="stn-empty" id="stnEmpty" hidden>No neighborhoods match that combination. Try clearing a filter.</p>
""")

    # Districts
    for d in districts:
        members = [
            (slug, n) for slug, n in nbhs.items() if n.get("district") == d["id"]
        ]
        if not members:
            continue
        out.append(f"""    <section class="stn-district" data-district="{d['id']}">
      <div class="stn-district-head">
        <h2>{esc(d['name'])}</h2>
        <p>{esc(d['blurb'])}</p>
      </div>
      <div class="stn-grid">
""")
        for slug, n in members:
            tags = "".join(
                vibe_chip(vibes[v]) for v in n.get("vibes", []) if v in vibes
            )
            has_page = bool(n.get("draft") or n.get("kevin"))
            name_html = (
                f'<a href="/neighborhoods/{slug}/">{esc(n["name"])}</a>'
                if has_page
                else esc(n["name"])
            )
            badge = ""
            if n.get("kevin"):
                badge = '<span class="stn-badge reviewed">Kevin&rsquo;s notes</span>'
            elif n.get("is_commercial"):
                badge = '<span class="stn-badge commercial">District</span>'

            zips = n.get("zips") or []
            zip_html = (
                f'<span class="stn-zip">ZIP {", ".join(zips)}</span>' if zips else "<span></span>"
            )
            more = (
                f'<a class="stn-more" href="/neighborhoods/{slug}/">Explore &rarr;</a>'
                if has_page
                else '<span class="stn-soon">Guide in progress</span>'
            )
            vibe_attr = " ".join(n.get("vibes", []))
            out.append(f"""        <article class="stn-card" data-vibes="{vibe_attr}" data-name="{esc(n['name'])}">
          <div class="stn-card-top">
            <h3>{name_html}</h3>
            {badge}
          </div>
          <p class="stn-personality">{esc(n['personality'])}</p>
          <div class="stn-card-tags">{tags}</div>
          <div class="stn-card-foot">{zip_html}{more}</div>
        </article>
""")
        out.append("      </div>\n    </section>\n")

    # Verified South Tampa buyer facts. Every figure here traces to a primary
    # source (City of Tampa, Hillsborough County, the county Planning
    # Commission) and is cited inline. Deliberately excluded: the widely-quoted
    # "Plant High premium" (no methodologically sound study exists — every
    # percentage traces to agent marketing) and volatile YoY medians (recent
    # swings are sales-mix artifacts, not appreciation).
    out.append("""    <section class="stn-facts">
      <div class="stn-facts-inner">
        <p class="stn-eyebrow" style="text-align:left">Before you tour</p>
        <h2>Three things that decide South Tampa deals</h2>
        <p class="stn-facts-lede">Every neighborhood below sits under the same three forces. They matter more to what you will actually pay, and what you can actually do with a house, than any list of amenities.</p>

        <div class="stn-fact">
          <h3>Flood zone is the first question, not the last</h3>
          <p>Most of South Tampa sits in a FEMA Special Flood Hazard Area, where flood insurance is mandatory with a mortgage. After Helene and Milton, the City mailed roughly <strong>1,900 substantial-damage letters</strong> to owners in the flood hazard area. One thing that works in your favor and rarely gets mentioned: Tampa is a <strong>CRS Class 5 community</strong>, which earns a <strong>25% NFIP premium discount</strong> inside flood zones and 10% outside.</p>
          <p class="stn-src">Source: <a href="https://www.tampa.gov/tss-stormwater/info/flood" target="_blank" rel="noopener">City of Tampa Stormwater</a></p>
        </div>

        <div class="stn-fact">
          <h3>The 50% rule is why so many bungalows get torn down</h3>
          <p>If repairs or improvements exceed <strong>50% of the home&rsquo;s value</strong> and it sits in an A or V zone, the house must be brought up to current floodplain code, including elevating above base flood elevation. Two details that catch people: <strong>the value excludes the land</strong>, and <strong>costs accumulate over a rolling 12 months</strong>, so a series of smaller permits triggers it just as surely as one big renovation. On a modest older house, a gut renovation can mandate elevation. That math is why these homes often trade as land.</p>
          <p class="stn-src">Source: <a href="https://hcfl.gov/businesses/hillsgovhub/residential-and-mobile-home-checklists/substantial-damageimprovement-guidelines" target="_blank" rel="noopener">Hillsborough County substantial improvement guidelines</a></p>
        </div>

        <div class="stn-fact">
          <h3>The teardown wave is real and measurable</h3>
          <p>The county Planning Commission puts South Tampa among the two highest-demolition districts in Hillsborough, averaging <strong>231 permitted residential demolitions a year</strong>. Together with Central Tampa it accounts for roughly <strong>88% of the City of Tampa&rsquo;s residential demolitions</strong>, and all ten of the county&rsquo;s highest-demolition ZIP codes are in South and Central Tampa. If you are buying an older home here, know whether you are buying a house or a lot. They price differently.</p>
          <p class="stn-src">Source: <a href="https://planhillsborough.org/residential-demolitions-peaked-in-2021/" target="_blank" rel="noopener">Hillsborough County Planning Commission</a></p>
        </div>
      </div>
    </section>
""")

    # Honest data note
    out.append(f"""    <section class="stn-note">
      <div class="stn-note-inner">
        <h3>How to read this guide</h3>
        <p><strong>The personalities are Kevin&rsquo;s.</strong> Forty years of showing these streets, not a description scraped off a listing site. {reviewed} of {total} neighborhoods have his full written notes so far. He adds one every week, so check back.</p>
        <p><strong>Market figures are ZIP-area context, not appraisals.</strong> South Tampa fits {total} named neighborhoods into about six ZIP codes, so published data cannot tell Golfview from Palma Ceia. Treat the numbers as a starting range and call Kevin for what a specific block is actually doing.</p>
        <p><strong>Boundaries are argued about.</strong> Ask three people where Palma Ceia ends and you will get three answers. These follow City of Tampa planning districts where they exist and local usage where they do not.</p>
      </div>
    </section>
""")

    # Reuse the article CTA pattern
    out.append("""    <section class="blog-cta-magnets">
      <p class="blog-cta-eyebrow">Narrowing it down?</p>
      <h2 class="blog-cta-heading">Two free ways Kevin can help</h2>
      <div class="resource-grid two-up">
        <div class="resource-card">
          <div class="resource-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12l9-9 9 9"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/></svg>
          </div>
          <span class="resource-tag">For Sellers</span>
          <h3>Free Home Valuation Report</h3>
          <p>Find out what your South Tampa home is really worth today. Kevin reviews comparable sales on your actual block, not the ZIP average.</p>
          <ul class="resource-bullets">
            <li>Custom comparative market analysis (CMA)</li>
            <li>7-day neighborhood trend snapshot</li>
            <li>Honest pricing strategy recommendation</li>
          </ul>
          <a href="/home-evaluation-questionnaire/" class="btn-primary" style="align-self:flex-start;margin-top:.5rem;">Get My Home Valuation</a>
        </div>
        <div class="resource-card">
          <div class="resource-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/><line x1="8" y1="7" x2="16" y2="7"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
          </div>
          <span class="resource-tag">For Buyers</span>
          <h3>The Complete Home Buyer&rsquo;s Guide</h3>
          <p>A step-by-step PDF walking you through every part of buying a home in Tampa Bay, from first conversation to closing day.</p>
          <ul class="resource-bullets">
            <li>Pre-approval and financing breakdown</li>
            <li>What to look for at showings</li>
            <li>Offer, inspection, and closing playbook</li>
          </ul>
          <form class="resource-form" data-resource="buyers-guide">
            <input type="hidden" name="site_slug" value="kevin-freel">
            <input type="hidden" name="form_type" value="resource-buyers-guide">
            <input class="hp-field" type="text" name="_honey" tabindex="-1" autocomplete="off">
            <input type="text" name="first_name" placeholder="Your first name" required aria-label="Your first name">
            <input type="email" name="email" placeholder="Your email address" required aria-label="Your email">
            <button type="submit">Download the Guide</button>
            <div class="resource-status" aria-live="polite"></div>
          </form>
        </div>
      </div>
    </section>
""")

    out.append("  </main>\n")

    # Filter behaviour
    out.append("""  <script>
  (function(){
    var chips = Array.prototype.slice.call(document.querySelectorAll('.vibe-chip'));
    var cards = Array.prototype.slice.call(document.querySelectorAll('.stn-card'));
    var sections = Array.prototype.slice.call(document.querySelectorAll('.stn-district'));
    var clear = document.getElementById('clearVibes');
    var empty = document.getElementById('stnEmpty');
    var active = [];

    function apply(){
      var shown = 0;
      cards.forEach(function(c){
        var v = (c.getAttribute('data-vibes') || '').split(' ');
        var ok = active.length === 0 || active.every(function(a){ return v.indexOf(a) !== -1; });
        c.hidden = !ok;
        if (ok) shown++;
      });
      // Hide a district heading when every card under it is filtered out
      sections.forEach(function(s){
        var vis = s.querySelectorAll('.stn-card:not([hidden])').length;
        s.hidden = vis === 0;
      });
      clear.hidden = active.length === 0;
      empty.hidden = shown !== 0;
    }

    chips.forEach(function(chip){
      chip.addEventListener('click', function(){
        var id = chip.getAttribute('data-vibe');
        var i = active.indexOf(id);
        if (i === -1) { active.push(id); chip.setAttribute('aria-pressed','true'); }
        else { active.splice(i,1); chip.setAttribute('aria-pressed','false'); }
        apply();
      });
    });

    clear.addEventListener('click', function(){
      active = [];
      chips.forEach(function(c){ c.setAttribute('aria-pressed','false'); });
      apply();
    });
  })();
  </script>
""")

    out.append(tail())
    return "".join(out)


# ──────────────────────────────────────────────────────────────────────
# Detail page
# ──────────────────────────────────────────────────────────────────────
def build_detail(slug: str, n: dict, data: dict, prices: dict) -> str:
    vibes = {v["id"]: v for v in data["vibes"]}
    district = next((d for d in data["districts"] if d["id"] == n.get("district")), {})
    kevin = n.get("kevin") or {}
    mkt = market_for(n, prices)

    title = f"{n['name']} | South Tampa Neighborhood Guide | Kevin Freel"
    desc = (n.get("personality") or "")[:155]

    out = [head_block(title, desc, f"{SITE}/neighborhoods/{slug}/")]

    out.append("""  <style>
  .nb-hero{max-width:820px;margin:0 auto;padding:8rem clamp(1.25rem,4vw,2rem) 0}
  .nb-back{display:inline-flex;align-items:center;gap:.4rem;font-size:.8125rem;font-weight:600;color:var(--gold);text-decoration:none;margin-bottom:1.25rem}
  .nb-back:hover{text-decoration:underline}
  .nb-back svg{width:14px;height:14px}
  .nb-district{font-size:.75rem;letter-spacing:.16em;text-transform:uppercase;color:var(--text-muted);font-weight:600;margin-bottom:.6rem}
  .nb-hero h1{font-family:var(--font-serif);font-size:clamp(2.1rem,5vw,3.2rem);line-height:1.08;color:var(--navy);margin:0 0 1rem;font-weight:600}
  .nb-lede{font-size:1.125rem;line-height:1.65;color:var(--text-muted);margin:0 0 1.25rem;max-width:62ch}
  .nb-tags{display:flex;flex-wrap:wrap;gap:.4rem;margin-bottom:2.5rem}

  .nb-body{max-width:820px;margin:0 auto;padding:0 clamp(1.25rem,4vw,2rem)}
  .nb-section{margin-bottom:2.75rem}
  .nb-section h2{font-family:var(--font-serif);font-size:1.5rem;color:var(--navy);margin:0 0 .9rem;font-weight:600}
  .nb-section p{color:var(--text);line-height:1.75;margin:0 0 1rem;max-width:68ch}
  .nb-section p:last-child{margin-bottom:0}

  .nb-market{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--border);border:1px solid var(--border);border-radius:10px;overflow:hidden;margin-bottom:.75rem}
  .nb-mstat{background:var(--white);padding:1.15rem 1.25rem}
  .nb-mstat .k{display:block;font-size:.6875rem;letter-spacing:.14em;text-transform:uppercase;color:var(--text-muted);font-weight:600;margin-bottom:.35rem}
  .nb-mstat .v{font-family:var(--font-serif);font-size:1.625rem;color:var(--navy);line-height:1;font-variant-numeric:tabular-nums}
  .nb-mstat .v.pos{color:#2a6d3b}
  .nb-caveat{font-size:.8125rem;color:var(--text-light);line-height:1.6;margin:0}

  .nb-byline{font-size:.875rem;color:var(--text-muted);font-style:italic;margin:0;padding-top:.5rem;border-top:1px solid var(--border)}
  .nb-byline-box{background:var(--bg-alt);border:1px dashed var(--border);border-radius:10px;padding:1.5rem 1.75rem;text-align:center}
  .nb-byline-box p{color:var(--text-muted);font-size:.875rem;line-height:1.65;margin:0 auto 1.15rem;max-width:60ch}

  .nb-nearby{display:flex;flex-wrap:wrap;gap:.5rem}
  .nb-nearby a{font-size:.8125rem;font-weight:500;color:var(--navy);background:var(--bg-alt);border:1px solid var(--border);border-radius:999px;padding:.4rem .85rem;text-decoration:none;transition:all .18s}
  .nb-nearby a:hover{border-color:var(--gold);color:var(--gold)}
  @media(max-width:640px){.nb-hero{padding-top:6.5rem}}
  </style>
""")

    out.append(body_open())
    out.append("  <main>\n")

    tags = "".join(vibe_chip(vibes[v]) for v in n.get("vibes", []) if v in vibes)
    out.append(f"""    <section class="nb-hero">
      <a href="/south-tampa-neighborhoods/" class="nb-back">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
        All South Tampa neighborhoods
      </a>
      <p class="nb-district">{esc(district.get('name',''))}</p>
      <h1>{esc(n['name'])}</h1>
      <p class="nb-lede">{esc(n['personality'])}</p>
      <div class="nb-tags">{tags}</div>
    </section>

    <div class="nb-body">
""")

    # Market snapshot — real data only
    if mkt:
        trend = ""
        if mkt.get("trend_pct_5yr") is not None:
            trend = f"""        <div class="nb-mstat"><span class="k">5-Year Trend</span><span class="v pos">+{mkt['trend_pct_5yr']}%</span></div>
"""
        straddle = ""
        if len(mkt["zips"]) > 1:
            straddle = (
                f" {esc(n['name'])} straddles both ZIPs, so this averages them."
            )
        soft = ""
        if mkt.get("zip_confidence") == "low":
            soft = (
                " Worth knowing: this is an informal name with no official City"
                " boundary, so even the ZIP is approximate here."
            )
        out.append(f"""      <section class="nb-section">
        <h2>What the market looks like here</h2>
        <div class="nb-market">
          <div class="nb-mstat"><span class="k">Median Value</span><span class="v">${mkt['median_price']:,}</span></div>
{trend}          <div class="nb-mstat"><span class="k">ZIP{"s" if len(mkt['zips'])>1 else ""}</span><span class="v">{", ".join(mkt['zips'])}</span></div>
        </div>
        <p class="nb-caveat">Zillow Home Value Index for ZIP {", ".join(mkt['zips'])}, updated {esc(mkt.get('as_of') or 'monthly')}. This is <strong>area context, not a valuation</strong>.{straddle} In South Tampa a single block can swing the number substantially, and this ZIP covers several other neighborhoods too.{soft} For what your specific street is doing, <a href="/home-evaluation-questionnaire/">ask Kevin for a CMA</a>.</p>
      </section>
""")

    # Body copy. Kevin's reviewed words always win and carry his byline. The
    # baseline framing publishes under neutral headings with NO byline, because
    # attributing AI-written copy to a licensed agent would be dishonest.
    draft = n.get("draft") or {}
    reviewed = bool(kevin.get("take"))

    def paras_of(text: str) -> str:
        return "\n        ".join(
            f"<p>{esc(p)}</p>" for p in text.split("\n\n") if p.strip()
        )

    SECTIONS = [
        # (key, heading when Kevin wrote it, heading for the baseline framing)
        ("take", "Kevin&rsquo;s take", f"About {esc(n['name'])}"),
        ("expect", "What to expect", "What to expect"),
        ("investment", "The investment angle", "The investment angle"),
    ]

    for key, kevin_heading, neutral_heading in SECTIONS:
        text = kevin.get(key) or draft.get(key)
        if not text:
            continue
        is_kevin = bool(kevin.get(key))
        out.append(f"""      <section class="nb-section">
        <h2>{kevin_heading if is_kevin else neutral_heading}</h2>
        {paras_of(text)}
      </section>
""")

    best = kevin.get("best_for") or draft.get("best_for")
    if best:
        out.append(f"""      <section class="nb-section">
        <div class="nbh-best-for"><strong>Best for:</strong> {esc(best)}</div>
      </section>
""")

    # Say plainly whose words these are. Kevin can review partially (he might
    # rewrite the take but leave the market sections alone), so the byline must
    # claim exactly what he actually wrote and no more.
    narrative = ("take", "expect", "investment")
    his = [k for k in narrative if kevin.get(k)]
    theirs = [k for k in narrative if not kevin.get(k) and draft.get(k)]

    if his and not theirs:
        out.append("""      <section class="nb-section">
        <p class="nb-byline">Written by Kevin Freel, selling South Tampa since 1985.</p>
      </section>
""")
    elif his:
        out.append("""      <section class="nb-section">
        <p class="nb-byline">The sections above under Kevin&rsquo;s name are his own words. The rest is the guide&rsquo;s research summary, which he is still working through.</p>
      </section>
""")
    else:
        out.append(f"""      <section class="nb-section">
        <div class="nb-byline-box">
          <p>This profile is the guide&rsquo;s research summary, not Kevin&rsquo;s personal write-up. He is rewriting these one at a time in his own words, from forty years of actually selling these streets. {esc(n['name'])} is in the queue.</p>
          <a href="/contact/" class="btn-primary">Ask Kevin about {esc(n['name'])}</a>
        </div>
      </section>
""")

    # Nearby
    siblings = [
        (s, x)
        for s, x in data["neighborhoods"].items()
        if x.get("district") == n.get("district") and s != slug
    ][:8]
    if siblings:
        links = "\n          ".join(
            (
                f'<a href="/neighborhoods/{s}/">{esc(x["name"])}</a>'
                if (x.get("draft") or x.get("kevin"))
                else f'<a href="/south-tampa-neighborhoods/#{s}">{esc(x["name"])}</a>'
            )
            for s, x in siblings
        )
        out.append(f"""      <section class="nb-section">
        <h2>Nearby in {esc(district.get('name',''))}</h2>
        <div class="nb-nearby">
          {links}
        </div>
      </section>
""")

    out.append("    </div>\n")

    # CTA
    out.append(f"""    <section class="blog-cta-magnets">
      <p class="blog-cta-eyebrow">Thinking about {esc(n['name'])}?</p>
      <h2 class="blog-cta-heading">Two free ways Kevin can help</h2>
      <div class="resource-grid two-up">
        <div class="resource-card">
          <div class="resource-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12l9-9 9 9"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/></svg>
          </div>
          <span class="resource-tag">For Sellers</span>
          <h3>Free Home Valuation Report</h3>
          <p>Find out what your {esc(n['name'])} home is really worth today. Kevin reviews comparable sales on your actual block, not the ZIP average.</p>
          <ul class="resource-bullets">
            <li>Custom comparative market analysis (CMA)</li>
            <li>7-day neighborhood trend snapshot</li>
            <li>Honest pricing strategy recommendation</li>
          </ul>
          <a href="/home-evaluation-questionnaire/" class="btn-primary" style="align-self:flex-start;margin-top:.5rem;">Get My Home Valuation</a>
        </div>
        <div class="resource-card">
          <div class="resource-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/><line x1="8" y1="7" x2="16" y2="7"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
          </div>
          <span class="resource-tag">For Buyers</span>
          <h3>The Complete Home Buyer&rsquo;s Guide</h3>
          <p>A step-by-step PDF walking you through every part of buying a home in Tampa Bay, from first conversation to closing day.</p>
          <ul class="resource-bullets">
            <li>Pre-approval and financing breakdown</li>
            <li>What to look for at showings</li>
            <li>Offer, inspection, and closing playbook</li>
          </ul>
          <form class="resource-form" data-resource="buyers-guide">
            <input type="hidden" name="site_slug" value="kevin-freel">
            <input type="hidden" name="form_type" value="resource-buyers-guide">
            <input class="hp-field" type="text" name="_honey" tabindex="-1" autocomplete="off">
            <input type="text" name="first_name" placeholder="Your first name" required aria-label="Your first name">
            <input type="email" name="email" placeholder="Your email address" required aria-label="Your email">
            <button type="submit">Download the Guide</button>
            <div class="resource-status" aria-live="polite"></div>
          </form>
        </div>
      </div>
    </section>
""")

    out.append("  </main>\n")
    out.append(tail())
    return "".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    data = json.loads(DATA.read_text())
    prices = json.loads(PRICES.read_text()) if PRICES.exists() else {}

    OUT_DIR.mkdir(exist_ok=True)

    written = []

    catalog = build_catalog(data, prices)
    if not args.dry_run:
        OUT_CATALOG.write_text(catalog)
    written.append(str(OUT_CATALOG.relative_to(ROOT)))

    # Every neighborhood with published content gets its own page.
    for slug, n in data["neighborhoods"].items():
        if not (n.get("draft") or n.get("kevin")):
            continue
        page = build_detail(slug, n, data, prices)
        target = OUT_DIR / f"{slug}.html"
        if not args.dry_run:
            target.write_text(page)
        written.append(str(target.relative_to(ROOT)))

    verb = "Would write" if args.dry_run else "Wrote"
    print(f"{verb} {len(written)} file(s):")
    for w in written:
        print(f"  {w}")

    reviewed = sum(1 for n in data["neighborhoods"].values() if n.get("kevin"))
    print(
        f"\n{reviewed}/{len(data['neighborhoods'])} neighborhoods have Kevin's written notes."
    )


if __name__ == "__main__":
    main()
