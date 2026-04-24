#!/usr/bin/env python3
"""
sync_listings.py — Kevin Freel daily listings pipeline.

Scrapes Kevin's active listings from Century 21, optimizes hero photos to WebP,
and regenerates the /listings page + a homepage "Featured Active Listings" block.

Safe re-run: idempotent. On scrape failure, leaves existing files alone.

Run:
    python3 scripts/sync_listings.py
"""

from __future__ import annotations

import hashlib
import html
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from PIL import Image

# ────────────────────────────────────────────────────────────────────
#  Paths (absolute, relative to repo root)
# ────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = REPO_ROOT / "images" / "listings"
LISTINGS_DIR = REPO_ROOT / "listings"
DATA_FILE = REPO_ROOT / "listings.json"
LISTINGS_HTML = LISTINGS_DIR / "index.html"
HOMEPAGE_HTML = REPO_ROOT / "index.html"

C21_PRIMARY = (
    "https://www.century21.com/agent/detail/fl/tampa/agents/kevin-freel/"
    "aid-P00200000FDdqjdTeyq4WAT7ZsX9W1eWQVF2WqrF"
)
C21_FALLBACK = "https://www.century21.com/real-estate/kevin-freel/P25220973/"
C21_BASE = "https://www.century21.com"

# C21 serves a React SPA loading shell to normal browsers — only bots
# (e.g. Googlebot) get the server-rendered HTML with listing data. Using a
# Googlebot UA is required to get scrapeable content.
USER_AGENT = (
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
)

# Track download bytes for reporting
_stats = {"bytes_downloaded": 0, "photos_downloaded": 0, "photos_cached": 0}


# ────────────────────────────────────────────────────────────────────
#  Fetch helpers
# ────────────────────────────────────────────────────────────────────

def fetch(url: str, *, timeout: int = 30) -> bytes:
    """Fetch a URL with browser-like headers. Returns bytes."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "identity",  # avoid gzip — keep it simple
            "Connection": "close",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_agent_page() -> str:
    """
    Fetch the agent page. Try fallback URL (server-rendered) first since the
    /agent/detail/ primary URL is a client-side React SPA and returns a
    loading shell without listings.
    """
    attempts: list[str] = []
    for url in (C21_FALLBACK, C21_PRIMARY):
        try:
            data = fetch(url, timeout=45)
            if data:
                text = data.decode("utf-8", errors="replace")
                attempts.append(f"{url}: {len(text):,} chars")
                # Is this an SPA shell? Detect by absence of listings markers.
                if (
                    '<div id="root"></div>' in text
                    and "C21 loading" in text
                ):
                    print(f"[warn] {url} returned SPA shell, trying next",
                          file=sys.stderr)
                    continue
                return text
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            print(f"[warn] fetch failed for {url}: {exc}", file=sys.stderr)
    raise RuntimeError(
        "could not fetch a usable C21 page. Attempts: " + "; ".join(attempts)
    )


# ────────────────────────────────────────────────────────────────────
#  Parse helpers
# ────────────────────────────────────────────────────────────────────

# MLS numbers are 1-3 uppercase letters + 6-10 digits with a clean boundary.
# C21 property IDs (P00800000...) start with P and are followed by MORE
# alphanumerics — use a negative-lookahead to skip them.
_MLS_RE = re.compile(r"\b([A-Z]{1,3}\d{6,10})(?![A-Za-z0-9])")

# C21 "listing ID" (property ID) used inside detail URLs: /lid-P008XXXXXX...
_LID_RE = re.compile(r"/lid-(P\d+[A-Za-z0-9]+)")
_PRICE_RE = re.compile(r"\$[\d,]+")
_ACRES_RE = re.compile(r"([\d,.]+)\s*Acres?", re.IGNORECASE)
_SQFT_RE = re.compile(r"([\d,]+)\s*sq\.?\s*ft\.?", re.IGNORECASE)
_BEDS_RE = re.compile(r"(\d+)\s*(?:bed|br|bd)\b", re.IGNORECASE)
_BATHS_RE = re.compile(r"([\d.]+)\s*(?:bath|ba)\b", re.IGNORECASE)
_ZIP_RE = re.compile(r"\b(\d{5})(?:-\d{4})?\b")


def _abs_url(url: str) -> str:
    """Make URL absolute against century21.com."""
    if not url:
        return url
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return C21_BASE + url
    if url.startswith("http"):
        return url
    return C21_BASE + "/" + url.lstrip("/")


def _clean_text(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()


def _extract_mls_from_url(url: str) -> str | None:
    """Pull TB8497958-style MLS# out of a photo URL or listing URL."""
    if not url:
        return None
    m = _MLS_RE.search(url)
    return m.group(0) if m else None


