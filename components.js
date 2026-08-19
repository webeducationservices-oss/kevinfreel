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
    // The ten neighborhood links in the jumbo panel all share
    // data-nav="neighborhoods", which is what lights the group up on any of the
    // 52 neighborhood pages. Matching them on the slug alone would turn all ten
    // red at once, so a link whose href has more than one path segment has to
    // match the whole path before it counts as the current page.
    var href = (a.getAttribute('href') || '').replace(/\/+$/, '');
    if (href.split('/').length > 2 && href !== path) return;
    a.classList.add('nav-active');
  });

  /* megaActive: light up a top-level jumbo item when ANY page inside its group
     is the current page. The group is read from the [data-nav] values the item
     actually contains, so adding a link to a panel needs no second edit here.
     data-nav-extra on the trigger covers a destination that is only reachable
     from that panel's CTA button: those buttons deliberately carry no data-nav,
     because .nav-active paints text red and the button is already red. */
  function megaActive(group, trigger) {
    if (!trigger) return;
    var slugs = [];
    group.querySelectorAll('[data-nav]').forEach(function (el) {
      slugs.push(el.getAttribute('data-nav'));
    });
    (trigger.getAttribute('data-nav-extra') || '').split(',').forEach(function (s) {
      s = s.trim();
      if (s) slugs.push(s);
    });
    if (slugs.indexOf(slug) !== -1) trigger.classList.add('nav-active');
  }

  document.querySelectorAll('.nav-item.has-mega').forEach(function (item) {
    megaActive(item, item.querySelector('.nav-trigger'));
  });
  document.querySelectorAll('#mobile-menu .m-acc').forEach(function (acc) {
    megaActive(acc, acc.querySelector('.m-acc-trigger'));
  });
})();

/* ── Jumbo (mega) menu ── Desktop panels.
   Hover is pure CSS so the menu still works with JS disabled. This layer adds
   what CSS cannot do: click/keyboard opening, aria-expanded, and Escape.
   Escape also sets .mega-suppressed on the bar, which is the only way to close
   a panel the pointer is still hovering; moving off the item clears it. */
(function () {
  var bar = document.querySelector('.nav');
  var items = document.querySelectorAll('.nav-item.has-mega');
  if (!bar || !items.length) return;

  function setOpen(item, isOpen) {
    item.classList.toggle('open', isOpen);
    var trigger = item.querySelector('.nav-trigger');
    if (trigger) trigger.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  }

  function closeAll() {
    items.forEach(function (item) { setOpen(item, false); });
  }

  // Set while Escape hands focus back to a trigger, so the focus handler below
  // does not immediately reopen the panel Escape was asked to close.
  var escaping = false;

  items.forEach(function (item) {
    var trigger = item.querySelector('.nav-trigger');
    if (!trigger) return;

    // Tabbing onto a trigger opens its panel, so a keyboard user sees the same
    // thing a mouse user sees on hover. Gated on :focus-visible because a mouse
    // click also focuses the button, and opening here would make the click
    // handler below read it as already open and toggle it straight shut.
    trigger.addEventListener('focus', function () {
      if (escaping) return;
      if (!trigger.matches(':focus-visible')) return;
      items.forEach(function (other) { if (other !== item) setOpen(other, false); });
      bar.classList.remove('mega-suppressed');
      setOpen(item, true);
    });

    trigger.addEventListener('click', function () {
      var isOpen = item.classList.contains('open');
      closeAll();
      bar.classList.remove('mega-suppressed');
      if (!isOpen) setOpen(item, true);
    });

    // Down arrow opens the panel and steps into it, the usual disclosure idiom.
    trigger.addEventListener('keydown', function (e) {
      if (e.key !== 'ArrowDown' && e.key !== 'Down') return;
      e.preventDefault();
      closeAll();
      bar.classList.remove('mega-suppressed');
      setOpen(item, true);
      var panel = item.querySelector('.mega');
      var first = panel && panel.querySelector('a');
      if (!first) return;
      // Force the style recalc first. The panel is visibility:hidden until the
      // .open class lands, and a hidden element cannot take focus, so calling
      // focus() in the same tick would silently do nothing.
      void panel.offsetHeight;
      first.focus();
    });

    // Tabbing out of the group closes it. relatedTarget is where focus is
    // going, so moving between two links inside the same panel is ignored.
    item.addEventListener('focusout', function (e) {
      if (!e.relatedTarget || !item.contains(e.relatedTarget)) setOpen(item, false);
    });

    // Hovering an item must not leave a keyboard-opened panel behind it. If
    // focus was sitting in the panel being closed, take it back to that
    // trigger rather than stranding it on something now hidden.
    item.addEventListener('mouseenter', function () {
      var stranded = null;
      items.forEach(function (other) {
        if (other === item) return;
        if (other.contains(document.activeElement)) stranded = other;
        setOpen(other, false);
      });
      if (stranded) {
        var back = stranded.querySelector('.nav-trigger');
        if (back) back.focus();
      }
    });
    item.addEventListener('mouseleave', function () {
      bar.classList.remove('mega-suppressed');
    });
  });

  // Escape has to be caught on the document: a panel opened by hover alone has
  // no focus inside the bar, so a listener on .nav would never hear the key.
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape' && e.key !== 'Esc') return;
    var openItem = null;
    items.forEach(function (item) {
      if (item.classList.contains('open')) openItem = item;
    });
    var hovered = bar.querySelector('.nav-item.has-mega:hover');
    if (!openItem && !hovered) return;
    closeAll();
    bar.classList.add('mega-suppressed');
    // Never strand focus on a panel we just hid.
    if (openItem && openItem.contains(document.activeElement)) {
      var trigger = openItem.querySelector('.nav-trigger');
      if (trigger) {
        escaping = true;
        trigger.focus();
        escaping = false;
      }
    }
  });

  document.addEventListener('click', function (e) {
    if (!bar.contains(e.target)) closeAll();
  });
})();

