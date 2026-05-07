#!/usr/bin/env python3
"""
Restructure Kevin Freel's blog posts to conform to BLOG-TEMPLATE.md.

Reads each existing post in /blog/*.html plus blog/manifest.json and rewrites
each file with:
  - hero <img> rendered inside .blog-post-hero (per spec)
  - YouTube videos embedded (privacy-respecting, lazy-loaded) at top of body
  - qualifying H3 sections wrapped in .article-card
  - .blog-inline-cta injected after video and mid-body for long posts
  - .blog-post-wrap with .blog-article + .blog-sidebar (related posts + CTA)
  - final .blog-post-cta with category-aware messaging

Also rewrites /blog/index.html using the BLOG-TEMPLATE.md spec
(#postGrid + .blog-grid + .post-card with data-cat) and refreshes
manifest.json with category info.

Usage:
  python3 process_blog.py            # restructure all posts + rebuild index
  python3 process_blog.py --only=heights
  python3 process_blog.py --index-only
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString

# --- Paths ---
ROOT = Path('/Users/justinbabcock/Desktop/Websites/kevinfreel')
BLOG_DIR = ROOT / 'blog'
IMAGES_DIR = ROOT / 'images' / 'blog'
MANIFEST_PATH = BLOG_DIR / 'manifest.json'

# --- Tag display names (lookup) ---
TAG_DISPLAY = {
    'just-sold': 'Just Sold',
    'open-house': 'Open House',
    'storm-recovery': 'Storm Recovery',
    'market-update': 'Market Update',
    'south-tampa': 'South Tampa',
    'selling': 'Selling',
    'buying': 'Buying',
    'luxury': 'Luxury',
    'tampa-bay': 'Tampa Bay',
    'investing': 'Investing',
    'mortgage': 'Mortgage',
    'news': 'News',
}

# Categories that should get a "Schedule a Showing" inline CTA after the video
PROPERTY_CATEGORIES = {'just-sold', 'open-house', 'buying', 'selling', 'luxury'}


# --- helpers ---
def log(msg):
    print(msg, flush=True)


def html_escape(s):
    if s is None:
        return ''
    return (str(s).replace('&', '&amp;')
                  .replace('<', '&lt;')
                  .replace('>', '&gt;')
                  .replace('"', '&quot;'))


def truncate(s, n):
    s = (s or '').strip()
    if len(s) <= n:
        return s
    cut = s[:n]
    if ' ' in cut:
        cut = cut.rsplit(' ', 1)[0]
    return cut.rstrip(' ,.;:') + '…'


def parse_iso_date(iso):
    """Return (datetime, friendly_str)."""
    if not iso:
        return None, ''
    try:
        s = iso.strip()
        # Normalize -0400 to -04:00 if needed
        m = re.search(r'([+-])(\d{2})(\d{2})$', s)
        if m and ':' not in s[m.start():]:
            s = s[:m.start()] + f'{m.group(1)}{m.group(2)}:{m.group(3)}'
        dt = datetime.fromisoformat(s)
    except Exception:
        return None, ''
    friendly = dt.strftime('%B %-d, %Y')
    return dt, friendly


def estimate_read_time(text):
    words = len(text.split())
    minutes = max(1, round(words / 220))
    return f'{minutes} min read'


# --- YouTube embed ---
YOUTUBE_RE = re.compile(
    r'(?:https?:)?//(?:www\.)?'
    r'(?:(?:youtube|youtube-nocookie)\.com/(?:watch\?v=|embed/|v/|shorts/)|youtu\.be/)'
    r'([A-Za-z0-9_\-]{6,})',
    re.IGNORECASE,
)


def extract_youtube_id(url):
    if not url:
        return None
    m = YOUTUBE_RE.search(url)
    if m:
        return m.group(1)
    return None


def find_youtube_id(soup):
    """Look for any YouTube link or iframe inside `soup`. Return the first ID."""
    # Iframes first
    for iframe in soup.find_all('iframe'):
        vid = extract_youtube_id(iframe.get('src', ''))
        if vid:
            return vid
    # Anchor tags
    for a in soup.find_all('a'):
        vid = extract_youtube_id(a.get('href', ''))
        if vid:
            return vid
    # Plain text
    text = soup.get_text(' ', strip=True)
    vid = extract_youtube_id(text)
    return vid


def remove_youtube_links(soup):
    """Strip iframes and 'Watch the video' anchors that point to YouTube."""
    # Iframes
    for iframe in list(soup.find_all('iframe')):
        if extract_youtube_id(iframe.get('src', '')):
            # Remove parent <p> if it only wraps this iframe
            parent = iframe.parent
            iframe.decompose()
            if parent and parent.name == 'p' and not parent.get_text(strip=True):
                parent.decompose()

    # Anchors that link to YouTube
    for a in list(soup.find_all('a')):
        href = a.get('href', '')
        if not extract_youtube_id(href):
            continue
        text = a.get_text(' ', strip=True).lower()
        # If the anchor is the entire content of a paragraph, drop the paragraph
        parent = a.parent
        a_text_only = True
        if parent and parent.name == 'p':
            other_text = ''.join(
                str(c) if isinstance(c, NavigableString) else c.get_text('', strip=True)
                for c in parent.children if c is not a
            ).strip()
            a_text_only = (other_text == '')
        # Heuristic: drop the link if it's a "watch the video" style link OR
        # the entire paragraph is just the link.
        watch_phrases = ('watch the video', 'watch video', 'watch on youtube', 'see the video', 'click here')
        is_watch_link = any(p in text for p in watch_phrases) or text.endswith('→')
        if is_watch_link or a_text_only:
            if parent and parent.name == 'p' and a_text_only:
                parent.decompose()
            else:
                a.decompose()


def youtube_embed_html(video_id, title='Kevin Freel Real Estate'):
    title_attr = html_escape(title)
    return (
        '<div class="blog-video">'
        f'<iframe src="https://www.youtube-nocookie.com/embed/{video_id}" '
        f'title="{title_attr}" '
        'frameborder="0" '
        'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" '
        'referrerpolicy="strict-origin-when-cross-origin" '
        'allowfullscreen loading="lazy"></iframe>'
        '</div>'
    )


# --- H3 cards ---
def style_h3_cards(article_root):
    """Wrap qualifying H3 sections in `.article-card`.

    Rules:
      - Only h3 (not h2)
      - Skip when total h3 count is 0, 1 or 2
      - Skip a specific h3 if it has fewer than 2 paragraphs of content
        before the next h2/h3
    Returns: number of cards added.
    """
    h3s = article_root.find_all('h3')
    if len(h3s) < 3:
        return 0

    # Get a soup factory regardless of whether `article_root` is a Tag or soup.
    soup_factory = BeautifulSoup('', 'html.parser')

    cards_added = 0
    for h3 in list(h3s):
        # Count following <p> siblings until the next h2/h3
        para_count = 0
        sibs = []
        sib = h3.find_next_sibling()
        while sib and (not sib.name or sib.name.lower() not in ('h2', 'h3')):
            if sib.name and sib.name.lower() == 'p':
                para_count += 1
            sibs.append(sib)
            sib = sib.find_next_sibling()
        if para_count < 2:
            continue
        # Build wrapper
        wrapper = soup_factory.new_tag('div')
        wrapper['class'] = 'article-card'
        h3.insert_before(wrapper)
        wrapper.append(h3.extract())
        for s in sibs:
            wrapper.append(s.extract())
        cards_added += 1
    return cards_added


# --- Inline CTA injection ---
def inline_cta_html(category, position='middle'):
    cat = (category or '').lower()
    if cat == 'just-sold':
        title = 'Want results like these?'
        body = "When the right marketing meets 40 years of Tampa Bay relationships, homes sell. Let's talk about your move."
        button = "Let's Talk"
    elif cat == 'open-house':
        title = 'Want to see this home in person?'
        body = "Schedule a private tour or get more details from Kevin — no pressure, no spam."
        button = 'Schedule a Showing'
    elif cat == 'selling':
        title = 'Thinking about selling?'
        body = "See exactly what Kevin does to get your home sold for top dollar — no obligation."
        button = 'Get a Free Strategy Call'
    elif cat == 'buying':
        title = 'Looking for a home in Tampa Bay?'
        body = "Kevin will help you find a home that fits — and negotiate hard to get it."
        button = 'Get Started'
    elif cat == 'luxury':
        title = 'Considering a luxury move?'
        body = 'Discreet representation, premium marketing, decades of high-end Tampa Bay experience.'
        button = "Schedule a Consultation"
    elif cat == 'market-update':
        title = 'Curious what your home is worth right now?'
        body = "Kevin will give you a real number based on the actual market — not a website estimate."
        button = 'Request a Home Valuation'
    elif cat == 'storm-recovery':
        title = 'Storm-affected home? Let Kevin help.'
        body = "From insurance navigation to selling as-is or rebuilding, you don't have to figure it out alone."
        button = 'Talk to Kevin'
    else:
        title = 'Looking to buy or sell in Tampa Bay?'
        body = "Kevin has 40+ years of local experience. Get a no-pressure consultation."
        button = 'Talk to Kevin'

    return (
        '<aside class="blog-inline-cta">'
        f'<h4>{html_escape(title)}</h4>'
        f'<p>{html_escape(body)}</p>'
        f'<a href="/contact" class="btn-primary">{html_escape(button)}</a>'
        '</aside>'
    )


def small_cta_pill_html(category):
    """A compact pill button shown right after the video for property posts."""
    if category in {'just-sold', 'selling'}:
        text = 'Get Your Home Sold'
        href = '/contact'
    elif category == 'luxury':
        text = 'Schedule a Consultation'
        href = '/contact'
    elif category == 'open-house':
        text = 'Schedule a Showing'
        href = '/contact'
    elif category == 'buying':
        text = 'Start Your Home Search'
        href = '/search'
    else:
        text = 'Get Started'
        href = '/contact'
    return (
        '<div class="blog-cta-pill-row">'
        f'<a href="{html_escape(href)}" class="blog-cta-pill">'
        f'{html_escape(text)} <span aria-hidden="true">&rarr;</span></a>'
        '</div>'
    )


def inject_inline_cta(article_soup, category, word_count):
    """Insert .blog-inline-cta block into an article soup if word_count > 1500.
    Inserts roughly halfway through the paragraphs."""
    if word_count < 1500:
        return False
    paragraphs = article_soup.find_all('p', recursive=True)
    # Filter to paragraphs that are direct children of the article (skip nested lists, etc.)
    top_paragraphs = [p for p in paragraphs
                      if p.parent is article_soup
                      or (p.parent and p.parent.name == 'div' and 'article-card' in p.parent.get('class', []))]
    if len(top_paragraphs) < 6:
        return False
    target = top_paragraphs[len(top_paragraphs) // 2]
    cta = BeautifulSoup(inline_cta_html(category, 'middle'), 'html.parser')
    target.insert_after(cta)
    return True


def insert_after_video_cta(article_soup, category):
    """Inject a small pill CTA right after the video block for property categories."""
    if category not in PROPERTY_CATEGORIES:
        return False
    video = article_soup.find('div', class_='blog-video')
    if not video:
        return False
    pill = BeautifulSoup(small_cta_pill_html(category), 'html.parser')
    video.insert_after(pill)
    return True


# --- Final CTA messaging by category ---
def final_cta_html(category):
    cat = (category or '').lower()
    if cat == 'just-sold':
        head = 'Thinking about selling?'
        body = "If you'd like results like these for your own home, let's talk. Kevin has been getting results in Tampa Bay since 1985."
    elif cat == 'open-house':
        head = 'Schedule a Private Showing'
        body = "Can't make the open house? Kevin can show you the home on your schedule. Reach out anytime."
    elif cat == 'selling':
        head = 'Ready to Sell Your Home?'
        body = 'Get a no-obligation strategy call with Kevin. See your home value, the marketing plan, and what to expect.'
    elif cat == 'buying':
        head = 'Looking for the Right Home?'
        body = "Kevin knows Tampa Bay inside and out. He'll help you find a home that fits — and negotiate hard to get it."
    elif cat == 'luxury':
        head = 'Considering a Luxury Property?'
        body = 'Discreet representation, premium marketing, and decades of high-end Tampa Bay experience.'
    elif cat == 'market-update':
        head = "Want a Real Number on Your Home's Value?"
        body = "Forget the website estimates. Kevin will give you an honest valuation based on the current market."
    elif cat == 'storm-recovery':
        head = 'Storm-Affected? Kevin Can Help.'
        body = "From insurance to selling as-is or rebuilding, Kevin has guided dozens of Tampa Bay families through recovery."
    else:
        head = 'Interested in Tampa Bay Real Estate?'
        body = "Whether you're buying, selling, or just have questions — Kevin is here to help."
    return f'''      <div class="blog-post-cta">
        <h3>{html_escape(head)}</h3>
        <p>{html_escape(body)}</p>
        <a href="tel:7274108599" class="btn-primary">Call Kevin — 727-410-8599</a>
        <a href="/contact" class="btn-outline">Send a Message</a>
      </div>'''


# --- Sidebar ---
def build_sidebar_html(slug, primary_tag, all_posts, post_title):
    """Related Articles + CTA sidebar."""
    # Pick up to 3 most recent posts in same primary tag (excluding self).
    primary = primary_tag or 'news'
    related = []
    for p in all_posts:
        if p['slug'] == slug:
            continue
        tags = p.get('tags', []) or []
        if primary in tags:
            related.append(p)
        if len(related) >= 3:
            break
    # If not enough, fall back to most recent overall
    if len(related) < 3:
        for p in all_posts:
            if p['slug'] == slug:
                continue
            if p in related:
                continue
            related.append(p)
            if len(related) >= 3:
                break

    rel_html = ''
    for p in related[:3]:
        rel_html += (
            f'          <a class="sidebar-link" href="/blog/{html_escape(p["slug"])}">'
            f'{html_escape(p["title"])}</a>\n'
        )

    cta_title = 'Looking to Make a Move?'
    cta_body = 'Kevin Freel has been guiding Tampa Bay families home since 1985. Real talk, real results.'
    cta_btn = 'Call Kevin'

    return f'''      <aside class="blog-sidebar">
        <div class="sidebar-card">
          <div class="sidebar-head">Related Articles</div>
          <div class="sidebar-body">
{rel_html.rstrip()}
          </div>
        </div>
        <div class="sidebar-cta">
          <div class="sidebar-cta-title">{html_escape(cta_title)}</div>
          <p>{html_escape(cta_body)}</p>
          <a href="tel:7274108599" class="btn-primary">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="16" height="16"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z"/></svg>
            {html_escape(cta_btn)}
          </a>
          <a href="/contact" class="sidebar-cta-link">Send a message →</a>
        </div>
      </aside>'''


# --- Sanitizer (undo prior transforms for idempotency) ---
def sanitize_prior_transforms(body_html):
    """Strip prior video embeds, pill CTAs, inline CTAs, and unwrap article-card divs.
    Also reconstruct a YouTube link for any youtube-nocookie iframe found, so the
    video can be re-embedded fresh."""
    soup = BeautifulSoup(f'<div id="__sanroot">{body_html}</div>', 'html.parser')
    root = soup.find('div', id='__sanroot')
    if not root:
        return body_html

    # 1. Reconstruct a YouTube link from any iframe so find_youtube_id later still works
    for video_div in list(root.select('.blog-video')):
        iframe = video_div.find('iframe')
        if iframe:
            src = iframe.get('src', '')
            video_id = extract_youtube_id(src)
            if video_id:
                # Replace the video block with a plain anchor so it gets re-embedded
                a = soup.new_tag('a', href=f'https://www.youtube.com/watch?v={video_id}')
                a.string = 'Watch the video →'
                p = soup.new_tag('p')
                p.append(a)
                video_div.replace_with(p)
                continue
        video_div.decompose()

    # 2. Remove pill CTA rows
    for pill in list(root.select('.blog-cta-pill-row')):
        pill.decompose()

    # 3. Remove inline CTAs
    for cta in list(root.select('.blog-inline-cta')):
        cta.decompose()

    # 4. Unwrap .article-card divs (preserve children)
    for card in list(root.select('.article-card')):
        # Move children to the position of the card, then drop the card
        for child in list(card.children):
            if hasattr(child, 'extract'):
                card.insert_before(child.extract())
            else:
                card.insert_before(child)
        card.decompose()

    return root.decode_contents()


# --- HTML extraction ---
def extract_post_meta(html_text, slug, manifest_lookup):
    """Return dict of metadata from an existing post HTML."""
    soup = BeautifulSoup(html_text, 'html.parser')

    # Title from h1 inside .blog-post-hero (preferred) or fallback to manifest
    h1 = soup.select_one('.blog-post-hero h1')
    title = h1.get_text(' ', strip=True) if h1 else ''
    if not title:
        title = manifest_lookup.get(slug, {}).get('title', slug)

    # Date
    date_meta = soup.select_one('meta[property="article:published_time"]')
    iso_date = date_meta.get('content', '') if date_meta else ''
    if not iso_date:
        iso_date = manifest_lookup.get(slug, {}).get('date', '')
    dt, friendly = parse_iso_date(iso_date)

    # Description
    desc_meta = soup.select_one('meta[name="description"]')
    description = desc_meta.get('content', '') if desc_meta else ''
    if not description:
        description = manifest_lookup.get(slug, {}).get('excerpt', '')

    # Hero image
    og_img = soup.select_one('meta[property="og:image"]')
    hero_abs = og_img.get('content', '') if og_img else ''
    hero_local = manifest_lookup.get(slug, {}).get('hero_image', '')
    if not hero_local and hero_abs:
        m = re.match(r'https?://[^/]+(/.+)$', hero_abs)
        if m:
            hero_local = m.group(1)

    # Tags
    tags = manifest_lookup.get(slug, {}).get('tags', []) or []
    if not tags:
        tag_spans = soup.select('.blog-post-meta .tag')
        for ts in tag_spans:
            t = ts.get_text(' ', strip=True)
            # Find slug for this name
            for sl, name in TAG_DISPLAY.items():
                if name == t:
                    tags.append(sl)
                    break

    # Body (article) — support both old `.blog-post-body` and new `.blog-article`
    article = soup.select_one('article.blog-post-body, article.blog-article')
    body_html = article.decode_contents() if article else ''

    # Sanitize: undo prior transformations so re-runs are idempotent.
    if body_html:
        body_html = sanitize_prior_transforms(body_html)

    return {
        'slug': slug,
        'title': title,
        'iso_date': iso_date,
        'friendly_date': friendly,
        'sort_date': dt.strftime('%Y-%m-%d') if dt else '',
        'description': description,
        'hero_local': hero_local,
        'hero_abs': hero_abs or (
            f'https://kevinfreel.com{hero_local}' if hero_local and hero_local.startswith('/') else ''
        ),
        'tags': tags,
        'body_html_raw': body_html,
        'soup': soup,
    }


# --- Body transformation ---
def transform_body(body_html_raw, primary_tag, post_title):
    """Apply all transformations: YouTube embed, H3 cards, inline CTA.

    Returns (transformed_html, stats_dict)
    """
    stats = {
        'has_video': False,
        'h3_cards': 0,
        'inline_cta': False,
        'after_video_cta': False,
        'word_count': 0,
    }

    soup = BeautifulSoup(f'<div id="__root">{body_html_raw}</div>', 'html.parser')
    root = soup.find('div', id='__root')

    # 1. Find any YouTube reference, embed it, then strip the original link/iframe
    video_id = find_youtube_id(root)
    if video_id:
        remove_youtube_links(root)
        embed = BeautifulSoup(youtube_embed_html(video_id, post_title), 'html.parser')
        # Insert embed at the very top of the article body
        root.insert(0, embed)
        stats['has_video'] = True

    # 2. Insert pill CTA right after the video for property categories
    if stats['has_video']:
        if insert_after_video_cta(root, primary_tag):
            stats['after_video_cta'] = True

    # 3. Word count
    text = root.get_text(' ', strip=True)
    stats['word_count'] = len(text.split())

    # 4. Convert H3 sections to .article-card (must run before inline CTA so the CTA
    #    isn't captured inside a card)
    stats['h3_cards'] = style_h3_cards(root)

    # 5. Inject mid-body inline CTA for long posts
    if inject_inline_cta(root, primary_tag, stats['word_count']):
        stats['inline_cta'] = True

    # 6. Pretty-print: add newlines after major block tags so source is readable.
    transformed = root.decode_contents()
    # newline after closing block tags
    transformed = re.sub(
        r'(</(?:p|h2|h3|h4|ul|ol|li|blockquote|aside|div)>)(?!\n)',
        r'\1\n',
        transformed,
    )
    # newline after opening major container tags
    transformed = re.sub(
        r'(<(?:aside|div)\s[^>]*>)(?!\n)',
        r'\1\n',
        transformed,
    )
    transformed = re.sub(r'\n{3,}', '\n\n', transformed)
    return transformed.strip(), stats


# --- HTML template (unchanged nav/footer; new spec-conformant layout) ---

def get_nav_html():
    """Return the standard nav block. Wrapped in BEGIN_NAV/END_NAV markers so
    the user's separate nav-system update can find/replace it cleanly."""
    return '''  <!-- BEGIN_NAV -->
<!-- ── NAV ── -->
<nav class="nav scrolled" aria-label="Main navigation">
  <div class="nav-inner">
    <a href="/" class="nav-logo" aria-label="Kevin Freel — Realtor Since 1985"><span class="nav-logo-name">KEVIN <span>FREEL</span></span><span class="nav-logo-tagline">Realtor Since 1985</span></a>
    <ul class="nav-links">
      <li><a href="/search" data-nav="search">Search</a></li>
      <li><a href="/listings" data-nav="listings">Listings</a></li>
      <li><a href="/about" data-nav="about">About</a></li>
      <li><a href="/resources" data-nav="resources">Resources</a></li>
      <li><a href="/sellers" data-nav="sellers">Sellers</a></li>
      <li><a href="/buyers" data-nav="buyers">Buyers</a></li>
      <li><a href="/photography" data-nav="photography">Photography</a></li>
      <li><a href="/blog" data-nav="blog">Blog</a></li>
      <li><a href="/contact" data-nav="contact">Contact</a></li>
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
  <a href="/" data-nav="home">Home</a>
  <a href="/search" data-nav="search">Search</a>
  <a href="/listings" data-nav="listings">Listings</a>
  <a href="/about" data-nav="about">About</a>
  <a href="/resources" data-nav="resources">Resources</a>
  <a href="/sellers" data-nav="sellers">Sellers</a>
  <a href="/buyers" data-nav="buyers">Buyers</a>
  <a href="/photography" data-nav="photography">Photography</a>
  <a href="/blog" data-nav="blog">Blog</a>
  <a href="/contact" data-nav="contact">Contact</a>
  <a href="tel:7274108599" class="nav-cta">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z"/></svg>
    727-410-8599
  </a>
</div>
  <!-- END_NAV -->
'''