def _extract_lid_from_url(url: str) -> str | None:
    """Pull the C21 listing ID (P008...) out of a detail URL."""
    if not url:
        return None
    m = _LID_RE.search(url)
    return m.group(1) if m else None


def _parse_address(block_text: str) -> tuple[str, str, str, str]:
    """
    Parse a combined address string like:
        "123 Main St, Tampa, FL 33602"
    Returns (street, city, state, zip). Any part may be empty.
    """
    text = _clean_text(block_text)
    if not text:
        return ("", "", "", "")

    # Try to pull zip first
    zip_m = _ZIP_RE.search(text)
    zip_code = zip_m.group(1) if zip_m else ""

    # Split on commas
    parts = [p.strip() for p in text.split(",") if p.strip()]
    street = parts[0] if parts else ""
    city = parts[1] if len(parts) >= 2 else ""
    state_zip = parts[2] if len(parts) >= 3 else ""

    state = ""
    if state_zip:
        state_m = re.match(r"([A-Z]{2})", state_zip.strip())
        if state_m:
            state = state_m.group(1)
    if not state:
        # look anywhere in the trailing chunk
        tail = " ".join(parts[2:]) if len(parts) > 2 else text
        sm = re.search(r"\b([A-Z]{2})\b\s*\d{5}", tail)
        if sm:
            state = sm.group(1)

    return (street, city, state, zip_code)


def _parse_meta(meta_text: str) -> tuple[int, int, str]:
    """
    Parse a meta blurb like:
        "3 Beds · 2 Baths · 1,848 sq. ft."
        "5.06 Acres"
    Returns (beds, baths, sqft_or_acres).
    """
    text = _clean_text(meta_text)
    beds = 0
    baths = 0
    size = ""

    beds_m = _BEDS_RE.search(text)
    if beds_m:
        try:
            beds = int(beds_m.group(1))
        except ValueError:
            beds = 0

    baths_m = _BATHS_RE.search(text)
    if baths_m:
        try:
            # Round half baths down (C21 uses 2.5 = 2 full + 1 half sometimes)
            baths = int(float(baths_m.group(1)))
        except ValueError:
            baths = 0

    acres_m = _ACRES_RE.search(text)
    sqft_m = _SQFT_RE.search(text)
    if acres_m:
        size = f"{acres_m.group(1)} Acres"
    elif sqft_m:
        size = f"{sqft_m.group(1)} sq. ft."

    return (beds, baths, size)


