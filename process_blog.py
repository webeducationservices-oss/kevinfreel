#!/usr/bin/env python3
"""
Migrate Kevin Freel's Squarespace blog to static HTML on the new site.

Reads URLs from /tmp/kevinfreel-blog/blog-urls.txt.
For each URL:
  - fetches HTML
  - parses title, date, body, hero image
  - downloads + converts hero image to WebP
  - writes /blog/<slug>.html using the site's design system
Then builds /blog/index.html and /blog/manifest.json.
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
import io
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString
from PIL import Image

# --- Paths ---
ROOT = Path('/Users/justinbabcock/Desktop/Websites/kevinfreel')
URL_FILE = Path('/tmp/kevinfreel-blog/blog-urls.txt')
BLOG_DIR = ROOT / 'blog'
IMAGES_DIR = ROOT / 'images' / 'blog'
CHECKPOINT = Path('/tmp/kevinfreel-blog/checkpoint.json')
MANIFEST_PATH = BLOG_DIR / 'manifest.json'

USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36'

# --- Tag inference ---
# Order matters — first match wins for primary tag.
# Each keyword is matched as a WHOLE-WORD/PHRASE (word-boundary) substring.
TAG_RULES = [
    # (keywords, tag-slug, display-name)
    (['just sold', 'sold in ', 'sold on ', 'sold this ', 'recently sold', 'just-sold', 'another home sold', 'another sold', 'another luxury home sold'], 'just-sold', 'Just Sold'),
    (['open house'], 'open-house', 'Open House'),
    (['hurricane', 'tropical storm', 'hurricane milton', 'hurricane helene', 'hurricane ian', 'flood damage', 'storm damage', 'storm-damaged', 'storm surge', 'post-hurricane', 'post hurricane'], 'storm-recovery', 'Storm Recovery'),
    (['market report', 'market update', 'housing market', 'market outlook', 'market conditions', 'market forecast', 'market trends'], 'market-update', 'Market Update'),
    (['south tampa', 'hyde park', 'ballast point', 'palma ceia', 'davis island', 'beach park', 'bayshore'], 'south-tampa', 'South Tampa'),
    (['seller', 'selling your home', 'sell your home', 'home selling tips'], 'selling', 'Selling'),
    (['buyer', 'home buying', 'buy a home', 'first-time buyer', 'first time buyer', 'home buyer tips'], 'buying', 'Buying'),
    (['luxury home', 'million-dollar', 'million dollar', 'luxury property', 'luxury listing'], 'luxury', 'Luxury'),
    (['carrollwood', 'new tampa', 'westchase', 'st. pete', 'saint pete', 'saint-pete', 'clearwater', 'dunedin', 'belleair', 'lutz', 'brandon', 'tampa heights', 'riverview', 'st. petersburg', 'indian rocks', 'treasure island'], 'tampa-bay', 'Tampa Bay'),
    (['investment property', 'rental property', 'real estate investor', 'real estate investing'], 'investing', 'Investing'),
    (['mortgage', 'refinance', 'interest rate', 'home loan', 'mortgage rate'], 'mortgage', 'Mortgage'),
]

# --- helpers ---
def log(msg):
    print(msg, flush=True)

def slugify(s):
    s = s.lower()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')

def ensure_dirs():
    BLOG_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

def load_checkpoint():
    if CHECKPOINT.exists():
        try:
            return json.loads(CHECKPOINT.read_text())
        except Exception:
            return {}
    return {}

def save_checkpoint(cp):
    CHECKPOINT.write_text(json.dumps(cp, indent=2))

def fetch(url, tries=3, timeout=30):
    last = None
    for t in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': '*/*'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            last = e
            time.sleep(1.5 * (t + 1))
    raise last

def fetch_html(url):
    data = fetch(url)
    return data.decode('utf-8', errors='replace')

def parse_date(iso):
    """Parse ISO-like '2026-04-16T14:08:03-0400' into (datetime, iso_z, friendly)."""
    if not iso:
        return None, '', ''
    try:
        # Normalize -0400 to -04:00 for fromisoformat
        s = iso.strip()
        m = re.search(r'([+-])(\d{2})(\d{2})$', s)
        if m:
            s = s[:m.start()] + f'{m.group(1)}{m.group(2)}:{m.group(3)}'
        dt = datetime.fromisoformat(s)
    except Exception:
        return None, '', ''
    iso_out = dt.strftime('%Y-%m-%dT%H:%M:%S%z')
    # Insert colon in tz
    if iso_out and len(iso_out) >= 5 and iso_out[-5] in '+-' and ':' not in iso_out[-5:]:
        iso_out = iso_out[:-2] + ':' + iso_out[-2:]
    friendly = dt.strftime('%B %-d, %Y')
    return dt, iso_out, friendly

def infer_tags(title, text):
    blob = (title + ' ' + (text or '')).lower()
    picks = []
    for keywords, slug, name in TAG_RULES:
        for kw in keywords:
            if kw in blob:
                if slug not in [p[0] for p in picks]:
                    picks.append((slug, name))
                break
        if len(picks) >= 3:
            break
    if not picks:
        picks.append(('news', 'News'))
    return picks  # list of (slug, display)

def decode_entities(t):
    """Decode common HTML entities so we don't double-encode later."""
    if not t:
        return ''
    import html as _html
    return _html.unescape(t)

