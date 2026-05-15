/**
 * Kevin Freel — Lead Magnet API
 * -----------------------------
 * Vercel serverless Node.js function (ES modules, Node 20+). Handles all 6
 * lead-magnet form submissions on kevinfreel.com. For each submission it:
 *
 *   1. Forwards the lead to https://myaieditor.com/api/form-notify so Kevin
 *      gets the standard email + Google Sheet logging (form-notify is the sole
 *      reCAPTCHA / honeypot / rate-limit verifier — do NOT double-verify here).
 *   2. Reads form-notify's `accepted` flag. If false, returns the same response
 *      to the client and skips the marketing email (the submission is spam).
 *   3. Sends a branded marketing email to the visitor via Resend directly,
 *      with the appropriate PDF attached (for buyers-guide / mortgage-roadmap)
 *      or a "View Report" button (for neighborhood-report / prep-checklist /
 *      investors-guide). The home-valuation magnet is redirect-only — no email.
 *   4. Returns { success, accepted, next } where `next` tells the caller what
 *      to redirect to (a page URL or a PDF path) or null for spam.
 *
 * Required env vars (set in Vercel project settings):
 *
 *   RESEND_API_KEY        Resend API key (re_...) — required to send emails.
 *                         If missing, the function still forwards to
 *                         form-notify but skips the visitor marketing email.
 *   NEXT_PUBLIC_SITE_URL  (optional) Origin used to fetch PDFs over HTTP for
 *                         attachment. Defaults to https://kevinfreel.com once
 *                         DNS is live; until then set this to the active
 *                         Vercel preview URL (e.g. https://kevinfreel.vercel.app).
 *
 * Request (POST /api/lead-magnet):
 *   {
 *     "site_slug":       "kevin-freel",
 *     "form_type":       "resource-<slug>",   // slug is one of MAGNET_CONFIG keys
 *     "first_name":      "John",
 *     "email":           "john@example.com",
 *     "_honey":          "",                  // honeypot — passes through to form-notify
 *     "recaptcha_token": "..."                // reCAPTCHA v3 token — verified by form-notify
 *   }
 *
 * Response:
 *   {
 *     "success":  true,
 *     "accepted": true | false,
 *     "next":     "/page-or-pdf-url" | null   // where the client should redirect
 *   }
 *
 * Local testing:
 *   vercel dev
 *   curl -X POST http://localhost:3000/api/lead-magnet \
 *     -H "Content-Type: application/json" \
 *     -d '{"site_slug":"kevin-freel","form_type":"resource-buyers-guide","first_name":"Justin","email":"you@example.com","_honey":"","recaptcha_token":"test"}'
 */

const FORM_NOTIFY_URL = 'https://myaieditor.com/api/form-notify';
const RESEND_API_URL = 'https://api.resend.com/emails';
const SITE_ORIGIN = (process.env.NEXT_PUBLIC_SITE_URL || 'https://kevinfreel.com').replace(/\/$/, '');
const FROM_ADDRESS = 'Kevin Freel <hello@sitenotifications.org>';
const REPLY_TO = 'KevinFreel@c21be.com';

// Magnet configuration. `next` is what the caller should redirect to (page URL
// or PDF path). `email` is the template key consumed below — `null` means no
// marketing email is sent (used by home-valuation).
const MAGNET_CONFIG = {
  'home-valuation': {
    next: (qs) => `/home-evaluation-questionnaire?${qs}`,
    email: null,
  },
  'buyers-guide': {
    next: () => '/pdfs/What-To-Expect.pdf',
    email: 'buyers',
  },
  'neighborhood-report': {
    next: () => '/tampa-bay-neighborhoods',
    email: 'neighborhoods',
  },
  'prep-checklist': {
    next: () => '/home-prep-checklist',
    email: 'checklist',
  },
  'mortgage-roadmap': {
    next: () => '/pdfs/Mortgage-Financing-Roadmap.pdf',
    email: 'mortgage',
  },
  'investors-guide': {
    next: () => '/investor-guide',
    email: 'investors',
  },
};