def parse_listings(html_text: str) -> list[dict[str, Any]]:
    """
    Parse the agent HTML for listings.

    Strategy:
    1. JSON-LD ItemList in <script type="application/ld+json"> — structured
       data for price, address, beds, baths, sqft, image, URL.
    2. DOM cards (a.single-property-info) — authoritative for MLS#, status,
       lot acres. The image URL's embedded identifier does NOT always match
       the MLS, so we rely on the DOM's explicit "MLS# ..." label.

    Records merged by C21 listing ID (the /lid-P... segment of the URL).

    Returns only Active listings sorted by price desc.
    """
    by_lid: dict[str, dict[str, Any]] = {}
    soup = BeautifulSoup(html_text, "html.parser")

    # ── Strategy 1: JSON-LD ItemList ──
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "{}")
        except (ValueError, TypeError):
            continue
        graphs: list[Any] = []
        if isinstance(data, dict):
            graphs = data["@graph"] if isinstance(data.get("@graph"), list) else [data]
        elif isinstance(data, list):
            graphs = data
        for g in graphs:
            if not isinstance(g, dict) or g.get("@type") != "ItemList":
                continue
            for e in g.get("itemListElement", []) or []:
                entry = _extract_listing_from_jsonld_item(e)
                if not entry:
                    continue
                lid = _extract_lid_from_url(entry.get("c21_url", ""))
                if lid:
                    by_lid[lid] = entry

    # ── Strategy 2: DOM cards ──
    for card in soup.select(
        "a.single-property-info, .any-listing-card, .listing-card-container"
    ):
        dom_entry = _extract_listing_from_dom(card)
        if not dom_entry:
            continue
        lid = _extract_lid_from_url(dom_entry.get("c21_url", ""))
        if not lid:
            continue
        if lid in by_lid:
            target = by_lid[lid]
            # DOM wins on MLS# (authoritative) + status
            if dom_entry.get("mls_number"):
                target["mls_number"] = dom_entry["mls_number"]
            if dom_entry.get("status"):
                target["status"] = dom_entry["status"]
            # Acres / sqft — fill in or override w/ DOM value when JSON-LD blank
            if dom_entry.get("sqft_or_acres") and not target.get("sqft_or_acres"):
                target["sqft_or_acres"] = dom_entry["sqft_or_acres"]
            if "acre" in dom_entry.get("sqft_or_acres", "").lower():
                target["sqft_or_acres"] = dom_entry["sqft_or_acres"]
            # Photo fallback
            if not target.get("hero_photo_url") and dom_entry.get("hero_photo_url"):
                target["hero_photo_url"] = dom_entry["hero_photo_url"]
        else:
            by_lid[lid] = dom_entry

    # ── Final filter + sort ──
    out: list[dict[str, Any]] = []
    for entry in by_lid.values():
        if entry.get("status", "Active") != "Active":
            continue
        if not entry.get("price"):
            continue
        if not entry.get("mls_number"):
            continue
        # If sqft_or_acres is still empty but we have a numeric floorSize, format it
        if not entry.get("sqft_or_acres"):
            sqft_val = entry.pop("_sqft_value", None)
            if sqft_val:
                try:
                    entry["sqft_or_acres"] = f"{int(sqft_val):,} sq. ft."
                except (TypeError, ValueError):
                    pass
        entry.pop("_sqft_value", None)

        # Photo fallback: synthesize C21 image URL from MLS if missing
        if not entry.get("hero_photo_url"):
            mls = entry["mls_number"]
            if len(mls) >= 8 and mls[:2].isalpha():
                prefix = mls[:2]
                digits = mls[2:]
                groups = [digits[i:i + 2] for i in range(0, len(digits), 2)]
                path = "/".join(groups)
                entry["hero_photo_url"] = (
                    f"https://images-listings.century21.com/MFRMLS/{prefix}/"
                    f"{path}/_P/{mls}_P00.jpg"
                )
            else:
                continue

        out.append(entry)

    out.sort(key=lambda e: e.get("price", 0), reverse=True)
    return out


def _extract_listing_from_jsonld_item(item: dict[str, Any]) -> dict[str, Any] | None:
    """Extract a listing dict from one entry in an ItemList."""
    if not isinstance(item, dict):
        return None

    # Sometimes the entry wraps its data under 'item'
    if "item" in item and isinstance(item["item"], dict):
        item = item["item"]

    url = item.get("url") or ""
    name = item.get("name") or ""
    image = item.get("image") or ""
    if isinstance(image, list):
        image = image[0] if image else ""
    if isinstance(image, dict):
        image = image.get("url") or image.get("contentUrl") or ""

    # price can live at item.offers.price (list or dict)
    offers = item.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    price_raw = offers.get("price") if isinstance(offers, dict) else None
    if not price_raw:
        price_raw = item.get("price")
    try:
        price = int(re.sub(r"[^\d]", "", str(price_raw))) if price_raw else 0
    except (TypeError, ValueError):
        price = 0
    if not price:
        return None

    offer_url = offers.get("url") if isinstance(offers, dict) else ""
    detail_url = offer_url or url

    # mainEntity has the rich property details
    main = item.get("mainEntity") or {}
    if not isinstance(main, dict):
        main = {}

    # Address
    address_obj = main.get("address") or item.get("address") or {}
    if isinstance(address_obj, dict):
        street = address_obj.get("streetAddress") or ""
        city = address_obj.get("addressLocality") or ""
        state = address_obj.get("addressRegion") or ""
        zip_code = address_obj.get("postalCode") or ""
    else:
        street, city, state, zip_code = _parse_address(str(address_obj))

    # Fall back to name (e.g. "2204 N Central Avenue #1, TAMPA, FL 33602")
    if not street and name and "," in name:
        street, city, state, zip_code = _parse_address(name)
    # Title-case the city (C21 uses ALL CAPS)
    if city and city.isupper():
        city = city.title()
    if not state:
        state = "FL"

    # Beds / baths
    try:
        beds = int(main.get("numberOfBedrooms") or 0)
    except (TypeError, ValueError):
        beds = 0
    baths_raw = (
        main.get("numberOfBathroomsTotal")
        or main.get("numberOfFullBathrooms")
        or main.get("numberOfBathrooms")
        or 0
    )
    try:
        baths = int(float(baths_raw)) if baths_raw else 0
    except (TypeError, ValueError):
        baths = 0

    # Floor size / lot size
    size = ""
    sqft_value: Any = None
    fs = main.get("floorSize") or {}
    if isinstance(fs, dict) and fs.get("value"):
        sqft_value = fs["value"]
        try:
            size = f"{int(fs['value']):,} sq. ft."
        except (TypeError, ValueError):
            pass
    if not size:
        ls = main.get("lotSize") or {}
        if isinstance(ls, dict) and ls.get("value"):
            size = f"{ls['value']} Acres"

    # The image URL contains an MLS-like token but it's the CoreLogic listing
    # asset ID, not the real MLS number. We leave mls_number empty here and
    # let the DOM parser (which reads "MLS# XXX" text) populate it.
    mls = _extract_mls_from_url(str(image)) or ""

    return {
        "address": street,
        "city": city,
        "state": state,
        "zip": zip_code,
        "price_display": f"${price:,}",
        "price": price,
        "beds": beds,
        "baths": baths,
        "sqft_or_acres": size,
        "mls_number": mls,
        "status": "Active",
        "c21_url": _abs_url(detail_url),
        "hero_photo_url": _abs_url(str(image)) if image else "",
        "_sqft_value": sqft_value,
    }