def clean_title(t):
    if not t:
        return ''
    t = decode_entities(t)
    # Strip trailing site name
    t = re.sub(r'\s*(—|-|–)\s*KevinFreel\.com.*$', '', t, flags=re.I)
    t = re.sub(r'\s*\|\s*KevinFreel.*$', '', t, flags=re.I)
    return t.strip()

def html_escape(s):
    if s is None:
        return ''
    return (s.replace('&', '&amp;')
             .replace('<', '&lt;')
             .replace('>', '&gt;')
             .replace('"', '&quot;'))

def truncate(s, n):
    s = (s or '').strip()
    if len(s) <= n:
        return s
    cut = s[:n]
    # Back up to last space
    if ' ' in cut:
        cut = cut.rsplit(' ', 1)[0]
    return cut.rstrip(' ,.;:') + '…'

# --- HTML cleaning ---

ALLOWED_TAGS = {
    'p', 'h2', 'h3', 'h4', 'ul', 'ol', 'li',
    'strong', 'em', 'b', 'i', 'a', 'blockquote',
    'img', 'br', 'hr',
}

def clean_body(html, slug, image_map):
    """Extract clean body HTML from a Squarespace blog item.

    Keeps: h2/h3/p/ul/ol/li/strong/em/a/blockquote/img
    Strips: inline styles, class attrs, squarespace wrappers, script, style, YouTube embeds (converted to link)
    """
    soup = BeautifulSoup(html, 'html.parser')
    wrap = soup.select_one('.blog-item-content, .blog-item-content-wrapper')
    if not wrap:
        return '', []

    # Drop scripts/styles/iframes but remember video URLs
    video_links = []
    for iframe in wrap.find_all('iframe'):
        src = iframe.get('src', '')
        if 'youtube' in src or 'vimeo' in src:
            video_links.append(src)
        iframe.decompose()
    for wrapper in wrap.select('.sqs-video-wrapper'):
        html_attr = wrapper.get('data-html', '')
        m = re.search(r'src=["\'](https?://[^"\']+)["\']', html_attr)
        if m:
            video_links.append(m.group(1))
        wrapper.decompose()
    for tag in wrap.find_all(['script', 'style', 'noscript', 'svg', 'form']):
        tag.decompose()

    # Convert each image-like element to a plain <img> (to be downloaded later)
    body_images = []
    for img in wrap.find_all('img'):
        src = img.get('data-src') or img.get('src') or img.get('data-image')
        alt = img.get('alt') or img.get('data-image-caption') or ''
        if src and src.startswith('//'):
            src = 'https:' + src
        if src:
            body_images.append({'url': src, 'alt': alt})
            img.attrs = {'src': src, 'alt': alt}

    # Promote content from Squarespace wrapper divs: find all top-level .sqs-html-content
    # Build fresh content
    parts = []
    for html_block in wrap.select('.sqs-html-content'):
        parts.append(str(html_block))
    # Also capture any standalone image blocks outside html-content blocks
    for img in wrap.find_all('img'):
        # Only include if not already inside a html-content block
        if not img.find_parent(attrs={'class': 'sqs-html-content'}):
            parts.append(str(img))

    if not parts:
        # Fallback: try the whole wrap but strip Squarespace block wrappers
        parts.append(str(wrap))

    merged_html = '\n'.join(parts)
    body_soup = BeautifulSoup(merged_html, 'html.parser')

    # Recursively unwrap disallowed tags but keep their children, strip attrs from allowed tags
    def clean(node):
        for el in list(node.children):
            if isinstance(el, NavigableString):
                continue
            clean(el)
            name = el.name.lower() if el.name else ''
            if name not in ALLOWED_TAGS:
                # Unwrap: replace element with its children
                el.unwrap()
                continue
            # Strip all attrs except allowed ones per tag
            allowed_attrs = set()
            if name == 'a':
                allowed_attrs = {'href', 'title'}
            elif name == 'img':
                allowed_attrs = {'src', 'alt', 'width', 'height'}
            new_attrs = {k: v for k, v in el.attrs.items() if k in allowed_attrs}
            el.attrs = new_attrs
            # For links: rewrite internal kevinfreel.com links to relative paths; external get target=_blank
            if name == 'a':
                href = new_attrs.get('href', '')
                # Strip utm params from internal links
                m = re.match(r'https?://(?:www\.)?kevinfreel\.com(/[^?#]*)?(\?[^#]*)?(#.*)?$', href)
                if m:
                    path = m.group(1) or '/'
                    frag = m.group(3) or ''
                    el['href'] = path + frag
                    if 'target' in el.attrs:
                        del el['target']
                    if 'rel' in el.attrs:
                        del el['rel']
                elif href.startswith('http'):
                    el['target'] = '_blank'
                    el['rel'] = 'noopener noreferrer'
    clean(body_soup)

    # Remove empty paragraphs
    for p in body_soup.find_all(['p', 'h2', 'h3']):
        txt = p.get_text(strip=True)
        if not txt and not p.find('img'):
            p.decompose()

    # Replace image src for downloaded ones
    for img in body_soup.find_all('img'):
        src = img.get('src', '')
        if src in image_map:
            img['src'] = image_map[src]
            img['loading'] = 'lazy'

    # Add a "Watch video" link at the top if we had embeds
    if video_links:
        vid_html = ''
        for link in dict.fromkeys(video_links):  # dedupe preserve order
            # Normalize YouTube embed to watch URL
            m = re.search(r'youtube\.com/embed/([A-Za-z0-9_\-]+)', link)
            if m:
                link = f'https://www.youtube.com/watch?v={m.group(1)}'
            vid_html += f'<p><a href="{link}" target="_blank" rel="noopener noreferrer">Watch the video →</a></p>\n'
        body_soup.insert(0, BeautifulSoup(vid_html, 'html.parser'))

    final_html = str(body_soup)
    # Collapse repeated blank lines
    final_html = re.sub(r'\n{3,}', '\n\n', final_html)
    return final_html.strip(), body_images

