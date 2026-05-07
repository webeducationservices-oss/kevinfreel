#!/usr/bin/env python3
"""
build_partials.py — Propagate the global nav and footer partials into every HTML page.

Run this whenever you edit `partials/nav.html` or `partials/footer.html`.
The script is idempotent: running twice produces the same output.

Strategy:
- Every HTML file's nav block is wrapped between <!-- BEGIN_NAV --> and <!-- END_NAV -->.
- Every HTML file's footer block is wrapped between <!-- BEGIN_FOOTER --> and <!-- END_FOOTER -->.
- On first run, the script also recognises the legacy markup (the `<!-- ── NAV ── -->`
  comment before <nav> + the trailing mobile menu div, and the `<!-- ── FOOTER ── -->`
  comment before <footer>) and replaces it with the marker-bracketed partial.
- thank-you.html and 404.html (which use `.message-page` and don't have a standard nav/footer)
  are skipped automatically because they don't match either pattern.

Usage:
    python3 scripts/build_partials.py            # update everything
    python3 scripts/build_partials.py --dry-run  # report what would change
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_partial(name: str) -> str:
    return (ROOT / "partials" / f"{name}.html").read_text().strip()


def wrap(name: str, body: str) -> str:
    return f"<!-- BEGIN_{name.upper()} -->\n{body}\n  <!-- END_{name.upper()} -->"


def block_pattern(name: str) -> re.Pattern[str]:
    return re.compile(
        rf"<!-- BEGIN_{name.upper()} -->.*?<!-- END_{name.upper()} -->",
        re.DOTALL,
    )


# Legacy patterns — what existed before this build system.
# The nav block: from the `<!-- ── NAV ── -->` decoration comment to the closing
# </div> of the mobile-menu wrapper. We don't use \b after `mobile-menu"` because
# `"` is not a word character so there's no word boundary against a following space.
LEGACY_NAV_RE = re.compile(
    r'<!-- ── NAV ── -->.*?<div id="mobile-menu".*?</div>',
    re.DOTALL,
)

# The footer block: from `<!-- ── FOOTER ── -->` comment to the end of the </footer> tag
LEGACY_FOOTER_RE = re.compile(
    r'<!-- ── FOOTER ── -->\s*<footer\b.*?</footer>',
    re.DOTALL,
)


def process_file(path: Path, nav_block: str, footer_block: str) -> str | None:
    """Returns 'updated' / 'no-change' / 'skipped' and writes back if changed."""
    raw = path.read_text()
    out = raw

    # NAV — prefer marker pattern, fall back to legacy
    nav_marker = block_pattern("nav")
    if nav_marker.search(out):
        out = nav_marker.sub(nav_block, out, count=1)
    elif LEGACY_NAV_RE.search(out):
        out = LEGACY_NAV_RE.sub(nav_block, out, count=1)
    # else: file has no nav (404, thank-you, etc.) — skip nav update silently

    # FOOTER — same approach
    footer_marker = block_pattern("footer")
    if footer_marker.search(out):
        out = footer_marker.sub(footer_block, out, count=1)
    elif LEGACY_FOOTER_RE.search(out):
        out = LEGACY_FOOTER_RE.sub(footer_block, out, count=1)
    # else: skip silently

    if out == raw:
        return "no-change"

    path.write_text(out)
    return "updated"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    nav_partial = load_partial("nav")
    footer_partial = load_partial("footer")

    nav_block = wrap("nav", nav_partial)
    footer_block = wrap("footer", footer_partial)

    targets = (
        sorted(ROOT.glob("*.html"))
        + sorted((ROOT / "blog").glob("*.html"))
        + sorted((ROOT / "listings").glob("*.html"))
    )

    updated = 0
    no_change = 0
    for path in targets:
        if args.dry_run:
            raw = path.read_text()
            nav_marker = block_pattern("nav")
            if not nav_marker.search(raw) and not LEGACY_NAV_RE.search(raw):
                # Has no nav at all — skipped
                continue
            print(f"would update: {path.relative_to(ROOT)}")
            continue

        result = process_file(path, nav_block, footer_block)
        if result == "updated":
            updated += 1
        elif result == "no-change":
            no_change += 1

    if not args.dry_run:
        print(f"Updated: {updated}")
        print(f"No change: {no_change}")
        print(f"Total scanned: {len(targets)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