// Cache PDF base64 across warm function invocations. Vercel keeps functions
// warm for a few minutes, so we only pay the fetch cost on cold starts.
const pdfCache = new Map();

async function fetchPdfBase64(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to fetch PDF at ${url}: HTTP ${res.status}`);
  const buf = Buffer.from(await res.arrayBuffer());
  return buf.toString('base64');
}

async function getPdfBase64(pathFromOrigin) {
  const url = `${SITE_ORIGIN}${pathFromOrigin}`;
  if (pdfCache.has(url)) return pdfCache.get(url);
  const b64 = await fetchPdfBase64(url);
  pdfCache.set(url, b64);
  return b64;
}

// --- Email templates -------------------------------------------------------

const STATS_BLOCK = `
  <table role="presentation" class="stats" cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#f7f7f8;border-radius:8px;margin:24px 0;">
    <tr>
      <td align="center" style="padding:18px 8px;">
        <div style="font-family:Georgia,serif;font-size:20px;font-weight:700;color:#c41e2a;">40+</div>
        <div style="font-size:10px;letter-spacing:0.08em;color:#6b7280;text-transform:uppercase;margin-top:2px;">Years Experience</div>
      </td>
      <td align="center" style="padding:18px 8px;">
        <div style="font-family:Georgia,serif;font-size:20px;font-weight:700;color:#c41e2a;">1,200+</div>
        <div style="font-size:10px;letter-spacing:0.08em;color:#6b7280;text-transform:uppercase;margin-top:2px;">Properties Sold</div>
      </td>
      <td align="center" style="padding:18px 8px;">
        <div style="font-family:Georgia,serif;font-size:20px;font-weight:700;color:#c41e2a;">#1</div>
        <div style="font-size:10px;letter-spacing:0.08em;color:#6b7280;text-transform:uppercase;margin-top:2px;">At C21 Beggins</div>
      </td>
      <td align="center" style="padding:18px 8px;">
        <div style="font-family:Georgia,serif;font-size:20px;font-weight:700;color:#c41e2a;">14th</div>
        <div style="font-size:10px;letter-spacing:0.08em;color:#6b7280;text-transform:uppercase;margin-top:2px;">In Florida State</div>
      </td>
    </tr>
  </table>
`;

const ABOUT_KEVIN = `
  <p>I've been selling Tampa Bay real estate since 1985 — through every boom, every dip, and every shift in this market. My job is to make sure you don't have to learn it the hard way.</p>
`;

function shell({ preheader, content }) {
  return `<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kevin Freel Real Estate</title>
</head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f5f5f5;margin:0;padding:0;color:#1a1a1a;line-height:1.55;">
  <span style="display:none!important;visibility:hidden;mso-hide:all;font-size:1px;color:#f5f5f5;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;">${preheader}</span>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f5f5f5;">
    <tr><td align="center" style="padding:24px 12px;">
      <table role="presentation" width="560" cellpadding="0" cellspacing="0" border="0" style="max-width:560px;background:#ffffff;border-radius:4px;overflow:hidden;">
        <tr><td style="height:4px;background:#c41e2a;line-height:4px;font-size:0;">&nbsp;</td></tr>
        <tr><td align="center" style="padding:28px 32px 16px;">
          <div style="font-family:Georgia,serif;font-size:22px;font-weight:600;color:#111;letter-spacing:0.04em;">KEVIN <span style="color:#c41e2a;">FREEL</span></div>
          <div style="font-size:10px;font-weight:700;letter-spacing:0.18em;color:#6b7280;margin-top:6px;text-transform:uppercase;">Realtor Since 1985</div>
        </td></tr>
        <tr><td style="padding:0 32px;"><div style="height:1px;background:#e5e7eb;line-height:1px;font-size:0;">&nbsp;</div></td></tr>
        <tr><td style="padding:32px;font-size:15px;color:#1a1a1a;line-height:1.6;">
          ${content}
        </td></tr>
        <tr><td style="padding:28px 32px;background:#111;color:#ffffff;text-align:center;font-size:13px;line-height:1.6;">
          <div style="font-weight:600;font-size:14px;color:#ffffff;">Kevin Freel Real Estate</div>
          <div style="margin-top:6px;color:rgba(255,255,255,0.85);">727-410-8599 &middot; <a href="mailto:KevinFreel@c21be.com" style="color:#c41e2a;text-decoration:none;">KevinFreel@c21be.com</a> &middot; <a href="https://kevinfreel.com" style="color:#c41e2a;text-decoration:none;">kevinfreel.com</a></div>
          <div style="margin-top:4px;color:rgba(255,255,255,0.7);">1501 South Dale Mabry A1 &middot; Tampa, FL 33629</div>
          <div style="margin-top:14px;color:rgba(255,255,255,0.7);font-size:12px;">
            <a href="https://www.facebook.com/kevin.freel" style="color:rgba(255,255,255,0.85);text-decoration:none;">Facebook</a>
            &nbsp;&middot;&nbsp;
            <a href="https://www.instagram.com/kevinfreel/" style="color:rgba(255,255,255,0.85);text-decoration:none;">Instagram</a>
            &nbsp;&middot;&nbsp;
            <a href="https://www.linkedin.com/in/kevinfreel/" style="color:rgba(255,255,255,0.85);text-decoration:none;">LinkedIn</a>
          </div>
          <div style="color:rgba(255,255,255,0.55);font-size:11px;margin-top:16px;">&copy; 2026 Kevin Freel Real Estate. Sent because you requested a resource from kevinfreel.com.</div>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>`;
}

function button(label, href) {
  return `
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:8px 0 18px;">
    <tr><td style="background:#c41e2a;border-radius:6px;">
      <a href="${href}" style="display:inline-block;color:#ffffff;padding:14px 28px;text-decoration:none;font-weight:600;font-size:15px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">${label}</a>
    </td></tr>
  </table>`;
}

function buildBuyersGuideEmail(firstName) {
  const content = `
    <h1 style="font-family:Georgia,serif;font-size:22px;margin:0 0 16px;color:#111;">Your Tampa Bay home buyer's guide is here</h1>
    <p style="margin:0 0 14px;">Hi ${firstName}, thanks for downloading the <strong>Complete Tampa Bay Home Buyer's Guide</strong>. It covers everything from pre-approval to closing day — and there's plenty in here even seasoned buyers don't know about Florida-specific issues like flood zones, wind mitigation, and HOAs.</p>
    <p style="margin:0 0 14px;">It's attached as a PDF. You can also just hit reply if you have any questions — I read every email personally.</p>
    ${ABOUT_KEVIN}
    ${STATS_BLOCK}
    <p style="margin:0 0 8px;">When you're ready to start looking, just call: <strong><a href="tel:+17274108599" style="color:#c41e2a;text-decoration:none;">727-410-8599</a></strong>.</p>
    <p style="margin:18px 0 0;">— Kevin Freel</p>
  `;
  return {
    subject: `${firstName}, your Tampa Bay home buyer's guide is here`,
    preheader: 'Your Complete Tampa Bay Home Buyer\'s Guide is attached as a PDF.',
    html: shell({ preheader: 'Your Tampa Bay Home Buyer\'s Guide is attached.', content }),
    pdfPath: '/pdfs/What-To-Expect.pdf',
    pdfFilename: 'Tampa-Bay-Home-Buyers-Guide.pdf',
  };
}

