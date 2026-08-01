/* ── Active Nav Highlighting ── */
/* Reads window.location.pathname and adds .nav-active to the matching nav link.
   Drives off [data-nav] attribute set by partials/nav.html. */
(function () {
  var path = window.location.pathname.replace(/\/+$/, '') || '/';
  // Map path → nav key
  var slug;
  if (path === '/' || path === '') slug = 'home';
  else if (path.indexOf('/blog') === 0) slug = 'blog';
  else if (path.indexOf('/listings') === 0) slug = 'listings';
  else slug = path.replace(/^\//, '').split('/')[0];

  document.querySelectorAll('[data-nav="' + slug + '"]').forEach(function (a) {
    a.classList.add('nav-active');
  });
})();

/* ── reCAPTCHA v3 loader ──
   Injects the Google reCAPTCHA v3 script whenever a form is on the page.
   Exposes waitForRecaptchaToken(action) which resolves to the token, or
   '' if grecaptcha never becomes available (10s cap so we don't hang forever).
   Without this loader, form-notify silently rejects every submission with
   `missing_recaptcha_token`. */
var RECAPTCHA_SITE_KEY = '6Lck8aQsAAAAALMA-T6nwfkSf7bv4K-mOhkszeKh';
(function () {
  if (!document.querySelector('form[data-ajax], form[data-resource]')) return;
  if (document.querySelector('script[src*="recaptcha/api.js"]')) return;
  var s = document.createElement('script');
  s.src = 'https://www.google.com/recaptcha/api.js?render=' + RECAPTCHA_SITE_KEY;
  s.async = true;
  s.defer = true;
  document.head.appendChild(s);
})();
function waitForRecaptchaToken(action) {
  return new Promise(function (resolve) {
    var settled = false;
    function done(token) {
      if (settled) return;
      settled = true;
      resolve(typeof token === 'string' ? token : '');
    }
    // Hard cap. If the reCAPTCHA script is blocked (ad blockers), the key is
    // wrong, or grecaptcha.ready/execute never resolves, we MUST fall through
    // and post without a token rather than leave the visitor on a dead button.
    // form-notify records a tokenless post as `missing_recaptcha_token`, so the
    // lead is still recoverable from the Spam tab. A hang loses it outright.
    setTimeout(function () { done(''); }, 8000);
    var deadline = Date.now() + 8000;
    function tryOnce() {
      if (settled) return;
      if (typeof grecaptcha !== 'undefined' && grecaptcha.execute && grecaptcha.ready) {
        try {
          grecaptcha.ready(function () {
            try {
              grecaptcha.execute(RECAPTCHA_SITE_KEY, { action: action })
                .then(done, function () { done(''); });
            } catch (err) { done(''); }
          });
        } catch (err) { done(''); }
      } else if (Date.now() < deadline) {
        setTimeout(tryOnce, 150);
      } else {
        done('');
      }
    }
    tryOnce();
  });
}

/* ── Mobile Menu ── */
const menuBtn = document.getElementById('menu-btn');
const mobileMenu = document.getElementById('mobile-menu');
const menuOverlay = document.getElementById('menu-overlay');
const body = document.body;

function openMenu() {
  mobileMenu.classList.add('open');
  menuOverlay.classList.add('open');
  body.style.overflow = 'hidden';
  menuBtn.setAttribute('aria-expanded', 'true');
}
function closeMenu() {
  mobileMenu.classList.remove('open');
  menuOverlay.classList.remove('open');
  body.style.overflow = '';
  menuBtn.setAttribute('aria-expanded', 'false');
}

menuBtn.addEventListener('click', function () {
  mobileMenu.classList.contains('open') ? closeMenu() : openMenu();
});
menuOverlay.addEventListener('click', closeMenu);
document.querySelectorAll('.mobile-menu a').forEach(function (a) {
  a.addEventListener('click', closeMenu);
});

/* ── Sticky Nav Background ── */
const nav = document.querySelector('.nav');
window.addEventListener('scroll', function () {
  nav.classList.toggle('scrolled', window.scrollY > 60);
});

/* ── Scroll Reveal ── */
const reveals = document.querySelectorAll('.reveal');
const observer = new IntersectionObserver(function (entries) {
  entries.forEach(function (entry) {
    if (entry.isIntersecting) {
      entry.target.classList.add('visible');
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.15 });
reveals.forEach(function (el) { observer.observe(el); });

/* ── Stat Counter Animation ── */
function animateCounters() {
  document.querySelectorAll('[data-count]').forEach(function (el) {
    const target = parseInt(el.dataset.count, 10);
    const prefix = el.dataset.prefix || '';
    const suffix = el.dataset.suffix || '';
    const duration = 2000;
    const start = performance.now();
    function step(now) {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      el.textContent = prefix + Math.floor(target * eased).toLocaleString() + suffix;
      if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  });
}
const statsSection = document.querySelector('.stats');
if (statsSection) {
  const statsObs = new IntersectionObserver(function (entries) {
    if (entries[0].isIntersecting) {
      animateCounters();
      statsObs.unobserve(statsSection);
    }
  }, { threshold: 0.3 });
  statsObs.observe(statsSection);
}

/* ── Testimonial Carousel ── */
const track = document.querySelector('.testimonial-track');
const dots = document.querySelectorAll('.dot');
const prevBtn = document.querySelector('.carousel-prev');
const nextBtn = document.querySelector('.carousel-next');
let currentSlide = 0;

function getVisibleCount() {
  return window.innerWidth >= 1024 ? 3 : window.innerWidth >= 640 ? 2 : 1;
}

function getMaxSlide() {
  const cards = track ? track.children.length : 0;
  return Math.max(0, cards - getVisibleCount());
}

function goToSlide(n) {
  currentSlide = Math.max(0, Math.min(n, getMaxSlide()));
  const gap = 24;
  const card = track.children[0];
  const cardWidth = card.offsetWidth + gap;
  track.style.transform = 'translateX(-' + (currentSlide * cardWidth) + 'px)';
  dots.forEach(function (d, i) { d.classList.toggle('active', i === currentSlide); });
}

if (prevBtn && nextBtn) {
  prevBtn.addEventListener('click', function () { goToSlide(currentSlide - 1); });
  nextBtn.addEventListener('click', function () { goToSlide(currentSlide + 1); });
}
dots.forEach(function (d, i) {
  d.addEventListener('click', function () { goToSlide(i); });
});

window.addEventListener('resize', function () { goToSlide(currentSlide); });

/* ── Property Search (redirects to Zillow) ── */
var searchForm = document.querySelector('form[data-search]');
if (searchForm) {
  searchForm.addEventListener('submit', function (e) {
    e.preventDefault();
    var area = searchForm.querySelector('[name="area"]').value;
    var minPrice = searchForm.querySelector('[name="min_price"]').value;
    var maxPrice = searchForm.querySelector('[name="max_price"]').value;
    var beds = searchForm.querySelector('[name="beds"]').value;
    var type = searchForm.querySelector('[name="type"]').value;

    // Build Zillow URL. Example: /homes/for_sale/south-tampa-tampa-fl/3-_beds/500000-1000000_price/
    var slug = area || 'tampa-fl';
    var path = 'https://www.zillow.com/homes/for_sale/' + slug + '/';
    var filters = [];
    if (beds) filters.push(beds + '-_beds');
    if (minPrice || maxPrice) {
      var min = minPrice || '0';
      var max = maxPrice || '10000000';
      filters.push(min + '-' + max + '_price');
    }
    if (type === 'house') filters.push('house_type');
    if (type === 'condo') filters.push('condo_type');
    if (type === 'townhouse') filters.push('townhouse_type');
    if (filters.length) path += filters.join('/') + '/';

    window.open(path, '_blank', 'noopener');
  });
}

/* ── Recommendation Wizard ── */
var wizardForm = document.querySelector('form[data-wizard]');
if (wizardForm) {
  var wizardResults = document.getElementById('wizard-results');
  var allRecs = {
    foodie: [
      { name: 'Bern\'s Steak House', desc: 'Iconic Tampa steakhouse famous for dry-aged beef and a legendary wine cellar.', area: 'South Tampa' },
      { name: 'Ulele', desc: 'Native-inspired Florida cuisine on the Tampa Riverwalk with a spring-fed waterway.', area: 'Tampa Heights' },
      { name: 'Mise en Place', desc: 'Fine dining with seasonal menus — a Tampa institution since 1986.', area: 'Downtown Tampa' }
    ],
    waterfront: [
      { name: 'Hula Bay Club', desc: 'Waterfront dining with tiki vibes and one of the best sunset views in Tampa Bay.', area: 'Rocky Point' },
      { name: 'The Don CeSar', desc: 'The pink palace — historic beachfront hotel and landmark on St. Pete Beach.', area: 'St. Pete Beach' },
      { name: 'Clearwater Beach', desc: 'Powder-white sand and turquoise water — consistently ranked top US beach.', area: 'Clearwater' }
    ],
    outdoorsy: [
      { name: 'Bayshore Boulevard', desc: 'The world\'s longest continuous sidewalk (4.5 miles) along Tampa Bay.', area: 'South Tampa' },
      { name: 'Honeymoon Island State Park', desc: 'Pristine beach, nature trails, and osprey sanctuary — ferry access to Caladesi.', area: 'Dunedin' },
      { name: 'Tampa Riverwalk', desc: '2.6-mile scenic path connecting parks, museums, and restaurants.', area: 'Downtown Tampa' }
    ],
    family: [
      { name: 'Busch Gardens', desc: 'Thrill rides and African-themed zoo attractions for the whole family.', area: 'Tampa' },
      { name: 'Florida Aquarium', desc: 'Home to 7,000+ sea creatures plus outdoor splash pad and dolphin cruises.', area: 'Downtown Tampa' },
      { name: 'Glazer Children\'s Museum', desc: 'Interactive hands-on exhibits — a rainy-day staple for families.', area: 'Downtown Tampa' }
    ],
    nightlife: [
      { name: 'Ybor City', desc: 'Historic cigar district with craft cocktail bars, live music, and Cuban flair.', area: 'Ybor City' },
      { name: 'Armature Works', desc: 'Restored trolley warehouse with food hall, rooftop bar, and riverfront patio.', area: 'Tampa Heights' },
      { name: 'SoHo (South Howard)', desc: 'The hottest stretch of bars, rooftops, and restaurants in South Tampa.', area: 'South Tampa' }
    ],
    artsy: [
      { name: 'Dali Museum', desc: 'World\'s most comprehensive collection of Salvador Dali\'s work, in a stunning building.', area: 'St. Petersburg' },
      { name: 'Tampa Museum of Art', desc: 'Modern and contemporary art along the Hillsborough River.', area: 'Downtown Tampa' },
      { name: 'Central Avenue', desc: 'St. Pete\'s arts district — galleries, murals, and monthly ArtWalk.', area: 'St. Petersburg' }
    ]
  };

  wizardForm.addEventListener('submit', function (e) {
    e.preventDefault();
    var checked = wizardForm.querySelectorAll('input[name="mood"]:checked');
    if (!checked.length) return;
    var moods = [];
    checked.forEach(function (c) { moods.push(c.value); });

    var picks = [];
    var seen = {};
    for (var i = 0; i < moods.length && picks.length < 3; i++) {
      var options = allRecs[moods[i]] || [];
      for (var j = 0; j < options.length && picks.length < 3; j++) {
        if (!seen[options[j].name]) {
          picks.push(options[j]);
          seen[options[j].name] = true;
        }
      }
    }

    if (!wizardResults) return;
    var html = '<h3>Kevin\'s Top Three Picks</h3><div class="result-grid">';
    picks.forEach(function (p) {
      html += '<div class="result-card"><div class="result-area">' + p.area + '</div><h4>' + p.name + '</h4><p>' + p.desc + '</p></div>';
    });
    html += '</div>';
    wizardResults.innerHTML = html;
    wizardResults.classList.add('visible');
    wizardResults.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
}

/* ── Resource Lead Forms (via /api/lead-magnet → PDF or page redirect) ── */
document.querySelectorAll('form[data-resource]').forEach(function (rForm) {
  rForm.addEventListener('submit', async function (e) {
    e.preventDefault();
    var btn = rForm.querySelector('button[type="submit"]');
    var status = rForm.querySelector('.resource-status');
    var original = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Sending...';
    if (status) { status.textContent = ''; status.className = 'resource-status'; }

    var data = {};
    new FormData(rForm).forEach(function (v, k) { data[k] = v; });

    // reCAPTCHA v3 token — form-notify rejects without it (loader is at top of file)
    data.recaptcha_token = await waitForRecaptchaToken('lead_magnet');

    // PDF magnets: pre-open a tab synchronously so popup blockers don't fire
    // (browsers only allow window.open during a user gesture chain)
    var slug = rForm.getAttribute('data-resource');
    var pdfMagnets = { 'buyers-guide': '/pdfs/What-To-Expect.pdf', 'mortgage-roadmap': '/pdfs/Mortgage-Financing-Roadmap.pdf' };
    var pdfTab = pdfMagnets[slug] ? window.open('about:blank', '_blank') : null;

    try {
      var res = await fetch('/api/lead-magnet/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      // Never assume success. A non-2xx response, or a body we cannot parse,
      // means the lead may not have been recorded, so show the fallback.
      var json = await res.json().catch(function () { return {}; });
      var accepted = res.ok && json.success !== false && json.accepted !== false;

      if (accepted) {
        // GTM conversion event
        window.dataLayer = window.dataLayer || [];
        window.dataLayer.push({ event: 'form_submission', form_type: 'resource-' + slug, form_location: window.location.pathname });

        // Handle redirect / PDF open
        if (json.next && pdfTab && pdfMagnets[slug]) {
          // PDF magnet — point the pre-opened tab at the PDF
          pdfTab.location.href = json.next;
          if (status) { status.textContent = 'Your guide is opening in a new tab. Check your email too!'; status.className = 'resource-status success'; }
        } else if (json.next && slug === 'home-valuation') {
          // Home valuation — full-page redirect to the questionnaire
          window.location.href = json.next;
          return;
        } else if (json.next) {
          // Page magnets — open in a new tab so they don't lose context
          window.open(json.next, '_blank');
          if (status) { status.textContent = 'Sent! Opening your guide in a new tab.'; status.className = 'resource-status success'; }
        } else {
          if (status) { status.textContent = 'Thanks! Check your email — Kevin will send it shortly.'; status.className = 'resource-status success'; }
        }

        rForm.querySelectorAll('input[type="email"], input[type="text"]:not([type="hidden"])').forEach(function (i) { if (i.name !== '_honey') i.value = ''; });
        btn.textContent = 'Sent!';
        setTimeout(function () { btn.textContent = original; btn.disabled = false; }, 3500);
      } else {
        if (pdfTab) pdfTab.close();
        if (status) { status.textContent = "We couldn't send that just now. Please call Kevin at 727-410-8599."; status.className = 'resource-status error'; }
        btn.disabled = false;
        btn.textContent = original;
      }
    } catch (err) {
      if (pdfTab) pdfTab.close();
      if (status) { status.textContent = "We couldn't send that just now. Please call Kevin at 727-410-8599."; status.className = 'resource-status error'; }
      btn.disabled = false;
      btn.textContent = original;
    }
  });
});

/* ── Photo Gallery with Filters + Lightbox ── */
(function () {
  var grid = document.querySelector('.gallery-grid');
  if (!grid) return;
  var items = grid.querySelectorAll('.gallery-item');
  var filters = document.querySelectorAll('.gallery-filter');
  var empty = document.querySelector('.gallery-empty');
  var lightbox = document.getElementById('lightbox');
  var lightboxImg = document.getElementById('lightbox-img');
  var lightboxCaption = document.getElementById('lightbox-caption');
  var currentIndex = 0;
  var visibleItems = Array.prototype.slice.call(items);

  function applyFilter(filter) {
    visibleItems = [];
    items.forEach(function (item) {
      var cats = (item.dataset.category || '').split(' ');
      var property = item.dataset.property || '';
      var match = filter === 'all' || cats.indexOf(filter) !== -1 || property === filter;
      if (match) {
        item.classList.remove('hidden');
        visibleItems.push(item);
      } else {
        item.classList.add('hidden');
      }
    });
    if (empty) empty.classList.toggle('visible', visibleItems.length === 0);
  }

  filters.forEach(function (btn) {
    btn.addEventListener('click', function () {
      filters.forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      applyFilter(btn.dataset.filter);
    });
  });

  function openLightbox(index) {
    if (!lightbox || !lightboxImg) return;
    currentIndex = index;
    var item = visibleItems[index];
    var src = item.dataset.full || item.querySelector('img').src;
    var caption = item.dataset.caption || '';
    lightboxImg.src = src;
    lightboxImg.alt = caption;
    if (lightboxCaption) lightboxCaption.textContent = caption;
    lightbox.classList.add('open');
    body.style.overflow = 'hidden';
  }

  function closeLightbox() {
    if (!lightbox) return;
    lightbox.classList.remove('open');
    body.style.overflow = '';
    lightboxImg.src = '';
  }

  function nextImage() {
    if (!visibleItems.length) return;
    openLightbox((currentIndex + 1) % visibleItems.length);
  }

  function prevImage() {
    if (!visibleItems.length) return;
    openLightbox((currentIndex - 1 + visibleItems.length) % visibleItems.length);
  }

  items.forEach(function (item, i) {
    item.addEventListener('click', function () {
      var idx = visibleItems.indexOf(item);
      if (idx !== -1) openLightbox(idx);
    });
  });

  var closeBtn = document.querySelector('.lightbox-close');
  var prevBtn = document.querySelector('.lightbox-prev');
  var nextBtn = document.querySelector('.lightbox-next');
  if (closeBtn) closeBtn.addEventListener('click', closeLightbox);
  if (prevBtn) prevBtn.addEventListener('click', prevImage);
  if (nextBtn) nextBtn.addEventListener('click', nextImage);
  if (lightbox) {
    lightbox.addEventListener('click', function (e) {
      if (e.target === lightbox) closeLightbox();
    });
  }
  document.addEventListener('keydown', function (e) {
    if (!lightbox || !lightbox.classList.contains('open')) return;
    if (e.key === 'Escape') closeLightbox();
    if (e.key === 'ArrowRight') nextImage();
    if (e.key === 'ArrowLeft') prevImage();
  });
})();

/* ── Blog Index Search + Filter ── */
/* Supports both new spec (#postGrid + .post-card[data-cat]) and the
   legacy .blog-card[data-tags] pattern. */
(function () {
  var grid = document.querySelector('#postGrid, .blog-grid');
  if (!grid) return;
  var cards = grid.querySelectorAll('.post-card, .blog-card');
  if (!cards.length) return;

  var searchInput = document.getElementById('blog-search');
  var filterBtns = document.querySelectorAll('.filter-btn, .blog-tag-filter');
  var empty = document.querySelector('.blog-empty');
  var activeFilter = 'all';
  var activeQuery = '';

  function matchesFilter(card) {
    if (activeFilter === 'all') return true;
    var f = activeFilter.toLowerCase();
    var cat = (card.dataset.cat || '').toLowerCase();
    var tags = (card.dataset.tags || '').toLowerCase();
    if (cat === f) return true;
    if (tags.split(',').map(function (t) { return t.trim(); }).indexOf(f) !== -1) return true;
    return false;
  }

  function apply() {
    var q = activeQuery.toLowerCase();
    var visible = 0;
    cards.forEach(function (card) {
      var title = (card.dataset.title || card.querySelector('.post-card-title, h3') && (card.querySelector('.post-card-title, h3').textContent) || '').toLowerCase();
      var excerpt = (card.dataset.excerpt || '').toLowerCase();
      var tags = (card.dataset.tags || '').toLowerCase();
      var cat = (card.dataset.cat || '').toLowerCase();
      var filterMatch = matchesFilter(card);
      var queryMatch = !q || title.indexOf(q) !== -1 || excerpt.indexOf(q) !== -1 || tags.indexOf(q) !== -1 || cat.indexOf(q) !== -1;
      if (filterMatch && queryMatch) {
        card.classList.remove('hidden');
        card.style.display = '';
        visible++;
      } else {
        card.classList.add('hidden');
        card.style.display = 'none';
      }
    });
    if (empty) empty.classList.toggle('visible', visible === 0);
  }

  filterBtns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      filterBtns.forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      activeFilter = btn.dataset.filter || 'all';
      apply();
    });
  });

  if (searchInput) {
    searchInput.addEventListener('input', function (e) {
      activeQuery = e.target.value || '';
      apply();
    });
  }
})();

/* ── Contact Form (AJAX submit) ── */
var form = document.querySelector('form[data-ajax]');
if (form) {
  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    var btn = form.querySelector('.form-submit');
    var status = document.getElementById('form-status');
    var originalLabel = btn.textContent;
    btn.disabled = true;
    btn.textContent = 'Sending...';
    if (status) { status.textContent = ''; status.className = 'form-status'; }

    var data = {};
    new FormData(form).forEach(function (v, k) { data[k] = v; });

    // reCAPTCHA v3 token — form-notify rejects without it (loader is at top of file)
    data.recaptcha_token = await waitForRecaptchaToken('contact');

    try {
      var res = await fetch(form.action, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      // Only redirect to the thank-you page once the server has actually
      // accepted the lead. form-notify can return 200 with accepted:false.
      var json = await res.json().catch(function () { return {}; });
      if (res.ok && json.success !== false && json.accepted !== false) {
        window.location.href = '/thank-you/';
      } else {
        if (status) { status.textContent = "We couldn't send that just now. Please call Kevin at 727-410-8599."; status.className = 'form-status error'; }
        btn.disabled = false;
        btn.textContent = originalLabel;
      }
    } catch (err) {
      if (status) { status.textContent = "We couldn't send that just now. Please call Kevin at 727-410-8599."; status.className = 'form-status error'; }
      btn.disabled = false;
      btn.textContent = originalLabel;
    }
  });
}