def _extract_listing_from_dom(card: Any) -> dict[str, Any] | None:
    """Parse a DOM .any-listing-card element into a listing dict."""
    # Status (skip pending/sold)
    status_el = card.select_one(".status-value")
    status = _clean_text(status_el.get_text(" ", strip=True)) if status_el else "Active"
    status = status.split()[0] if status else "Active"

    # Price
    price_el = card.select_one(".price")
    price_display = _clean_text(price_el.get_text(" ", strip=True)) if price_el else ""
    price_m = re.search(r"\$[\d,]+", price_display)
    if not price_m:
        return None
    price = int(re.sub(r"[^\d]", "", price_m.group(0)))

    # MLS
    mls_el = card.select_one(".mls-number")
    mls_text = _clean_text(mls_el.get_text(" ", strip=True)) if mls_el else ""
    mls_m = _MLS_RE.search(mls_text)
    mls = mls_m.group(0) if mls_m else ""

    # Address
    addr_el = card.select_one(".address")
    addr_text = ""
    if addr_el:
        addr_text = addr_el.get("title") or addr_el.get_text(" ", strip=True)
    street, city, state, zip_code = _parse_address(addr_text)
    if city and city.isupper():
        city = city.title()

    # Details line: either "3 beds · 2 baths · 1,848 sq. ft." or "5.06 Acres"
    details_el = card.select_one(".property-details-line")
    beds = baths = 0
    size = ""
    if details_el:
        bed_el = details_el.select_one(".bed-info")
        bath_el = details_el.select_one(".bath-info")
        sqft_el = details_el.select_one(".sq-ft-info")
        if bed_el:
            m = re.search(r"\d+", bed_el.get_text(" ", strip=True))
            beds = int(m.group(0)) if m else 0
        if bath_el:
            m = re.search(r"[\d.]+", bath_el.get_text(" ", strip=True))
            baths = int(float(m.group(0))) if m else 0
        if sqft_el:
            size = _clean_text(sqft_el.get_text(" ", strip=True))
        elif not bed_el and not bath_el:
            # Probably a lot: the single <span> inside contains "X Acres"
            size = _clean_text(details_el.get_text(" ", strip=True))

    # Image
    img_el = card.select_one(".property-img") or card.select_one("img")
    hero = ""
    if img_el:
        hero = (
            img_el.get("src")
            or img_el.get("data-src")
            or img_el.get("data-lazy-src")
            or ""
        )
        # Strip width= / format= query params — we want the original
        if hero:
            hero = re.sub(r"\?.*$", "", hero)

    # Detail URL
    a_el = card if card.name == "a" else card.find("a", href=True)
    href = ""
    if a_el and a_el.get("href"):
        href = a_el["href"].strip()

    if not mls:
        mls = _extract_mls_from_url(hero) or _extract_mls_from_url(href) or ""
    if not mls:
        return None

    return {
        "address": street,
        "city": city,
        "state": state or "FL",
        "zip": zip_code,
        "price_display": f"${price:,}",
        "price": price,
        "beds": beds,
        "baths": baths,
        "sqft_or_acres": size,
        "mls_number": mls,
        "status": status or "Active",
        "c21_url": _abs_url(href),
        "hero_photo_url": _abs_url(hero) if hero else "",
    }