function buildMortgageRoadmapEmail(firstName) {
  const content = `
    <h1 style="font-family:Georgia,serif;font-size:22px;margin:0 0 16px;color:#111;">Your Mortgage &amp; Financing Roadmap</h1>
    <p style="margin:0 0 14px;">Hi ${firstName}, here's everything you asked for about financing your home. The PDF covers documents to gather, credit prep, the timeline from pre-approval to closing, and the red flags to watch for.</p>
    <p style="margin:0 0 14px;">Skim it now, then keep it as a reference. Most buyers refer back to it 3-4 times during the process.</p>
    ${ABOUT_KEVIN}
    ${STATS_BLOCK}
    <p style="margin:0 0 8px;">Questions on financing? Reply to this email or call <strong><a href="tel:+17274108599" style="color:#c41e2a;text-decoration:none;">727-410-8599</a></strong> — happy to walk you through it.</p>
    <p style="margin:18px 0 0;">— Kevin Freel</p>
  `;
  return {
    subject: `${firstName}, your Mortgage & Financing Roadmap (PDF)`,
    preheader: 'Your Mortgage & Financing Roadmap is attached as a PDF.',
    html: shell({ preheader: 'Your Mortgage & Financing Roadmap is attached as a PDF.', content }),
    pdfPath: '/pdfs/Mortgage-Financing-Roadmap.pdf',
    pdfFilename: 'Mortgage-Financing-Roadmap.pdf',
  };
}