def get_footer_html():
    """Return footer wrapped in BEGIN_FOOTER/END_FOOTER markers."""
    return '''  <!-- BEGIN_FOOTER -->
<!-- ── FOOTER ── -->
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
      <a href="https://www.linkedin.com/in/kevin-freel-b0363029/" target="_blank" rel="noopener noreferrer" aria-label="LinkedIn">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.063 2.063 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
      </a>
      <a href="https://x.com/Sellingtampa1" target="_blank" rel="noopener noreferrer" aria-label="X (Twitter)">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231 5.45-6.231zm-1.161 17.52h1.833L7.084 4.126H5.117L17.083 19.77z"/></svg>
      </a>
      <a href="https://www.tiktok.com/@kevinfreel" target="_blank" rel="noopener noreferrer" aria-label="TikTok">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-5.2 1.74 2.89 2.89 0 012.31-4.64 2.93 2.93 0 01.88.13V9.4a6.84 6.84 0 00-1-.05A6.33 6.33 0 005.8 20.1a6.34 6.34 0 0010.86-4.43v-7a8.16 8.16 0 004.77 1.52v-3.4a4.85 4.85 0 01-1.84-.1z"/></svg>
      </a>
      <a href="https://share.google/KxNDtGpzlkBEwSXu2" target="_blank" rel="noopener noreferrer" aria-label="Google Business Profile">
        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A10.997 10.997 0 0012 23z"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
      </a>
    </div>
  </div>
</footer>
  <!-- END_FOOTER -->
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
  <meta name="twitter:image" content="{og_image_abs}">
  <meta property="article:published_time" content="{iso_date}">
  <meta property="article:author" content="Kevin Freel">

  <link rel="icon" href="/favicon.ico">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">

  <link rel="preload" as="font" type="font/woff2" href="/fonts/playfair-display.woff2" crossorigin>
  <link rel="preload" as="font" type="font/woff2" href="/fonts/inter.woff2" crossorigin>
  <link rel="preload" as="image" type="image/webp" href="{hero_local}" fetchpriority="high">

  <link rel="stylesheet" href="/fonts/fonts.css">
  <link rel="stylesheet" href="/styles.css">

  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    "headline": {title_json},
    "description": {desc_json},
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
      <img src="{hero_local}" alt="{title_esc}" loading="eager" width="1200" height="675">
      <div class="blog-post-hero-content">
        <a href="/blog" class="blog-back-link">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
          Back to Blog
        </a>
        <span class="blog-post-cat">{primary_cat_name}</span>
        <h1>{title_esc}</h1>
        <div class="post-meta">
          <span>Kevin Freel</span>
          <span class="post-meta-dot"></span>
          <span>{friendly_date}</span>
          <span class="post-meta-dot"></span>
          <span>{read_time}</span>
        </div>
      </div>
    </section>

    <div class="blog-post-wrap">
      <article class="blog-article">
{body_html}
      </article>

{sidebar}
    </div>

    <div class="blog-post-footer">
{final_cta}
    </div>

  </main>

{footer}
</body>
</html>
'''