# --- Image handling ---

def download_and_convert(url, out_path, max_width=1200, quality=72):
    """Download image from `url`, convert to WebP at `out_path`. Returns True on success."""
    # If already exists and non-trivial size, skip re-download
    if out_path.exists() and out_path.stat().st_size > 2000:
        return True
    try:
        data = fetch(url, tries=3, timeout=40)
        img = Image.open(io.BytesIO(data))
        if img.mode in ('P', 'LA'):
            img = img.convert('RGBA')
        if img.mode == 'RGBA':
            # flatten to white bg
            bg = Image.new('RGB', img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        w, h = img.size
        if w > max_width:
            new_h = int(h * (max_width / w))
            img = img.resize((max_width, new_h), Image.LANCZOS)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, 'WEBP', quality=quality, method=6)
        return True
    except Exception as e:
        log(f'  ! image fail {url[:80]}: {e}')
        return False

# --- HTML template ---

NAV_HTML = '''  <!-- ── NAV ── -->
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
    <a href="/contact">Contact</a>
    <a href="tel:7274108599" class="nav-cta">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z"/></svg>
      727-410-8599
    </a>
  </div>
'''

FOOTER_HTML = '''  <!-- ── FOOTER ── -->
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
'''

POST_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">

  <title>{title_esc} — Kevin Freel Real Estate</title>
  <meta name="description" content="{desc_esc}">
  <link rel="canonical" href="https://kevinfreel.com/blog/{slug}">

  <meta property="og:title" content="{title_esc}">
  <meta property="og:description" content="{desc_esc}">
  <meta property="og:image" content="{og_image_abs}">
  <meta property="og:url" content="https://kevinfreel.com/blog/{slug}">
  <meta property="og:type" content="article">
  <meta property="og:site_name" content="Kevin Freel Real Estate">
  <meta property="article:published_time" content="{iso_date}">
  <meta property="article:author" content="Kevin Freel">

  <link rel="icon" href="/favicon.ico">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">

  <link rel="preload" as="font" type="font/woff2" href="/fonts/playfair-display.woff2" crossorigin>
  <link rel="preload" as="font" type="font/woff2" href="/fonts/inter.woff2" crossorigin>

  <link rel="stylesheet" href="/fonts/fonts.css">
  <link rel="stylesheet" href="/styles.css">

  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    "headline": {title_json},
    "author": {{"@type": "Person", "name": "Kevin Freel"}},
    "datePublished": "{iso_date}",
    "image": "{og_image_abs}",
    "publisher": {{"@type": "Organization", "name": "Kevin Freel Real Estate", "url": "https://kevinfreel.com"}},
    "mainEntityOfPage": "https://kevinfreel.com/blog/{slug}"
  }}
  </script>

  <script src="/components.js" defer></script>