function buildNeighborhoodReportEmail(firstName) {
  const url = `${SITE_ORIGIN}/tampa-bay-neighborhoods`;
  const content = `
    <h1 style="font-family:Georgia,serif;font-size:22px;margin:0 0 16px;color:#111;">Your Tampa Bay Neighborhood Report</h1>
    <p style="margin:0 0 14px;">Hi ${firstName}, here's the deep-dive on 12 Tampa Bay neighborhoods — median prices, schools, commute times, and my honest take on what each area actually feels like to live in. I update this quarterly, so it's current.</p>
    ${button('View the Report →', url)}
    ${ABOUT_KEVIN}
    ${STATS_BLOCK}
    <p style="margin:0 0 8px;">Have a specific neighborhood in mind? Reply or call <strong><a href="tel:+17274108599" style="color:#c41e2a;text-decoration:none;">727-410-8599</a></strong> — I've sold homes in every one of these areas.</p>
    <p style="margin:18px 0 0;">— Kevin Freel</p>
  `;
  return {
    subject: `${firstName}, your Tampa Bay Neighborhood Report`,
    preheader: '12 Tampa Bay neighborhoods, ranked and reviewed — updated quarterly.',
    html: shell({ preheader: '12 Tampa Bay neighborhoods, ranked and reviewed.', content }),
    pdfPath: null,
    pdfFilename: null,
  };
}

function buildPrepChecklistEmail(firstName) {
  const url = `${SITE_ORIGIN}/home-prep-checklist`;
  const content = `
    <h1 style="font-family:Georgia,serif;font-size:22px;margin:0 0 16px;color:#111;">Your 74-Point Home Prep Checklist</h1>
    <p style="margin:0 0 14px;">Hi ${firstName}, here's the exact checklist I walk my sellers through before listing. <strong>74 actionable items</strong> grouped into 15 bite-sized sections. Small fixes can mean tens of thousands of dollars at closing — every item has been ROI-tested through 40 years of selling Tampa Bay homes.</p>
    ${button('Open the Checklist →', url)}
    <p style="margin:0 0 14px;">Pin it. Print it. Hand it to your spouse.</p>
    ${ABOUT_KEVIN}
    ${STATS_BLOCK}
    <p style="margin:0 0 8px;">When you're ready for a no-pressure walkthrough of your home, call <strong><a href="tel:+17274108599" style="color:#c41e2a;text-decoration:none;">727-410-8599</a></strong>.</p>
    <p style="margin:18px 0 0;">— Kevin Freel</p>
  `;
  return {
    subject: `${firstName}, your 74-Point Home Prep Checklist`,
    preheader: '74 ROI-tested items to get top dollar before you list.',
    html: shell({ preheader: '74 ROI-tested items to get top dollar before you list.', content }),
    pdfPath: null,
    pdfFilename: null,
  };
}