# ────────────────────────────────────────────────────────────────────
#  Photo download + WebP optimization
# ────────────────────────────────────────────────────────────────────

def optimize_photo(mls: str, photo_url: str) -> tuple[Path | None, Path | None]:
    """
    Download a hero photo, save as 1200px-wide WebP (q72) + 480px thumbnail.
    Skip if both already exist.
    Returns (main_path, thumb_path), either/both may be None on failure.
    """
    if not photo_url:
        return (None, None)

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    main_path = IMAGES_DIR / f"{mls}.webp"
    thumb_path = IMAGES_DIR / f"{mls}-sm.webp"

    if main_path.exists() and thumb_path.exists():
        _stats["photos_cached"] += 1
        return (main_path, thumb_path)

    try:
        data = fetch(photo_url, timeout=45)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        print(f"[warn] photo download failed for {mls} ({photo_url}): {exc}",
              file=sys.stderr)
        return (None, None)

    _stats["bytes_downloaded"] += len(data)
    _stats["photos_downloaded"] += 1

    try:
        img = Image.open(io.BytesIO(data))
        # Convert to RGB — some C21 photos are CMYK / palette
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        elif img.mode == "RGBA":
            # Flatten alpha onto white so WebP stays compact
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            img = bg

        # Main (1200px wide, preserve aspect)
        main = img.copy()
        main.thumbnail((1200, 1200), Image.LANCZOS)
        main.save(main_path, format="WEBP", quality=72, method=6)

        # Thumbnail (480px wide)
        thumb = img.copy()
        thumb.thumbnail((480, 480), Image.LANCZOS)
        thumb.save(thumb_path, format="WEBP", quality=72, method=6)
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] photo optimize failed for {mls}: {exc}", file=sys.stderr)
        return (None, None)

    return (main_path, thumb_path)


# ────────────────────────────────────────────────────────────────────
#  Listings page + homepage injection
# ────────────────────────────────────────────────────────────────────

NAV_HTML = """  <!-- ── NAV ── -->
  <nav class="nav scrolled" aria-label="Main navigation">
    <div class="nav-inner">
      <a href="/" class="nav-logo">KEVIN <span>FREEL</span></a>
      <ul class="nav-links">
        <li><a href="/search">Search</a></li>
        <li><a href="/about">About</a></li>
        <li><a href="/resources">Resources</a></li>
        <li><a href="/sellers">Sellers</a></li>
        <li><a href="/buyers">Buyers</a></li>
        <li><a href="/photography">Photography</a></li>
        <li><a href="/blog">Blog</a></li>
        <li><a href="/contact">Contact</a></li>
        <li>
          <a href="tel:7274108599" class="nav-cta">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z"/></svg>
            727-410-8599
          </a>
        </li>
      </ul>
      <button id="menu-btn" aria-label="Open menu" aria-expanded="false">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
      </button>
    </div>
  </nav>

  <!-- ── Mobile Menu ── -->
  <div id="menu-overlay" class="menu-overlay"></div>
  <div id="mobile-menu" class="mobile-menu" aria-label="Mobile navigation">
    <a href="/">Home</a>
    <a href="/search">Search</a>
    <a href="/about">About</a>
    <a href="/resources">Resources</a>
    <a href="/sellers">Sellers</a>
    <a href="/buyers">Buyers</a>
    <a href="/photography">Photography</a>
    <a href="/blog">Blog</a>
    <a href="/contact">Contact</a>
    <a href="tel:7274108599" class="nav-cta">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z"/></svg>
      727-410-8599
    </a>
  </div>
"""

FOOTER_HTML = """  <!-- ── FOOTER ── -->
  <footer class="footer">
    <div class="footer-inner">
      <a href="/" class="footer-logo">KEVIN <span>FREEL</span></a>
      <p class="footer-copy">&copy; 2026 Kevin Freel Real Estate. All rights reserved.</p>
      <div class="footer-social">
        <a href="https://www.facebook.com/SellingTampa" target="_blank" rel="noopener noreferrer" aria-label="Facebook">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>
        </a>
        <a href="https://www.instagram.com/kevinsellstampabay/" target="_blank" rel="noopener noreferrer" aria-label="Instagram">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/></svg>
        </a>
      </div>
    </div>
  </footer>
"""