# --- Build single post ---
def render_post(meta, manifest, force=False):
    slug = meta['slug']
    out_path = BLOG_DIR / f'{slug}.html'

    primary_tag = (meta.get('tags') or ['news'])[0]
    primary_name = TAG_DISPLAY.get(primary_tag, 'News')

    body_transformed, stats = transform_body(
        meta['body_html_raw'], primary_tag, meta['title']
    )

    # Indent body for template
    body_indented = '\n'.join('        ' + line for line in body_transformed.splitlines())

    # Sidebar (uses all manifest entries as candidate "all_posts")
    sidebar_html = build_sidebar_html(slug, primary_tag, manifest, meta['title'])

    # Final CTA
    final_cta = final_cta_html(primary_tag)

    # Read time
    read_time = estimate_read_time(
        BeautifulSoup(body_transformed, 'html.parser').get_text(' ', strip=True)
    )

    # Excerpt (140-char)
    desc = (meta.get('description') or '').strip()
    if not desc:
        first_p = BeautifulSoup(body_transformed, 'html.parser').find('p')
        if first_p:
            desc = first_p.get_text(' ', strip=True)
    desc_short = truncate(desc, 200)

    # Hero image fallback
    hero_local = meta.get('hero_local') or '/images/properties/grandifloras/exterior-aerial-1-md.webp'
    if not hero_local.startswith('/'):
        hero_local = '/' + hero_local
    hero_abs = meta.get('hero_abs')
    if not hero_abs:
        hero_abs = f'https://kevinfreel.com{hero_local}'

    page = POST_TEMPLATE.format(
        slug=slug,
        title_esc=html_escape(meta['title']),
        title_json=json.dumps(meta['title']),
        desc_esc=html_escape(desc_short),
        desc_json=json.dumps(desc_short),
        og_image_abs=html_escape(hero_abs),
        iso_date=meta['iso_date'],
        friendly_date=html_escape(meta['friendly_date']),
        read_time=read_time,
        primary_cat_name=html_escape(primary_name),
        hero_local=html_escape(hero_local),
        nav=get_nav_html(),
        footer=get_footer_html(),
        body_html=body_indented,
        sidebar=sidebar_html,
        final_cta=final_cta,
    )
    out_path.write_text(page, encoding='utf-8')
    return stats