</head>
<body>

{nav}
  <main>

    <section class="blog-post-hero">
      <div class="blog-post-hero-inner">
        <a href="/blog" class="blog-back-link">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
          Back to Blog
        </a>
        <div class="blog-post-meta">
          <span>{friendly_date}</span>
{tags_html}        </div>
        <h1>{title_esc}</h1>
      </div>
    </section>

    <article class="blog-post-body">
{body_html}
    </article>

    <div class="blog-post-footer">
      <div class="blog-post-cta">
        <h3>Interested in Tampa Bay Real Estate?</h3>
        <p>Whether you're buying, selling, or just have questions — Kevin is here to help.</p>
        <a href="tel:7274108599" class="btn-primary">Call Kevin — 727-410-8599</a>
      </div>
    </div>

  </main>

{footer}
</body>
</html>
'''

# --- Main post processor ---

def process_post(url, checkpoint, force=False):
    slug = url.rstrip('/').rsplit('/', 1)[-1]
    out_path = BLOG_DIR / f'{slug}.html'
    if not force and slug in checkpoint and checkpoint[slug].get('ok') and out_path.exists():
        return checkpoint[slug]

    try:
        html = fetch_html(url)
    except Exception as e:
        log(f'  ! fetch fail: {e}')
        return {'slug': slug, 'url': url, 'ok': False, 'error': f'fetch: {e}'}

    soup = BeautifulSoup(html, 'html.parser')

    # Title
    og_title_tag = soup.select_one('meta[property="og:title"]')
    h1_tag = soup.select_one('h1.entry-title, .blog-item-title h1, article h1')
    title_raw = None
    if h1_tag:
        title_raw = h1_tag.get_text(' ', strip=True)
    if not title_raw and og_title_tag:
        title_raw = og_title_tag.get('content', '')
    title = clean_title(title_raw or slug.replace('-', ' ').title())

    # Date
    date_tag = soup.select_one('meta[itemprop="datePublished"]')
    iso_raw = date_tag.get('content') if date_tag else ''
    if not iso_raw:
        t = soup.select_one('time[datetime]')
        if t:
            iso_raw = t.get('datetime')
    dt, iso_date, friendly_date = parse_date(iso_raw)
    if not iso_date:
        iso_date = '2024-01-01T00:00:00-05:00'
        friendly_date = 'January 1, 2024'
        dt = datetime(2024, 1, 1)

    # OG image for hero
    og_image_tag = soup.select_one('meta[property="og:image"]')
    og_image_url = og_image_tag.get('content') if og_image_tag else ''
    if og_image_url and og_image_url.startswith('//'):
        og_image_url = 'https:' + og_image_url
    # Force https
    if og_image_url.startswith('http://'):
        og_image_url = 'https://' + og_image_url[7:]

    # Body & inline images
    body_clean, body_images = clean_body(html, slug, {})

    # Description / excerpt
    desc_tag = soup.select_one('meta[property="og:description"], meta[name="description"]')
    desc_raw = desc_tag.get('content') if desc_tag else ''
    # Derive from body if empty
    if not desc_raw and body_clean:
        body_soup = BeautifulSoup(body_clean, 'html.parser')
        first_p = body_soup.find('p')
        if first_p:
            desc_raw = first_p.get_text(' ', strip=True)
    desc_raw = decode_entities(desc_raw)
    excerpt = truncate(desc_raw, 200)
    excerpt_short = truncate(desc_raw, 140)

    # Tags
    body_text_for_tags = BeautifulSoup(body_clean, 'html.parser').get_text(' ', strip=True) if body_clean else ''
    tags = infer_tags(title, body_text_for_tags)

    # Download hero image
    hero_local = None
    hero_abs = ''
    if og_image_url:
        hero_path = IMAGES_DIR / slug / 'hero.webp'
        if download_and_convert(og_image_url, hero_path, max_width=1200, quality=72):
            hero_local = f'/images/blog/{slug}/hero.webp'
            hero_abs = f'https://kevinfreel.com{hero_local}'

    # Download body images and rewrite
    image_map = {}
    if body_images:
        for idx, bi in enumerate(body_images):
            u = bi['url']
            if u.startswith('//'):
                u = 'https:' + u
            if u.startswith('http://'):
                u = 'https://' + u[7:]
            local_path = IMAGES_DIR / slug / f'img-{idx+1}.webp'
            if download_and_convert(u, local_path, max_width=1200, quality=72):
                image_map[bi['url']] = f'/images/blog/{slug}/img-{idx+1}.webp'
        # Rewrite body with new paths
        if image_map:
            body_soup = BeautifulSoup(body_clean, 'html.parser')
            for img in body_soup.find_all('img'):
                src = img.get('src', '')
                if src in image_map:
                    img['src'] = image_map[src]
                    img['loading'] = 'lazy'
            body_clean = str(body_soup)

    # If no hero downloaded, use a placeholder
    if not hero_local:
        hero_local = '/images/properties/grandifloras/exterior-aerial-1-md.webp'
        hero_abs = f'https://kevinfreel.com{hero_local}'

    # Indent body HTML for template
    body_indented = '\n'.join('      ' + line for line in body_clean.splitlines())

    # Build tags html
    tags_html = ''
    for slug_t, name in tags:
        tags_html += f'          <span class="tag">{html_escape(name)}</span>\n'

    # Render
    page = POST_TEMPLATE.format(
        title_esc=html_escape(title),
        title_json=json.dumps(title),
        slug=slug,
        desc_esc=html_escape(excerpt_short),
        og_image_abs=html_escape(hero_abs),
        iso_date=iso_date,
        friendly_date=friendly_date,
        nav=NAV_HTML,
        footer=FOOTER_HTML,
        tags_html=tags_html,
        body_html=body_indented,
    )
    out_path.write_text(page, encoding='utf-8')

    return {
        'slug': slug,
        'url': url,
        'ok': True,
        'title': title,
        'iso_date': iso_date,
        'friendly_date': friendly_date,
        'sort_date': dt.strftime('%Y-%m-%d') if dt else '2024-01-01',
        'excerpt': excerpt,
        'excerpt_short': excerpt_short,
        'hero_image': hero_local,
        'hero_abs': hero_abs,
        'tags': [{'slug': s, 'name': n} for s, n in tags],
    }

# --- Blog index builder ---

INDEX_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">

  <title>Blog — Kevin Freel Real Estate</title>
  <meta name="description" content="Market updates, just-listed highlights, sold success stories, and Tampa Bay real estate tips — straight from Kevin.">
  <link rel="canonical" href="https://kevinfreel.com/blog">

  <meta property="og:title" content="Blog — Kevin Freel Real Estate">
  <meta property="og:description" content="Tampa Bay real estate updates, market reports, and sold stories from 40-year Realtor Kevin Freel.">
  <meta property="og:image" content="https://kevinfreel.com/images/og-image.jpg">
  <meta property="og:url" content="https://kevinfreel.com/blog">
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
    "@type": "Blog",
    "name": "Kevin Freel Real Estate Blog",
    "url": "https://kevinfreel.com/blog",
    "publisher": {{"@type": "Organization", "name": "Kevin Freel Real Estate"}}
  }}
  </script>

  <script src="/components.js" defer></script>
</head>
<body>

{nav}
  <main>

    <section class="page-hero" aria-label="Blog">
      <div class="page-hero-inner">
        <p class="hero-label">Tampa Bay Real Estate Blog</p>
        <h1>Stories From the Field</h1>
        <p class="page-hero-sub">Market updates, just-listed highlights, sold success stories, and Tampa Bay real estate tips — straight from Kevin.</p>
      </div>
    </section>

    <section class="content-section" aria-label="Blog posts">
      <div class="content-inner">
        <div class="blog-controls">
          <div class="blog-search">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input type="search" id="blog-search" placeholder="Search posts..." aria-label="Search blog">
          </div>
          <div class="blog-tag-filters">
            <button class="blog-tag-filter active" data-filter="all">All</button>
{tag_buttons}
          </div>
        </div>

        <div class="blog-grid">
{cards_html}
        </div>

        <div class="blog-empty">No posts match your search.</div>
      </div>
    </section>

  </main>

{footer}
</body>
</html>
'''