def _format_meta_line(listing: dict[str, Any]) -> str:
    """Build the 'beds · baths · sqft' / 'Lot: X acres' line."""
    beds = listing.get("beds", 0) or 0
    baths = listing.get("baths", 0) or 0
    size = listing.get("sqft_or_acres", "") or ""
    is_lot = (beds == 0 and baths == 0) or "acre" in size.lower()

    if is_lot and size:
        return f"Lot: {html.escape(size)}"
    if is_lot:
        return "Vacant Land"

    parts = []
    if beds:
        parts.append(f"{beds} {'Bed' if beds == 1 else 'Beds'}")
    if baths:
        parts.append(f"{baths} {'Bath' if baths == 1 else 'Baths'}")
    if size:
        parts.append(html.escape(size))
    return " &middot; ".join(parts) if parts else "—"


def _listing_card_html(listing: dict[str, Any], *, thumb: bool = False) -> str:
    """Render a single listing card. `thumb` uses the -sm.webp variant."""
    mls = listing["mls_number"]
    image_file = f"/images/listings/{mls}{'-sm' if thumb else ''}.webp"
    has_local = (IMAGES_DIR / f"{mls}{'-sm' if thumb else ''}.webp").exists()
    image_src = image_file if has_local else listing.get("hero_photo_url", "")

    address = html.escape(listing.get("address", "") or "Address available on request")
    city = html.escape(listing.get("city", ""))
    state = html.escape(listing.get("state", "FL"))
    zip_code = html.escape(listing.get("zip", ""))
    location_line = ", ".join([p for p in (city, f"{state} {zip_code}".strip()) if p])

    price_display = html.escape(listing.get("price_display", ""))
    meta_line = _format_meta_line(listing)
    c21_url = html.escape(listing.get("c21_url", "") or "#")
    alt_text = html.escape(f"{address}, {city}, {state}")

    return f"""          <article class="listing-card">
            <div class="listing-card-image">
              <span class="listing-badge">Active</span>
              <img src="{image_src}" alt="{alt_text}" loading="lazy" width="1200" height="900">
            </div>
            <div class="listing-card-body">
              <div class="listing-price">{price_display}</div>
              <h3 class="listing-address">{address}</h3>
              <p class="listing-location">{location_line}</p>
              <p class="listing-meta">{meta_line}</p>
              <p class="listing-mls">MLS# {html.escape(mls)}</p>
              <a href="{c21_url}" target="_blank" rel="noopener noreferrer" class="listing-cta">View Details →</a>
            </div>
          </article>"""


def render_listings_page(listings: list[dict[str, Any]], updated_at: str) -> str:
    """Full /listings page HTML."""
    count = len(listings)
    updated_display = _format_updated(updated_at)

    desc = (
        f"{count} active Tampa Bay real estate listings currently represented by "
        "Kevin Freel of Century 21 Beggins. Updated daily."
    ) if count else (
        "Kevin Freel's current Tampa Bay real estate listings. Updated daily. "
        "No active listings right now — call 727-410-8599 for pocket and off-market opportunities."
    )

    if count == 0:
        grid_html = """        <div class="listings-empty">
          <p class="listings-empty-headline">No active listings right now.</p>
          <p>Homes move fast in Tampa Bay. Text Kevin at <a href="tel:7274108599">727-410-8599</a> to hear about new listings before they hit the public market.</p>
        </div>"""
    else:
        cards = "\n".join(_listing_card_html(listing) for listing in listings)
        grid_html = f"""        <div class=\"popular-grid listings-grid\">\n{cards}\n        </div>"""

    meta_row = (
        f"Showing {count} active listing{'s' if count != 1 else ''}. "
        f"Last updated {updated_display}."
    ) if count else f"Last checked {updated_display}."

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">

  <title>Kevin Freel's Active Listings — Tampa Bay Real Estate</title>
  <meta name="description" content="{html.escape(desc)}">
  <link rel="canonical" href="https://kevinfreel.com/listings">

  <meta property="og:title" content="Kevin Freel's Active Listings — Tampa Bay Real Estate">
  <meta property="og:description" content="{html.escape(desc)}">
  <meta property="og:image" content="https://kevinfreel.com/images/og-image.jpg">
  <meta property="og:url" content="https://kevinfreel.com/listings">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Kevin Freel Real Estate">

  <link rel="icon" href="/favicon.ico">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">

  <link rel="preload" as="font" type="font/woff2" href="/fonts/playfair-display.woff2" crossorigin>
  <link rel="preload" as="font" type="font/woff2" href="/fonts/inter.woff2" crossorigin>

  <link rel="stylesheet" href="/fonts/fonts.css">
  <link rel="stylesheet" href="/styles.css">

  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "RealEstateAgent",
    "name": "Kevin Freel",
    "url": "https://kevinfreel.com",
    "telephone": "+1-727-410-8599",
    "description": "Licensed realtor in Tampa Bay with 40+ years experience. {count} active listing{'s' if count != 1 else ''} in Tampa Bay.",
    "areaServed": {{
      "@type": "Place",
      "name": "Tampa Bay, FL"
    }},
    "memberOf": {{
      "@type": "Organization",
      "name": "Century 21 Beggins"
    }}
  }}
  </script>

  <script src="/components.js" defer></script>