function buildInvestorsGuideEmail(firstName) {
  const url = `${SITE_ORIGIN}/investor-guide`;
  const content = `
    <h1 style="font-family:Georgia,serif;font-size:22px;margin:0 0 16px;color:#111;">Your Tampa Bay Investor's Guide</h1>
    <p style="margin:0 0 14px;">Hi ${firstName}, here's the <strong>Tampa Bay Investor's Guide</strong> — best ZIP codes for cap rate, single-family vs. multi-family breakdown, STR rules by city, and the 5 mistakes I see first-time investors make over and over. Plus my recommended buy-box for first-timers.</p>
    ${button('Read the Guide →', url)}
    ${ABOUT_KEVIN}
    ${STATS_BLOCK}
    <p style="margin:0 0 8px;">If you're eyeing a specific property, reply with the address — I'll run the numbers with you for free.</p>
    <p style="margin:18px 0 0;">— Kevin Freel</p>
  `;
  return {
    subject: `${firstName}, your Tampa Bay Investor's Guide`,
    preheader: 'Best ZIP codes, STR rules, and the 5 first-timer mistakes to avoid.',
    html: shell({ preheader: 'Best ZIP codes, STR rules, and the 5 first-timer mistakes to avoid.', content }),
    pdfPath: null,
    pdfFilename: null,
  };
}

const TEMPLATE_BUILDERS = {
  buyers: buildBuyersGuideEmail,
  mortgage: buildMortgageRoadmapEmail,
  neighborhoods: buildNeighborhoodReportEmail,
  checklist: buildPrepChecklistEmail,
  investors: buildInvestorsGuideEmail,
};

// --- Helpers ---------------------------------------------------------------

function escapeHtml(s = '') {
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[c]);
}

function parseSlug(formType) {
  if (typeof formType !== 'string') return null;
  const m = formType.match(/^resource-(.+)$/);
  return m ? m[1] : null;
}

async function readBody(req) {
  // Vercel auto-parses JSON bodies into req.body for content-type
  // application/json, but be defensive in case a raw stream arrives.
  if (req.body && typeof req.body === 'object') return req.body;
  if (typeof req.body === 'string') {
    try { return JSON.parse(req.body); } catch { return {}; }
  }
  // Stream fallback
  return await new Promise((resolve) => {
    let raw = '';
    req.on('data', (chunk) => { raw += chunk; });
    req.on('end', () => {
      try { resolve(JSON.parse(raw || '{}')); }
      catch { resolve({}); }
    });
    req.on('error', () => resolve({}));
  });
}

async function forwardToFormNotify(payload, slug) {
  const body = {
    ...payload,
    lead_magnet: slug,
    // Make the form_type human-readable in the notification email.
    form_type: payload.form_type || `resource-${slug}`,
  };
  try {
    const res = await fetch(FORM_NOTIFY_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      return { networkOk: false, accepted: true, reason: `form_notify_http_${res.status}` };
    }
    const json = await res.json().catch(() => ({}));
    // Default to accepted=true if the flag is missing (rolling deploy safety).
    const accepted = json.accepted !== false;
    return {
      networkOk: true,
      accepted,
      reason: typeof json.reason === 'string' ? json.reason : null,
    };
  } catch (err) {
    console.error('[lead-magnet] form-notify forward failed:', err);
    return { networkOk: false, accepted: true, reason: 'form_notify_unreachable' };
  }
}