/* ── Jumbo menu, mobile ── The same groups as accordions in the drawer.
   One open at a time, matching the desktop panels and keeping the drawer
   short enough to stay oriented in. */
(function () {
  var accs = document.querySelectorAll('#mobile-menu .m-acc');
  if (!accs.length) return;

  function collapse(acc) {
    var trigger = acc.querySelector('.m-acc-trigger');
    var panel = acc.querySelector('.m-acc-panel');
    acc.classList.remove('open');
    if (trigger) trigger.setAttribute('aria-expanded', 'false');
    if (panel) panel.style.maxHeight = '';
  }

  function expand(acc) {
    var trigger = acc.querySelector('.m-acc-trigger');
    var panel = acc.querySelector('.m-acc-panel');
    acc.classList.add('open');
    if (trigger) trigger.setAttribute('aria-expanded', 'true');
    // Animate to the panel's real height rather than a guessed max, so a long
    // group is never clipped and a short one does not crawl open.
    if (panel) panel.style.maxHeight = panel.scrollHeight + 'px';
  }

  accs.forEach(function (acc) {
    var trigger = acc.querySelector('.m-acc-trigger');
    if (!trigger || !acc.querySelector('.m-acc-panel')) return;
    trigger.addEventListener('click', function () {
      var wasOpen = acc.classList.contains('open');
      accs.forEach(collapse);
      if (!wasOpen) expand(acc);
    });
  });

  // Re-measure on resize: a rotated phone changes how many lines each label
  // wraps to, and a stale pixel height would clip the group.
  window.addEventListener('resize', function () {
    accs.forEach(function (acc) {
      if (!acc.classList.contains('open')) return;
      var panel = acc.querySelector('.m-acc-panel');
      if (!panel) return;
      panel.style.maxHeight = 'none';
      var h = panel.scrollHeight;
      panel.style.maxHeight = h + 'px';
    });
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

/* ── Traffic source attribution ──
   Classifies how the visitor got here so leads land tagged Organic / Paid /
   Referral / Email instead of an anonymous row. Caches the FIRST non-direct
   result in sessionStorage, because internal navigation strips ?utm_ params and
   the attribution would otherwise decay to DIRECT_TRAFFIC before the visitor
   reaches a form. A fresher campaign link in the same session overrides it.
   Spec: Desktop/Websites/FORMS-SOURCE-ATTRIBUTION.md */
function getSourceAttribution() {
  var KEY = 'wes_first_touch_source';
  var p = new URLSearchParams(window.location.search);
  var hasFresh = p.has('utm_source') || p.has('gclid') || p.has('gbraid') || p.has('wbraid') || p.has('fbclid') || p.has('msclkid');
  if (!hasFresh) {
    try {
      var cached = JSON.parse(sessionStorage.getItem(KEY) || 'null');
      if (cached) return cached;
    } catch (e) {}
  }
  var utm_source = (p.get('utm_source') || '').toLowerCase();
  var utm_medium = (p.get('utm_medium') || '').toLowerCase();
  var utm_campaign = p.get('utm_campaign') || '';
  var utm_term = p.get('utm_term') || '';
  var gclid = p.get('gclid') || p.get('gbraid') || p.get('wbraid'), fbclid = p.get('fbclid'), msclkid = p.get('msclkid');
  var ref = document.referrer || '';
  var refHost = ''; try { refHost = ref ? new URL(ref).hostname : ''; } catch (e) {}
  var offSite = ref && refHost && refHost !== window.location.hostname;
  var src = 'DIRECT_TRAFFIC', d1 = '', d2 = '';

  if (gclid)        { src = 'PAID_SEARCH'; d1 = 'google'; d2 = utm_term || utm_campaign || gclid; }
  else if (msclkid) { src = 'PAID_SEARCH'; d1 = 'bing';   d2 = utm_term || utm_campaign || msclkid; }
  else if (fbclid)  { src = 'PAID_SOCIAL'; d1 = utm_source || 'facebook'; d2 = utm_campaign || fbclid; }
  else if (utm_source) {
    if (utm_medium === 'email' || utm_source === 'hs_email') { src = 'EMAIL_MARKETING'; d1 = utm_source; d2 = utm_campaign; }
    else if (utm_medium === 'cpc' || utm_medium === 'ppc' || utm_medium === 'paid') {
      src = /google|bing|yahoo/.test(utm_source) ? 'PAID_SEARCH' : 'PAID_SOCIAL';
      d1 = utm_source; d2 = utm_term || utm_campaign;
    }
    else if (utm_medium === 'social' || utm_medium === 'social_media') { src = 'SOCIAL_MEDIA'; d1 = utm_source; d2 = utm_campaign; }
    else if (utm_medium === 'referral') { src = 'REFERRALS'; d1 = utm_source; d2 = utm_campaign; }
    else { src = 'OTHER_CAMPAIGNS'; d1 = utm_source; d2 = utm_campaign; }
  } else if (offSite) {
    if (/^(www\.)?(google|bing|duckduckgo|yahoo|ecosia)\.[a-z.]+$/i.test(refHost)) { src = 'ORGANIC_SEARCH'; d1 = refHost.replace(/^www\./,'').split('.')[0]; }
    else if (/^(www\.)?(facebook|instagram|twitter|x|linkedin|tiktok|pinterest|reddit|youtube|t)\.com$/i.test(refHost)) { src = 'SOCIAL_MEDIA'; d1 = refHost.replace(/^www\./,'').split('.')[0]; }
    else { src = 'REFERRALS'; d1 = refHost; }
  }

  var result = {
    analytics_source: src,
    analytics_source_data_1: d1,
    analytics_source_data_2: d2,
    first_referrer: ref,
    first_url: window.location.href
  };
  try { sessionStorage.setItem(KEY, JSON.stringify(result)); } catch (e) {}
  return result;
}

/* First-touch must be captured on the LANDING page, not at submit. Running the
   classifier once at load caches the ad click ID while it is still in the URL;
   at submit the cached first touch wins. Fleet bug: 22 of 26 Millennium paid
   leads logged as DIRECT_TRAFFIC because nothing ran until the form page. */
try { getSourceAttribution(); } catch (e) {}


/* Capture on EVERY page load, not just the one with the form. Landing pages are
   usually a blog post; the form is two clicks later, by which point the referrer
   and utm params are long gone. */
try { getSourceAttribution(); } catch (e) { /* attribution is best-effort */ }

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
/* Escape closes the drawer and hands focus back to the button that opened it.
   The accordion triggers are buttons, not links, so they are untouched by the
   close-on-click above and can expand a group without dismissing the drawer. */
document.addEventListener('keydown', function (e) {
  if (e.key !== 'Escape' && e.key !== 'Esc') return;
  if (!mobileMenu.classList.contains('open')) return;
  closeMenu();
  menuBtn.focus();
});
/* Resizing up to the desktop bar with the drawer open would otherwise leave the
   page scroll locked behind a drawer that is no longer reachable. */
window.addEventListener('resize', function () {
  if (window.innerWidth > 960 && mobileMenu.classList.contains('open')) closeMenu();
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
      { name: 'Mise en Place', desc: 'Fine dining with seasonal menus, a Tampa institution since 1986.', area: 'Downtown Tampa' }
    ],
    waterfront: [
      { name: 'Hula Bay Club', desc: 'Waterfront dining with tiki vibes and one of the best sunset views in Tampa Bay.', area: 'Rocky Point' },
      { name: 'The Don CeSar', desc: 'The pink palace, the historic beachfront hotel and landmark on St. Pete Beach.', area: 'St. Pete Beach' },
      { name: 'Clearwater Beach', desc: 'Powder-white sand and turquoise water, consistently ranked top US beach.', area: 'Clearwater' }
    ],
    outdoorsy: [
      { name: 'Bayshore Boulevard', desc: 'The world\'s longest continuous sidewalk (4.5 miles) along Tampa Bay.', area: 'South Tampa' },
      { name: 'Honeymoon Island State Park', desc: 'Pristine beach, nature trails, and osprey sanctuary, with ferry access to Caladesi.', area: 'Dunedin' },
      { name: 'Tampa Riverwalk', desc: '2.6-mile scenic path connecting parks, museums, and restaurants.', area: 'Downtown Tampa' }
    ],
    family: [
      { name: 'Busch Gardens', desc: 'Thrill rides and African-themed zoo attractions for the whole family.', area: 'Tampa' },
      { name: 'Florida Aquarium', desc: 'Home to 7,000+ sea creatures plus outdoor splash pad and dolphin cruises.', area: 'Downtown Tampa' },
      { name: 'Glazer Children\'s Museum', desc: 'Interactive hands-on exhibits, a rainy-day staple for families.', area: 'Downtown Tampa' }
    ],
    nightlife: [
      { name: 'Ybor City', desc: 'Historic cigar district with craft cocktail bars, live music, and Cuban flair.', area: 'Ybor City' },
      { name: 'Armature Works', desc: 'Restored trolley warehouse with food hall, rooftop bar, and riverfront patio.', area: 'Tampa Heights' },
      { name: 'SoHo (South Howard)', desc: 'The hottest stretch of bars, rooftops, and restaurants in South Tampa.', area: 'South Tampa' }
    ],
    artsy: [
      { name: 'Dali Museum', desc: 'World\'s most comprehensive collection of Salvador Dali\'s work, in a stunning building.', area: 'St. Petersburg' },
      { name: 'Tampa Museum of Art', desc: 'Modern and contemporary art along the Hillsborough River.', area: 'Downtown Tampa' },
      { name: 'Central Avenue', desc: 'St. Pete\'s arts district: galleries, murals, and monthly ArtWalk.', area: 'St. Petersburg' }
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

    // reCAPTCHA v3 token: form-notify rejects without it (loader is at top of file)
    data.recaptcha_token = await waitForRecaptchaToken('lead_magnet');

    // Spread LAST so a same-named form field can't clobber the attribution.
    try { Object.assign(data, getSourceAttribution()); } catch (e) { console.warn('source-attr:', e); }

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
          // PDF magnet: point the pre-opened tab at the PDF
          pdfTab.location.href = json.next;
          if (status) { status.textContent = 'Your guide is opening in a new tab. Check your email too!'; status.className = 'resource-status success'; }
        } else if (json.next && slug === 'home-valuation') {
          // Home valuation: full-page redirect to the questionnaire
          window.location.href = json.next;
          return;
        } else if (json.next) {
          // Page magnets: open in a new tab so they don't lose context
          window.open(json.next, '_blank');
          if (status) { status.textContent = 'Sent! Opening your guide in a new tab.'; status.className = 'resource-status success'; }
        } else {
          if (status) { status.textContent = 'Thanks! Check your email, Kevin will send it shortly.'; status.className = 'resource-status success'; }
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

    // reCAPTCHA v3 token: form-notify rejects without it (loader is at top of file)
    data.recaptcha_token = await waitForRecaptchaToken('contact');

    // Spread LAST so a same-named form field can't clobber the attribution.
    try { Object.assign(data, getSourceAttribution()); } catch (e) { console.warn('source-attr:', e); }

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