</head>
<body>

{NAV_HTML}
  <main>

    <!-- ── PAGE HERO ── -->
    <section class="page-hero" aria-label="Kevin Freel's active listings">
      <div class="page-hero-inner">
        <p class="hero-label">Current Inventory</p>
        <h1>Kevin's Active Listings</h1>
        <p class="page-hero-sub">Every listing Kevin currently represents, updated daily. Click through to view full details on Century 21.</p>
      </div>
    </section>

    <!-- ── LISTINGS GRID ── -->
    <section class="content-section" aria-label="Active listings">
      <div class="content-inner">
        <p class="listings-meta-row">{html.escape(meta_row)}</p>
{grid_html}
      </div>
    </section>

    <!-- ── CTA ── -->
    <section class="cta" aria-label="Off-market listings">
      <div class="cta-inner reveal">
        <p class="section-label">Can't Find What You Need?</p>
        <h2 class="cta-heading">Call Kevin for Off-Market Listings</h2>
        <p>Kevin has access to pocket listings and off-market opportunities that never appear on the MLS. Tell him what you're looking for — he'll find it.</p>
        <a href="tel:7274108599" class="cta-phone">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z"/></svg>
          727-410-8599
        </a>
      </div>
    </section>

  </main>

{FOOTER_HTML}
</body>
</html>
"""


def _format_updated(iso: str) -> str:
    """Turn 2026-04-22T10:30:00Z into 'April 22, 2026'."""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%B %-d, %Y")
    except ValueError:
        return iso


def inject_homepage(listings: list[dict[str, Any]], updated_at: str) -> bool:
    """
    Inject/update the 'Featured Active Listings' block on index.html.

    Uses markers <!-- LISTINGS_START --> / <!-- LISTINGS_END --> bracketing
    a full <section>. If markers are missing, inserts them after the Areas
    section (</section> that closes #areas).

    Returns True if the homepage was changed.
    """
    if not HOMEPAGE_HTML.exists():
        print("[warn] index.html not found — skipping homepage injection", file=sys.stderr)
        return False

    current = HOMEPAGE_HTML.read_text(encoding="utf-8")

    top_n = listings[:6]  # already price-desc
    if top_n:
        cards = "\n".join(_listing_card_html(listing) for listing in top_n)
        count = len(listings)
        inner_html = f"""
    <!-- ── FEATURED ACTIVE LISTINGS (auto-synced from Century 21) ── -->
    <section class="content-section featured-listings" aria-label="Featured active listings">
      <div class="content-inner">
        <div class="content-intro reveal">
          <p class="section-label">Active Listings</p>
          <h2 class="section-heading">Kevin's Current Listings</h2>
          <p class="section-sub">{count} {'home' if count == 1 else 'homes'} currently for sale with Kevin, synced daily from Century 21. <a href="/listings" style="color:var(--gold);font-weight:600;">See all active listings →</a></p>
        </div>
        <div class="popular-grid listings-grid">
{cards}
        </div>
        <div class="featured-listings-more">
          <a href="/listings" class="btn-primary">View All {count} Listings</a>
        </div>
      </div>
    </section>
"""
    else:
        inner_html = ""  # no active listings: render nothing

    marker_start = "<!-- LISTINGS_START -->"
    marker_end = "<!-- LISTINGS_END -->"
    block = f"{marker_start}{inner_html}\n    {marker_end}"

    if marker_start in current and marker_end in current:
        pattern = re.compile(
            re.escape(marker_start) + r".*?" + re.escape(marker_end), re.DOTALL
        )
        new_content = pattern.sub(block, current)
    else:
        # Find the end of the Areas section and insert after it.
        # Search for the `id="areas"` section's closing </section> tag.
        areas_idx = current.find('id="areas"')
        if areas_idx == -1:
            print("[warn] no #areas section and no listings markers — skipping injection",
                  file=sys.stderr)
            return False
        # Find the matching </section> after that. We count depth since
        # nested sections are possible.
        i = areas_idx
        depth = 0
        close_idx = -1
        tag_re = re.compile(r"<(/?section)\b", re.IGNORECASE)
        # start search from areas_idx; find <section...> first to initialize depth
        # Our approach: walk tags after areas_idx — first <section must bump depth
        # but areas_idx is mid-tag. Step back to find its own <section.
        section_open = current.rfind("<section", 0, areas_idx)
        if section_open == -1:
            print("[warn] could not locate #areas <section> — skipping injection",
                  file=sys.stderr)
            return False
        for m in tag_re.finditer(current, section_open):
            tag = m.group(1).lower()
            if tag == "section":
                depth += 1
            else:
                depth -= 1
            if depth == 0:
                close_idx = m.end()
                # expand to end of tag '>'
                gt = current.find(">", close_idx - 1)
                if gt != -1:
                    close_idx = gt + 1
                break
        if close_idx == -1:
            print("[warn] could not find #areas </section> close — skipping injection",
                  file=sys.stderr)
            return False
        injection = f"\n\n    {block}"
        new_content = current[:close_idx] + injection + current[close_idx:]

    if new_content != current:
        HOMEPAGE_HTML.write_text(new_content, encoding="utf-8")
        return True
    return False


# ────────────────────────────────────────────────────────────────────
#  Main
# ────────────────────────────────────────────────────────────────────

def main() -> int:
    print(f"[info] sync_listings starting at {datetime.now(timezone.utc).isoformat()}")

    try:
        html_text = fetch_agent_page()
    except Exception as exc:  # noqa: BLE001
        print(f"[error] failed to fetch C21 page: {exc}", file=sys.stderr)
        return 2

    print(f"[info] fetched {len(html_text):,} chars")

    if "--dump" in sys.argv or os.environ.get("SYNC_LISTINGS_DEBUG") == "1":
        dump_path = REPO_ROOT / "scripts" / "_debug_c21.html"
        dump_path.write_text(html_text, encoding="utf-8")
        print(f"[debug] dumped raw HTML to {dump_path}")

    try:
        listings = parse_listings(html_text)
    except Exception as exc:  # noqa: BLE001
        print(f"[error] parse crashed: {exc}", file=sys.stderr)
        return 2

    if not listings:
        print(
            "[error] parsed 0 listings — refusing to blank out existing files. "
            "Scrape may be blocked or page layout changed.",
            file=sys.stderr,
        )
        return 3

    print(f"[info] parsed {len(listings)} listings")

    # Download + optimize photos
    for listing in listings:
        mls = listing["mls_number"]
        photo_url = listing.get("hero_photo_url", "")
        main_p, thumb_p = optimize_photo(mls, photo_url)
        if main_p:
            listing["local_hero"] = f"/images/listings/{mls}.webp"
            listing["local_thumb"] = f"/images/listings/{mls}-sm.webp"

    # Garbage-collect images for MLS numbers no longer active (sold/pending).
    active_mls = {l["mls_number"] for l in listings}
    removed = 0
    if IMAGES_DIR.exists():
        for f in IMAGES_DIR.iterdir():
            if not f.is_file() or f.suffix != ".webp":
                continue
            # Strip optional -sm suffix
            stem = f.stem[:-3] if f.stem.endswith("-sm") else f.stem
            if stem not in active_mls:
                try:
                    f.unlink()
                    removed += 1
                except OSError as exc:
                    print(f"[warn] could not remove {f}: {exc}", file=sys.stderr)
    if removed:
        print(f"[info] removed {removed} stale image file(s)")

    updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Write listings.json
    payload = {
        "updated_at": updated_at,
        "count": len(listings),
        "listings": listings,
    }
    DATA_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[info] wrote {DATA_FILE.relative_to(REPO_ROOT)}")

    # Write listings page
    LISTINGS_DIR.mkdir(parents=True, exist_ok=True)
    LISTINGS_HTML.write_text(
        render_listings_page(listings, updated_at), encoding="utf-8"
    )
    print(f"[info] wrote {LISTINGS_HTML.relative_to(REPO_ROOT)}")

    # Inject homepage
    changed = inject_homepage(listings, updated_at)
    if changed:
        print("[info] updated index.html with homepage injection")
    else:
        print("[info] homepage injection unchanged")

    print(
        f"[info] DONE. {len(listings)} listings, "
        f"{_stats['photos_downloaded']} photos downloaded "
        f"({_stats['bytes_downloaded']:,} bytes), "
        f"{_stats['photos_cached']} cached."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