# --- Index page builder ---

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
          <div class="blog-filters" id="blogFilters">
            <button class="filter-btn active" data-filter="all">All</button>
{filter_buttons}
          </div>
        </div>

        <div id="postGrid" class="blog-grid">
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
    """Build /blog/index.html with the BLOG-TEMPLATE.md spec.

    Cards: <a class="post-card" data-cat="...">
      <div class="post-card-thumb"><img></div>
      <div class="post-card-body">
        <div class="post-card-cat">Category</div>
        <div class="post-card-title">Title</div>
        <div class="post-card-meta">Date</div>
      </div>
    </a>
    """
    posts_sorted = sorted(posts, key=lambda p: p.get('sort_date', ''), reverse=True)

    # Build the set of categories that appear as PRIMARY tags only.
    # data-cat on each card is set to the display name of the primary tag,
    # so the filter buttons use display names matching data-cat exactly.
    primary_counts = {}
    for p in posts_sorted:
        tags = p.get('tags', [])
        if tags:
            primary_counts[tags[0]] = primary_counts.get(tags[0], 0) + 1
    ordered_tags = sorted(primary_counts.items(), key=lambda x: (-x[1], x[0]))

    filter_buttons = ''
    for tag_slug, _count in ordered_tags:
        name = TAG_DISPLAY.get(tag_slug, tag_slug.title())
        filter_buttons += f'            <button class="filter-btn" data-filter="{html_escape(name)}">{html_escape(name)}</button>\n'

    cards_html = ''
    for p in posts_sorted:
        slug = p['slug']
        title = p['title']
        excerpt = truncate(p.get('excerpt', ''), 140)
        hero = p.get('hero_image', '/images/properties/grandifloras/exterior-aerial-1-md.webp')
        date_f = p.get('friendly_date') or _friendly_from_iso(p.get('date', ''))
        primary_tag = (p.get('tags') or ['news'])[0]
        primary_name = TAG_DISPLAY.get(primary_tag, 'News')
        all_tag_slugs = ','.join(p.get('tags', []))
        cards_html += f'''          <a class="post-card" href="/blog/{html_escape(slug)}" data-cat="{html_escape(primary_name)}" data-title="{html_escape(title)}" data-excerpt="{html_escape(excerpt)}" data-tags="{html_escape(all_tag_slugs)}">
            <div class="post-card-thumb">
              <img src="{html_escape(hero)}" alt="{html_escape(title)}" width="600" height="338" loading="lazy">
            </div>
            <div class="post-card-body">
              <div class="post-card-cat">{html_escape(primary_name)}</div>
              <div class="post-card-title">{html_escape(title)}</div>
              <div class="post-card-meta">{html_escape(date_f)}</div>
            </div>
          </a>
'''

    page = INDEX_TEMPLATE.format(
        nav=get_nav_html(),
        footer=get_footer_html(),
        filter_buttons=filter_buttons.rstrip(),
        cards_html=cards_html.rstrip(),
    )
    (BLOG_DIR / 'index.html').write_text(page, encoding='utf-8')