async function sendMarketingEmail({ email, template }) {
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) {
    console.warn('[lead-magnet] RESEND_API_KEY not set — skipping marketing email.');
    return { sent: false, reason: 'no_api_key' };
  }

  const attachments = [];
  if (template.pdfPath) {
    try {
      const pdfBase64 = await getPdfBase64(template.pdfPath);
      attachments.push({
        filename: template.pdfFilename || 'attachment.pdf',
        content: pdfBase64,
      });
    } catch (err) {
      console.error(`[lead-magnet] PDF fetch failed for ${template.pdfPath}:`, err);
      // Continue without attachment — the email still has the message body
      // and Kevin still gets the form-notify lead.
    }
  }

  // BCC justin@webeducationservices.com on every marketing email so the
  // WES team has visibility into what Kevin's leads are receiving.
  // (form-notify already CCs both Kevin and Justin on every lead capture
  // via site_access; this BCC covers the visitor-facing email side.)
  const payload = {
    from: FROM_ADDRESS,
    to: [email],
    bcc: ['justin@webeducationservices.com'],
    reply_to: REPLY_TO,
    subject: template.subject,
    html: template.html,
  };
  if (attachments.length) payload.attachments = attachments;

  try {
    const res = await fetch(RESEND_API_URL, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const errText = await res.text().catch(() => '');
      console.error(`[lead-magnet] Resend send failed: HTTP ${res.status}`, errText);
      // Fallback: try forms@sitenotifications.org from-address if hello@ rejected
      if (res.status === 403 || res.status === 422) {
        const fallback = { ...payload, from: 'Kevin Freel <forms@sitenotifications.org>' };
        const retry = await fetch(RESEND_API_URL, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${apiKey}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(fallback),
        });
        if (retry.ok) return { sent: true, reason: 'fallback_from' };
        const retryText = await retry.text().catch(() => '');
        console.error(`[lead-magnet] Resend fallback also failed: HTTP ${retry.status}`, retryText);
        return { sent: false, reason: `resend_${retry.status}` };
      }
      return { sent: false, reason: `resend_${res.status}` };
    }
    return { sent: true };
  } catch (err) {
    console.error('[lead-magnet] Resend network error:', err);
    return { sent: false, reason: 'network_error' };
  }
}

// --- Handler ---------------------------------------------------------------

export default async function handler(req, res) {
  // CORS — allow same-site fetch from kevinfreel.com pages.
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.status(204).end();
    return;
  }
  if (req.method !== 'POST') {
    res.status(405).json({ success: false, error: 'POST only' });
    return;
  }

  const body = await readBody(req);
  const { site_slug, form_type, first_name, email } = body || {};

  // Validate
  if (!site_slug || !form_type || !email || typeof email !== 'string' || !email.includes('@')) {
    res.status(400).json({ success: false, error: 'Missing required fields: site_slug, form_type, email' });
    return;
  }

  const slug = parseSlug(form_type);
  if (!slug || !MAGNET_CONFIG[slug]) {
    res.status(400).json({ success: false, error: `Unknown form_type: ${form_type}` });
    return;
  }

  const config = MAGNET_CONFIG[slug];
  const safeFirstName = escapeHtml((first_name || '').trim()) || 'there';

  // 1. Forward to form-notify (the authoritative gate).
  const { networkOk, accepted, reason } = await forwardToFormNotify(body, slug);

  // 2. Spam path — return without sending the marketing email.
  if (networkOk && !accepted) {
    res.status(200).json({ success: true, accepted: false, next: null, reason });
    return;
  }

  // 3. Compute the `next` redirect.
  const qs = new URLSearchParams({
    first_name: (first_name || '').trim(),
    email,
  }).toString();
  const next = config.next(qs);

  // 4. Send the marketing email (if this magnet has one).
  // Fire-and-forget? No — we want to return after send so the client knows.
  // But cap at ~10s so we don't blow the Vercel timeout. The Pro plan gives
  // us 60s; this is well within that.
  if (config.email && TEMPLATE_BUILDERS[config.email]) {
    const template = TEMPLATE_BUILDERS[config.email](safeFirstName);
    // Don't block the response on email failure — we've already done the
    // lead capture. Log it and move on.
    try {
      await sendMarketingEmail({ email, template });
    } catch (err) {
      console.error('[lead-magnet] Marketing email send threw:', err);
    }
  }

  res.status(200).json({ success: true, accepted: true, next });
}