def build_index(posts):
    # Sort newest first
    posts_sorted = sorted(posts, key=lambda p: p.get('sort_date', ''), reverse=True)

    # Collect unique tags (ordered by frequency)
    tag_counts = {}
    tag_names = {}
    for p in posts_sorted:
        for t in p.get('tags', []):
            tag_counts[t['slug']] = tag_counts.get(t['slug'], 0) + 1
            tag_names[t['slug']] = t['name']
    ordered_tags = sorted(tag_counts.items(), key=lambda x: (-x[1], x[0]))

    tag_buttons_html = ''
    for tag_slug, _count in ordered_tags:
        name = tag_names[tag_slug]
        tag_buttons_html += f'            <button class="blog-tag-filter" data-filter="{html_escape(tag_slug)}">{html_escape(name)}</button>\n'

    # Build cards
    cards_html = ''
    for p in posts_sorted:
        slug = p['slug']
        title = p['title']
        excerpt = truncate(p.get('excerpt', ''), 140)
        hero = p.get('hero_image', '/images/properties/grandifloras/exterior-aerial-1-md.webp')
        date_f = p['friendly_date']
        tag_slugs = ','.join([t['slug'] for t in p.get('tags', [])])
        first_tag = p['tags'][0]['name'] if p.get('tags') else 'News'
        cards_html += f'''          <a href="/blog/{slug}" class="blog-card" data-title="{html_escape(title)}" data-excerpt="{html_escape(excerpt)}" data-tags="{html_escape(tag_slugs)}">
            <div class="blog-card-image">
              <img src="{html_escape(hero)}" alt="{html_escape(title)}" width="600" height="338" loading="lazy">
            </div>
            <div class="blog-card-body">
              <div class="blog-card-meta">
                <span>{html_escape(date_f)}</span>
                <span class="tag">{html_escape(first_tag)}</span>
              </div>
              <h3>{html_escape(title)}</h3>
              <p>{html_escape(excerpt)}</p>
              <span class="blog-card-more">Read more →</span>
            </div>
          </a>
'''

    page = INDEX_TEMPLATE.format(
        nav=NAV_HTML,
        footer=FOOTER_HTML,
        tag_buttons=tag_buttons_html.rstrip(),
        cards_html=cards_html.rstrip(),
    )
    (BLOG_DIR / 'index.html').write_text(page, encoding='utf-8')