def _friendly_from_iso(iso):
    dt, friendly = parse_iso_date(iso)
    return friendly


# --- Main ---

def main():
    only = None
    index_only = False
    force = True  # default to force since this is a restructure pass
    for a in sys.argv[1:]:
        if a.startswith('--only='):
            only = a.split('=', 1)[1]
        elif a == '--index-only':
            index_only = True
        elif a == '--no-force':
            force = False

    # Load manifest as the source of truth for slugs/categories/dates/heroes
    manifest = json.loads(MANIFEST_PATH.read_text())
    manifest_lookup = {p['slug']: p for p in manifest}

    if index_only:
        # Just rebuild the index — derive friendly dates and excerpts as needed
        for p in manifest:
            if 'friendly_date' not in p:
                _, p['friendly_date'] = parse_iso_date(p.get('date', ''))
            if 'sort_date' not in p:
                dt, _ = parse_iso_date(p.get('date', ''))
                p['sort_date'] = dt.strftime('%Y-%m-%d') if dt else ''
        build_index(manifest)
        log(f'Built index with {len(manifest)} posts.')
        return

    # Process each post
    log(f'Processing {len(manifest)} posts...')
    stats_total = {
        'processed': 0, 'video': 0, 'h3_cards': 0,
        'inline_cta': 0, 'after_video_cta': 0, 'failed': []
    }

    # We need full manifest entries with friendly_date/sort_date for the sidebar.
    # Pre-populate.
    for p in manifest:
        dt, friendly = parse_iso_date(p.get('date', ''))
        p['friendly_date'] = friendly
        p['sort_date'] = dt.strftime('%Y-%m-%d') if dt else ''
        # Backfill excerpt if missing
        p.setdefault('excerpt', '')

    sorted_manifest = sorted(manifest, key=lambda x: x.get('sort_date', ''), reverse=True)

    for i, entry in enumerate(sorted_manifest, 1):
        slug = entry['slug']
        if only and slug != only:
            continue
        in_path = BLOG_DIR / f'{slug}.html'
        if not in_path.exists():
            log(f'[{i}/{len(sorted_manifest)}] {slug} ! file not found, skipping')
            stats_total['failed'].append((slug, 'file not found'))
            continue
        try:
            html = in_path.read_text(encoding='utf-8')
            meta = extract_post_meta(html, slug, manifest_lookup)
            stats = render_post(meta, sorted_manifest, force=force)
            stats_total['processed'] += 1
            if stats['has_video']:
                stats_total['video'] += 1
            if stats['h3_cards']:
                stats_total['h3_cards'] += 1
            if stats['inline_cta']:
                stats_total['inline_cta'] += 1
            if stats['after_video_cta']:
                stats_total['after_video_cta'] += 1
            log(f'[{i}/{len(sorted_manifest)}] ✓ {slug} '
                f'(video={"Y" if stats["has_video"] else "n"} '
                f'cards={stats["h3_cards"]} '
                f'cta={"Y" if stats["inline_cta"] else "n"} '
                f'words={stats["word_count"]})')
        except Exception as e:
            log(f'[{i}/{len(sorted_manifest)}] ✗ {slug}: {e}')
            stats_total['failed'].append((slug, str(e)))

    # Build index from manifest
    build_index(sorted_manifest)

    # Re-write manifest with friendly_date for caller use
    MANIFEST_PATH.write_text(json.dumps(
        [{'slug': p['slug'], 'title': p['title'], 'date': p.get('date', ''),
          'excerpt': p.get('excerpt', ''),
          'hero_image': p.get('hero_image', ''),
          'tags': p.get('tags', []),
          'category': TAG_DISPLAY.get((p.get('tags') or ['news'])[0], 'News')}
         for p in sorted_manifest],
        indent=2))

    # Summary
    log('\n=== DONE ===')
    log(f'Processed: {stats_total["processed"]}')
    log(f'YouTube embedded: {stats_total["video"]}')
    log(f'H3 cards added: {stats_total["h3_cards"]}')
    log(f'Inline CTAs: {stats_total["inline_cta"]}')
    log(f'After-video CTAs: {stats_total["after_video_cta"]}')
    log(f'Failures: {len(stats_total["failed"])}')
    for slug, err in stats_total['failed']:
        log(f'  - {slug}: {err}')


if __name__ == '__main__':
    main()