# --- Main ---

def main():
    ensure_dirs()
    urls = [u.strip() for u in URL_FILE.read_text().splitlines() if u.strip()]
    log(f'Total URLs: {len(urls)}')

    # Args
    only = None
    force = False
    index_only = False
    for a in sys.argv[1:]:
        if a.startswith('--only='):
            only = a.split('=', 1)[1]
        elif a == '--force':
            force = True
        elif a == '--index-only':
            index_only = True

    checkpoint = load_checkpoint()
    results = []

    if index_only:
        # Build from checkpoint data
        for slug, data in checkpoint.items():
            if data.get('ok'):
                results.append(data)
        build_index(results)
        MANIFEST_PATH.write_text(json.dumps(
            [{'slug': r['slug'], 'title': r['title'], 'date': r['iso_date'],
              'excerpt': r.get('excerpt', ''), 'hero_image': r.get('hero_image', ''),
              'tags': [t['slug'] for t in r.get('tags', [])]}
             for r in sorted(results, key=lambda x: x.get('sort_date', ''), reverse=True)],
            indent=2))
        log(f'Built index with {len(results)} posts.')
        return

    for i, url in enumerate(urls, 1):
        slug = url.rstrip('/').rsplit('/', 1)[-1]
        if only and slug != only:
            continue
        log(f'[{i}/{len(urls)}] {slug}')
        try:
            data = process_post(url, checkpoint, force=force)
        except Exception as e:
            log(f'  ! crashed: {e}')
            data = {'slug': slug, 'url': url, 'ok': False, 'error': str(e)}
        checkpoint[slug] = data
        save_checkpoint(checkpoint)
        if data.get('ok'):
            results.append(data)
            log(f'  ✓ {data["title"][:70]}')
        else:
            log(f'  ✗ FAILED: {data.get("error", "unknown")}')

    # Build index from all OK results
    ok_results = [d for d in checkpoint.values() if d.get('ok')]
    build_index(ok_results)
    # Manifest
    manifest = [{'slug': r['slug'], 'title': r['title'], 'date': r['iso_date'],
                 'excerpt': r.get('excerpt', ''), 'hero_image': r.get('hero_image', ''),
                 'tags': [t['slug'] for t in r.get('tags', [])]}
                for r in sorted(ok_results, key=lambda x: x.get('sort_date', ''), reverse=True)]
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))

    # Summary
    failed = [d for d in checkpoint.values() if not d.get('ok')]
    log(f'\n=== DONE ===')
    log(f'Succeeded: {len(ok_results)}')
    log(f'Failed: {len(failed)}')
    for f in failed:
        log(f'  - {f.get("slug")}: {f.get("error")}')

if __name__ == '__main__':
    main()
