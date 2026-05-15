#!/usr/bin/env python3
"""
Generate Kevin Freel's "Mortgage & Financing Roadmap" lead-magnet PDF.

Output: /Users/justinbabcock/Desktop/Websites/kevinfreel/pdfs/Mortgage-Financing-Roadmap.pdf

Brand:
  - Red       #c41e2a
  - Near-black#111111
  - Cream     #f5f5f5
  - White

Run:
  python3 scripts/generate_mortgage_pdf.py
"""

import os
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    PageBreak,
    Flowable,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY


# ---------------------------------------------------------------------------
# Brand
# ---------------------------------------------------------------------------

RED = HexColor("#c41e2a")
RED_DARK = HexColor("#a01821")
NAVY = HexColor("#111111")
CREAM = HexColor("#f5f5f5")
GRAY = HexColor("#6b7280")
GRAY_LIGHT = HexColor("#9ca3af")
GRAY_BORDER = HexColor("#e5e7eb")
BODY = HexColor("#1f2937")

OUT_PATH = "/Users/justinbabcock/Desktop/Websites/kevinfreel/pdfs/Mortgage-Financing-Roadmap.pdf"


# ---------------------------------------------------------------------------
# Custom flowables
# ---------------------------------------------------------------------------

class RedBar(Flowable):
    """A horizontal red accent bar used before section headings."""

    def __init__(self, width=0.6 * inch, height=0.09 * inch, color=RED):
        super().__init__()
        self.width = width
        self.height = height
        self.color = color

    def wrap(self, avail_w, avail_h):
        return self.width, self.height

    def draw(self):
        self.canv.setFillColor(self.color)
        self.canv.rect(0, 0, self.width, self.height, fill=1, stroke=0)


class HorizontalRule(Flowable):
    """A thin horizontal divider line."""

    def __init__(self, width, color=GRAY_BORDER, thickness=0.5):
        super().__init__()
        self.width = width
        self.color = color
        self.thickness = thickness

    def wrap(self, avail_w, avail_h):
        return self.width, self.thickness

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 0, self.width, 0)


class CoverGeometric(Flowable):
    """Cover page geometric accent: large red rectangle with offset cream block."""

    def __init__(self, width, height):
        super().__init__()
        self.width = width
        self.height = height

    def wrap(self, avail_w, avail_h):
        return self.width, self.height

    def draw(self):
        c = self.canv
        # Background cream block
        c.setFillColor(CREAM)
        c.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        # Large red rectangle
        c.setFillColor(RED)
        c.rect(0, self.height * 0.25, self.width * 0.65, self.height * 0.6, fill=1, stroke=0)
        # Smaller dark rectangle (overlap)
        c.setFillColor(NAVY)
        c.rect(self.width * 0.55, self.height * 0.1, self.width * 0.35, self.height * 0.45, fill=1, stroke=0)
        # Thin red accent line bottom
        c.setFillColor(RED)
        c.rect(0, 0, self.width, self.height * 0.035, fill=1, stroke=0)
        # Small label inside red block
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(0.3 * inch, self.height * 0.7, "TAMPA BAY")
        c.setFont("Helvetica", 8)
        c.drawString(0.3 * inch, self.height * 0.65, "REAL ESTATE")


class CircleInitials(Flowable):
    """A simple circle with initials for a photo placeholder."""

    def __init__(self, size=1.4 * inch, initials="KF"):
        super().__init__()
        self.size = size
        self.initials = initials

    def wrap(self, avail_w, avail_h):
        return self.size, self.size

    def draw(self):
        c = self.canv
        r = self.size / 2.0
        # Outer red ring
        c.setFillColor(RED)
        c.circle(r, r, r, fill=1, stroke=0)
        # Inner cream circle
        c.setFillColor(CREAM)
        c.circle(r, r, r - 0.08 * inch, fill=1, stroke=0)
        # Initials
        c.setFillColor(NAVY)
        c.setFont("Times-Bold", 36)
        text_w = c.stringWidth(self.initials, "Times-Bold", 36)
        c.drawString(r - text_w / 2.0, r - 12, self.initials)


# ---------------------------------------------------------------------------
# Page decoration (header / footer)
# ---------------------------------------------------------------------------

def header_footer(canvas, doc):
    canvas.saveState()

    page_w, page_h = LETTER

    # ---- Header ----
    # Red accent bar (small block)
    canvas.setFillColor(RED)
    canvas.rect(0.75 * inch, page_h - 0.55 * inch, 0.35 * inch, 0.13 * inch, fill=1, stroke=0)

    # Header text
    canvas.setFillColor(NAVY)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(1.2 * inch, page_h - 0.5 * inch, "KEVIN FREEL")

    canvas.setFillColor(GRAY)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(2.05 * inch, page_h - 0.5 * inch, "·  Realtor Since 1985")

    # Right-side header: "Mortgage & Financing Roadmap"
    canvas.setFillColor(GRAY)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(page_w - 0.75 * inch, page_h - 0.5 * inch, "Mortgage & Financing Roadmap")

    # Thin divider under header
    canvas.setStrokeColor(GRAY_BORDER)
    canvas.setLineWidth(0.4)
    canvas.line(0.75 * inch, page_h - 0.65 * inch, page_w - 0.75 * inch, page_h - 0.65 * inch)

    # ---- Footer ----
    canvas.setStrokeColor(GRAY_BORDER)
    canvas.setLineWidth(0.4)
    canvas.line(0.75 * inch, 0.7 * inch, page_w - 0.75 * inch, 0.7 * inch)

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRAY_LIGHT)
    canvas.drawString(
        0.75 * inch, 0.5 * inch,
        "Kevin Freel Real Estate  ·  727-410-8599  ·  kevinfreel.com",
    )
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(GRAY)
    canvas.drawRightString(page_w - 0.75 * inch, 0.5 * inch, f"Page {doc.page}")

    canvas.restoreState()


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def make_styles():
    base = getSampleStyleSheet()
    styles = {}

    styles["cover_eyebrow"] = ParagraphStyle(
        "cover_eyebrow",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=RED,
        spaceAfter=14,
        leading=12,
        alignment=TA_LEFT,
    )

    styles["cover_title"] = ParagraphStyle(
        "cover_title",
        parent=base["Title"],
        fontName="Times-Bold",
        fontSize=44,
        textColor=NAVY,
        leading=48,
        spaceAfter=10,
        alignment=TA_LEFT,
    )

    styles["cover_subtitle"] = ParagraphStyle(
        "cover_subtitle",
        parent=base["Normal"],
        fontName="Times-Italic",
        fontSize=16,
        textColor=GRAY,
        leading=22,
        spaceAfter=30,
        alignment=TA_LEFT,
    )

    styles["cover_byline"] = ParagraphStyle(
        "cover_byline",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=NAVY,
        leading=15,
        alignment=TA_LEFT,
    )

    styles["cover_date"] = ParagraphStyle(
        "cover_date",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=GRAY,
        leading=12,
        alignment=TA_LEFT,
    )

    styles["section_eyebrow"] = ParagraphStyle(
        "section_eyebrow",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=RED,
        leading=11,
        spaceAfter=4,
        alignment=TA_LEFT,
    )

    styles["h1"] = ParagraphStyle(
        "h1",
        parent=base["Heading1"],
        fontName="Times-Bold",
        fontSize=28,
        textColor=NAVY,
        leading=32,
        spaceBefore=2,
        spaceAfter=10,
        alignment=TA_LEFT,
    )

    styles["h2"] = ParagraphStyle(
        "h2",
        parent=base["Heading2"],
        fontName="Times-Bold",
        fontSize=16,
        textColor=NAVY,
        leading=20,
        spaceBefore=10,
        spaceAfter=4,
        alignment=TA_LEFT,
    )

    styles["h3"] = ParagraphStyle(
        "h3",
        parent=base["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=NAVY,
        leading=14,
        spaceBefore=10,
        spaceAfter=3,
        alignment=TA_LEFT,
    )

    styles["lead"] = ParagraphStyle(
        "lead",
        parent=base["Normal"],
        fontName="Times-Italic",
        fontSize=13,
        textColor=GRAY,
        leading=18,
        spaceAfter=14,
        alignment=TA_LEFT,
    )

    styles["body"] = ParagraphStyle(
        "body",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=10,
        textColor=BODY,
        leading=15,
        spaceAfter=8,
        alignment=TA_LEFT,
    )

    styles["body_justify"] = ParagraphStyle(
        "body_justify",
        parent=styles["body"],
        alignment=TA_JUSTIFY,
    )

    styles["bullet"] = ParagraphStyle(
        "bullet",
        parent=styles["body"],
        fontSize=10,
        leading=14,
        leftIndent=18,
        bulletIndent=4,
        spaceAfter=3,
    )

    styles["sub_bullet"] = ParagraphStyle(
        "sub_bullet",
        parent=styles["body"],
        fontSize=9.5,
        leading=14,
        leftIndent=34,
        bulletIndent=20,
        textColor=GRAY,
        spaceAfter=3,
    )

    styles["tip_title"] = ParagraphStyle(
        "tip_title",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=RED,
        leading=12,
        spaceAfter=4,
        alignment=TA_LEFT,
    )

    styles["tip_body"] = ParagraphStyle(
        "tip_body",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=10,
        textColor=NAVY,
        leading=14,
        alignment=TA_LEFT,
    )

    styles["welcome_body"] = ParagraphStyle(
        "welcome_body",
        parent=styles["body"],
        fontSize=11,
        leading=17,
        spaceAfter=12,
    )

    styles["stat_number"] = ParagraphStyle(
        "stat_number",
        parent=base["Normal"],
        fontName="Times-Bold",
        fontSize=22,
        textColor=RED,
        leading=24,
        alignment=TA_CENTER,
    )

    styles["stat_label"] = ParagraphStyle(
        "stat_label",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=8,
        textColor=NAVY,
        leading=11,
        alignment=TA_CENTER,
    )

    styles["toc_num"] = ParagraphStyle(
        "toc_num",
        parent=base["Normal"],
        fontName="Times-Bold",
        fontSize=14,
        textColor=RED,
        leading=18,
        alignment=TA_LEFT,
    )

    styles["toc_title"] = ParagraphStyle(
        "toc_title",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=NAVY,
        leading=14,
        alignment=TA_LEFT,
    )

    styles["toc_sub"] = ParagraphStyle(
        "toc_sub",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=GRAY,
        leading=12,
        alignment=TA_LEFT,
    )

    styles["toc_page"] = ParagraphStyle(
        "toc_page",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=10,
        textColor=GRAY,
        leading=14,
        alignment=TA_RIGHT,
    )

    styles["timeline_when"] = ParagraphStyle(
        "timeline_when",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=white,
        leading=11,
        alignment=TA_CENTER,
    )

    styles["timeline_title"] = ParagraphStyle(
        "timeline_title",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=NAVY,
        leading=13,
        spaceAfter=3,
        alignment=TA_LEFT,
    )

    styles["timeline_body"] = ParagraphStyle(
        "timeline_body",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=BODY,
        leading=13,
        alignment=TA_LEFT,
    )

    styles["cta_h"] = ParagraphStyle(
        "cta_h",
        parent=base["Normal"],
        fontName="Times-Bold",
        fontSize=36,
        textColor=NAVY,
        leading=42,
        alignment=TA_CENTER,
        spaceAfter=8,
    )

    styles["cta_sub"] = ParagraphStyle(
        "cta_sub",
        parent=base["Normal"],
        fontName="Times-Italic",
        fontSize=14,
        textColor=GRAY,
        leading=20,
        alignment=TA_CENTER,
        spaceAfter=24,
    )

    styles["cta_phone"] = ParagraphStyle(
        "cta_phone",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=28,
        textColor=RED,
        leading=32,
        alignment=TA_CENTER,
    )

    styles["cta_meta"] = ParagraphStyle(
        "cta_meta",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=11,
        textColor=NAVY,
        leading=18,
        alignment=TA_CENTER,
    )

    styles["cta_tag"] = ParagraphStyle(
        "cta_tag",
        parent=base["Normal"],
        fontName="Times-Italic",
        fontSize=13,
        textColor=GRAY,
        leading=18,
        alignment=TA_CENTER,
    )

    styles["q"] = ParagraphStyle(
        "q",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        textColor=NAVY,
        leading=14,
        spaceBefore=10,
        spaceAfter=4,
        alignment=TA_LEFT,
    )

    styles["a"] = ParagraphStyle(
        "a",
        parent=styles["body"],
        spaceAfter=10,
    )

    styles["glossary_term"] = ParagraphStyle(
        "glossary_term",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        textColor=RED,
        leading=12,
        alignment=TA_LEFT,
    )

    styles["glossary_def"] = ParagraphStyle(
        "glossary_def",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=BODY,
        leading=12,
        alignment=TA_LEFT,
    )

    styles["sidebar_h"] = ParagraphStyle(
        "sidebar_h",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=white,
        leading=12,
        alignment=TA_LEFT,
    )

    styles["sidebar_item"] = ParagraphStyle(
        "sidebar_item",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=NAVY,
        leading=13,
        leftIndent=10,
        bulletIndent=0,
        alignment=TA_LEFT,
    )

    return styles


# ---------------------------------------------------------------------------
# Helpers for repeated patterns
# ---------------------------------------------------------------------------

def section_heading(eyebrow_text, title_text, styles):
    """Eyebrow + red accent bar + large heading."""
    return [
        Paragraph(eyebrow_text, styles["section_eyebrow"]),
        RedBar(width=0.7 * inch, height=0.09 * inch),
        Spacer(1, 8),
        Paragraph(title_text, styles["h1"]),
    ]


def tip_box(title, body, styles, width=7.0 * inch):
    """Red-bordered tip callout box."""
    inner_para = [
        Paragraph(title, styles["tip_title"]),
        Paragraph(body, styles["tip_body"]),
    ]
    t = Table(
        [[inner_para]],
        colWidths=[width],
    )
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#fdf3f4")),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LINEBEFORE", (0, 0), (0, -1), 3, RED),
        ("BOX", (0, 0), (-1, -1), 0.4, HexColor("#f3d4d6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return KeepTogether([Spacer(1, 4), t, Spacer(1, 4)])


def bullet(text, styles, level=0):
    style = styles["bullet"] if level == 0 else styles["sub_bullet"]
    bullet_char = "•" if level == 0 else "–"
    return Paragraph(f"{bullet_char}&nbsp;&nbsp;{text}", style)


def numbered_action(num, header, body, styles):
    """Numbered action item — number + bold header + body."""
    num_para = Paragraph(f'<font color="#c41e2a"><b>{num}</b></font>', ParagraphStyle(
        "num",
        fontName="Times-Bold",
        fontSize=22,
        leading=24,
        textColor=RED,
        alignment=TA_CENTER,
    ))
    text_para = [
        Paragraph(header, styles["h3"]),
        Paragraph(body, styles["body"]),
    ]
    t = Table(
        [[num_para, text_para]],
        colWidths=[0.5 * inch, 6.5 * inch],
    )
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return KeepTogether(t)


# ---------------------------------------------------------------------------
# Page builders
# ---------------------------------------------------------------------------

def build_cover(styles):
    story = []

    # Big decorative top block
    story.append(Spacer(1, 0.1 * inch))
    story.append(CoverGeometric(width=7.0 * inch, height=3.0 * inch))
    story.append(Spacer(1, 0.45 * inch))

    story.append(Paragraph("LEAD-MAGNET GUIDE  ·  UPDATED MAY 2026", styles["cover_eyebrow"]))
    story.append(Paragraph("Mortgage &amp; Financing Roadmap", styles["cover_title"]))
    story.append(Paragraph(
        "From Pre-Approval to Closing — In Plain English.",
        styles["cover_subtitle"],
    ))

    # Thin red rule
    story.append(HorizontalRule(width=2.4 * inch, color=RED, thickness=1.2))
    story.append(Spacer(1, 16))

    story.append(Paragraph("By Kevin Freel", styles["cover_byline"]))
    story.append(Spacer(1, 3))
    story.append(Paragraph(
        "Century 21 Beggins  ·  40+ Years Tampa Bay Experience",
        styles["cover_date"],
    ))

    story.append(PageBreak())
    return story


def build_welcome(styles):
    story = []

    story.extend(section_heading(
        "CHAPTER 00  ·  WELCOME",
        "A Note From Kevin",
        styles,
    ))

    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Buying a home — especially your first one — can feel like learning a "
        "new language. Pre-quals, points, PMI, LTV, escrow, underwriting. "
        "It is a lot. After more than four decades helping families across "
        "Tampa Bay, I have learned that 90% of buyer stress comes from not "
        "understanding the financing piece.",
        styles["welcome_body"],
    ))

    story.append(Paragraph(
        "This roadmap walks you through every step — what to gather, what to "
        "avoid, what to expect, and what the jargon actually means. I have "
        "boiled it down to what genuinely matters and stripped out everything "
        "that does not. There are no upsells, no gotchas, and no lender "
        "kickbacks hidden in these pages.",
        styles["welcome_body"],
    ))

    story.append(Paragraph(
        "When you are ready — whether that is next week or next year — I am a "
        "phone call away. No pressure, no pitch. Just the honest answers I "
        "would give my own family.",
        styles["welcome_body"],
    ))

    story.append(Paragraph(
        '<font name="Times-Italic" color="#c41e2a">'
        "Here is everything you need to know about financing your Tampa Bay "
        "home — without the jargon."
        "</font>",
        ParagraphStyle(
            "kevin_pull",
            fontName="Times-Italic",
            fontSize=13,
            leading=18,
            textColor=RED,
            alignment=TA_LEFT,
            spaceBefore=4,
            spaceAfter=18,
        ),
    ))

    story.append(Paragraph(
        '<font name="Helvetica-Bold" color="#111111">— Kevin Freel</font>',
        styles["body"],
    ))

    story.append(Spacer(1, 24))

    # Stats row (4 stats)
    stats = [
        ("40+", "Years\nExperience"),
        ("1,200+", "Properties\nSold"),
        ("#1", "Agent at\nC21 Beggins"),
        ("14th", "In Florida\nStatewide"),
    ]
    cells = []
    for num, label in stats:
        cells.append([
            Paragraph(num, styles["stat_number"]),
            Spacer(1, 2),
            Paragraph(label.replace("\n", "<br/>"), styles["stat_label"]),
        ])

    stats_table = Table(
        [cells],
        colWidths=[1.65 * inch] * 4,
        rowHeights=[1.0 * inch],
    )
    stats_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (-1, -1), CREAM),
        ("LINEABOVE", (0, 0), (-1, 0), 1.2, RED),
        ("LINEBELOW", (0, -1), (-1, -1), 1.2, RED),
        ("LINEAFTER", (0, 0), (-2, -1), 0.4, GRAY_BORDER),
    ]))
    story.append(stats_table)

    story.append(PageBreak())
    return story


def build_toc(styles):
    story = []

    story.extend(section_heading(
        "CHAPTER 00  ·  CONTENTS",
        "What's Inside",
        styles,
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Eight short sections. Each is designed to be read in 3 to 5 minutes.",
        styles["lead"],
    ))
    story.append(Spacer(1, 4))

    # TOC entries: (num, title, subtitle, page)
    toc = [
        ("01", "Documents to Gather Before You Apply",
         "What every lender needs on day one.", "04"),
        ("02", "Strengthen Your Credit in 60 Days",
         "Six moves that can save you thousands.", "06"),
        ("03", "Pre-Approval to Closing Timeline",
         "What happens, and when.", "07"),
        ("04", "Common Mortgage Types Explained",
         "Conventional, FHA, VA, USDA — and the rest.", "09"),
        ("05", "Red Flags to Avoid",
         "Six warning signs of a bad loan or lender.", "10"),
        ("06", "Kevin's Preferred Lender Network",
         "How introductions work — and why.", "11"),
        ("07", "Frequently Asked Questions",
         "The six I hear most often.", "12"),
        ("08", "Glossary",
         "Plain-English mortgage terms.", "13"),
    ]

    rows = []
    for num, title, sub, page in toc:
        rows.append([
            Paragraph(num, styles["toc_num"]),
            [
                Paragraph(title, styles["toc_title"]),
                Paragraph(sub, styles["toc_sub"]),
            ],
            Paragraph(page, styles["toc_page"]),
        ])

    t = Table(
        rows,
        colWidths=[0.6 * inch, 5.6 * inch, 0.8 * inch],
    )
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, GRAY_BORDER),
    ]))
    story.append(t)

    story.append(Spacer(1, 18))
    story.append(HorizontalRule(width=2.4 * inch, color=RED, thickness=1.2))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        '<font name="Times-Italic">"You don\'t need to know everything. '
        'You just need to know what to ask next."</font>',
        styles["lead"],
    ))

    story.append(PageBreak())
    return story


def build_section_1(styles):
    """Documents to Gather Before You Apply (Pages 4-5)."""
    story = []

    story.extend(section_heading(
        "SECTION 01  ·  PREPARATION",
        "Before You Even Call a Lender",
        styles,
    ))
    story.append(Paragraph(
        "The fastest pre-approvals come from buyers who have these ready on day one.",
        styles["lead"],
    ))
    story.append(Spacer(1, 4))

    # Income docs
    story.append(Paragraph("Income Documents", styles["h2"]))
    for item in [
        "Last 2 W-2 forms (most recent two tax years)",
        "Last 30 days of paystubs",
        "Last 2 years of federal tax returns — with <i>all</i> schedules attached",
    ]:
        story.append(bullet(item, styles))

    # Self-employed extras
    story.append(Paragraph("If You're Self-Employed", styles["h2"]))
    for item in [
        "2 years of business tax returns",
        "Year-to-date Profit &amp; Loss statement (P&amp;L)",
        "Business bank statements for the last 2 months",
    ]:
        story.append(bullet(item, styles))

    # Assets
    story.append(Paragraph("Assets &amp; Reserves", styles["h2"]))
    story.append(bullet(
        "Last 2 months of statements for <b>every</b> account you intend "
        "to use — checking, savings, retirement, brokerage. All pages, "
        "even if the last page is blank.",
        styles,
    ))

    # Debts
    story.append(Paragraph("Debts &amp; Obligations", styles["h2"]))
    story.append(bullet(
        "A list of every credit card, car loan, student loan, child support, "
        "and alimony — with the monthly payment amount for each. Lenders will "
        "verify, but having it ready saves a week.",
        styles,
    ))

    # ID
    story.append(Paragraph("Identification", styles["h2"]))
    for item in [
        "Driver's license or U.S. passport",
        "Social Security card (the original — not a photocopy)",
    ]:
        story.append(bullet(item, styles))

    # VA loans
    story.append(Paragraph("For VA Loan Applicants", styles["h2"]))
    for item in [
        "DD-214 form (Certificate of Release or Discharge from Active Duty)",
        "Certificate of Eligibility (COE) — your lender can pull this for you",
    ]:
        story.append(bullet(item, styles))

    # Down payment proof
    story.append(Paragraph("Down Payment Proof", styles["h2"]))
    story.append(bullet(
        "If any portion of your down payment is gift funds, you'll need a "
        "signed gift letter from the giver stating it is not a loan, plus "
        "their bank statements showing the funds.",
        styles,
    ))

    story.append(tip_box(
        "KEVIN'S TIP",
        "Don't make any large deposits in the 60 days before applying — "
        "every $1,000+ deposit will need a paper trail. Easier to just wait. "
        "If you have to make a large deposit, document it (sale of car, "
        "tax refund, etc.) the moment it happens so you don't have to "
        "reconstruct it later.",
        styles,
    ))

    # Page 5: supplementary content — "What lenders are actually looking for"
    story.append(Spacer(1, 14))
    story.append(Paragraph("What Lenders Are Actually Looking For", styles["h2"]))
    story.append(Paragraph(
        "Understanding the four pillars of mortgage qualification helps you see "
        "your file the way underwriters do. They are weighing four factors:",
        styles["body"],
    ))

    pillar_cells = []
    pillars = [
        ("Capacity",
         "Can you afford it? Measured by debt-to-income (DTI). Most loans require under 43-50%."),
        ("Credit",
         "Will you pay it back? Measured by FICO score. 620 minimum for most programs; 740+ for best rates."),
        ("Capital",
         "Down payment + reserves. Lenders like to see 2-6 months of mortgage payments left after closing."),
        ("Collateral",
         "Is the home worth the loan? Confirmed by appraisal — protects the lender if you default."),
    ]
    for title, body in pillars:
        pillar_cells.append([
            Paragraph(
                f'<font color="#c41e2a"><b>{title.upper()}</b></font>',
                ParagraphStyle("plt", fontName="Helvetica-Bold", fontSize=9.5, textColor=RED, leading=12, spaceAfter=4),
            ),
            Paragraph(body, ParagraphStyle("plb", fontName="Helvetica", fontSize=9.5, textColor=BODY, leading=13)),
        ])

    pillar_table = Table(
        [pillar_cells],
        colWidths=[1.65 * inch] * 4,
        rowHeights=[1.55 * inch],
    )
    pillar_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("BACKGROUND", (0, 0), (-1, -1), CREAM),
        ("LINEABOVE", (0, 0), (-1, 0), 1.5, RED),
        ("LINEBELOW", (0, -1), (-1, -1), 1.5, RED),
        ("LINEAFTER", (0, 0), (-2, -1), 0.4, white),
    ]))
    story.append(pillar_table)

    story.append(Spacer(1, 14))
    story.append(Paragraph(
        '<font name="Times-Italic" color="#6b7280">Underwriters cross-check every pillar — '
        'strength in one cannot fully offset weakness in another. The best '
        'pre-approvals are balanced across all four.</font>',
        styles["lead"],
    ))

    story.append(PageBreak())
    return story


def build_section_2(styles):
    """Strengthen Your Credit in 60 Days (Page 6)."""
    story = []

    story.extend(section_heading(
        "SECTION 02  ·  CREDIT",
        "Strengthen Your Credit in 60 Days",
        styles,
    ))
    story.append(Paragraph(
        "Your credit score is the single biggest factor in your mortgage rate. "
        "Here's how to move the needle fast.",
        styles["lead"],
    ))
    story.append(Spacer(1, 4))

    actions = [
        ("1",
         "Pay credit cards to under 30% utilization",
         "Below 30% of the limit — not just below the limit itself. Doing this "
         "one month before you pull your report can move scores 20+ points."),
        ("2",
         "Do not close old credit cards",
         "Average age of accounts matters. Keep older cards open with a "
         "small recurring charge (a Netflix subscription, for example) "
         "paid in full each month."),
        ("3",
         "Do not apply for any new credit",
         "Every hard pull dings your score 3-5 points, and lenders see them. "
         "No new cards, no car loans, no store financing — not until after closing."),
        ("4",
         "Pull your reports free at annualcreditreport.com",
         "Then dispute any errors. About one in four reports has something "
         "wrong on them, and the fix takes 30-60 days. Start now."),
        ("5",
         "Pay everything on time",
         "Even one 30-day late payment can drop scores 60-100 points. "
         "Set up autopay for the minimum on every account today — you can "
         "always pay more on top, but the minimum guarantees you're never late."),
        ("6",
         "Pay early in the billing cycle",
         "Credit card companies report balances mid-cycle, not after your due date. "
         "If you pay the statement balance just before the close date, the "
         "balance reported to the bureaus looks lower — which raises your score."),
    ]

    for num, header, body in actions:
        story.append(numbered_action(num, header, body, styles))

    story.append(Spacer(1, 8))
    story.append(tip_box(
        "KEVIN'S TIP",
        "If your score is borderline — say 660 — waiting 60 days to do "
        "these things could save you 0.5% on your interest rate. Over a "
        "30-year loan, that's tens of thousands of dollars. Patience pays.",
        styles,
    ))

    story.append(PageBreak())
    return story


def build_section_3(styles):
    """Pre-Approval to Closing Timeline (Pages 7-8)."""
    story = []

    story.extend(section_heading(
        "SECTION 03  ·  TIMELINE",
        "Pre-Approval to Closing",
        styles,
    ))
    story.append(Paragraph(
        "What happens, and when — from application to handing you the keys.",
        styles["lead"],
    ))
    story.append(Spacer(1, 4))

    # Timeline rows: (when, title, body)
    timeline = [
        ("DAY 1-3",
         "Submit application; lender pulls credit",
         "You fill out the application (online or in person). The lender "
         "runs a tri-merge credit report and gives you an initial read."),
        ("WEEK 1",
         "Pre-approval letter issued",
         "Once income and credit are reviewed, you receive your pre-approval "
         "letter. <b>This is the green light to start writing offers.</b>"),
        ("OFFER DAY",
         "Update pre-approval for the property",
         "When you find the home, your lender updates the letter with the "
         "exact address, offer amount, and seller name. Sellers expect this."),
        ("DAY 1-5 POST-CONTRACT",
         "Appraisal ordered; inspection scheduled",
         "Lender orders the appraisal (you pay $500-$700). You schedule the "
         "home inspection separately. Both happen in parallel."),
        ("DAY 5-15",
         "Underwriting review",
         "The underwriter scrubs everything. Expect requests for additional "
         "docs — letters of explanation, updated paystubs, source-of-funds. "
         "Respond same-day if possible."),
        ("DAY 15-25",
         "Clear to close",
         "Lender issues the &quot;clear to close&quot; — final approval. "
         "The closing disclosure is sent at least 3 business days before closing."),
        ("DAY 25-30",
         "Final walkthrough + closing",
         "You walk the home one last time (usually 24 hours before closing), "
         "sign 80-100 pages at the title company, and get the keys."),
    ]

    rows = []
    for when, title, body in timeline:
        when_para = Paragraph(when, ParagraphStyle(
            "when_inner",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=white,
            leading=12,
            alignment=TA_CENTER,
        ))
        body_block = [
            Paragraph(title, styles["timeline_title"]),
            Paragraph(body, styles["timeline_body"]),
        ]
        rows.append([when_para, body_block])

    t = Table(
        rows,
        colWidths=[1.45 * inch, 5.55 * inch],
    )
    style_cmds = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, -1), 8),
        ("RIGHTPADDING", (0, 0), (0, -1), 8),
        ("LEFTPADDING", (1, 0), (1, -1), 14),
        ("RIGHTPADDING", (1, 0), (1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (0, -1), RED),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, GRAY_BORDER),
    ]
    t.setStyle(TableStyle(style_cmds))
    story.append(t)

    story.append(PageBreak())

    # Page 8: Red flags sidebar
    story.extend(section_heading(
        "SECTION 03  ·  CONTINUED",
        "Red Flags That Could Delay Closing",
        styles,
    ))
    story.append(Paragraph(
        "From the moment your offer is accepted until you sign at closing, "
        "your financing is fragile. Avoid these — every one of them has "
        "killed a deal I've worked on.",
        styles["lead"],
    ))
    story.append(Spacer(1, 4))

    # Build sidebar as a styled box
    sidebar_header = Paragraph(
        '<font name="Helvetica-Bold" color="white" size="11">DO NOT DO ANY OF THIS</font>',
        ParagraphStyle("sh", fontName="Helvetica-Bold", fontSize=11, textColor=white, leading=14),
    )

    items = [
        ("Change jobs", "Underwriting verifies employment as recently as the day before closing. A new job — even a better one — restarts everything."),
        ("Buy a car or furniture on credit", "Your debt-to-income ratio is calculated continuously. A $500/month car payment can disqualify you outright."),
        ("Move large amounts between accounts", "Lenders look for &quot;seasoning&quot; — money that has been in your account for 60+ days. Moving funds raises flags."),
        ("Co-sign a loan for anyone else", "Co-signing counts as your debt, even though you're not the primary borrower. This includes student loans for kids."),
        ("Delay responding to your lender", "Documents requested by Friday should be back by Monday at the latest. Slow responses = delayed closings = expired rate locks."),
        ("Open or close any credit accounts", "Even closing an old card you haven't used in years can shift your score. Keep the financial picture frozen until after closing."),
    ]

    rows = [[sidebar_header, ""]]
    for title, body in items:
        rows.append([
            Paragraph(f'<font color="#c41e2a"><b>✕</b></font>', ParagraphStyle(
                "x", fontName="Helvetica-Bold", fontSize=14, textColor=RED, leading=16, alignment=TA_CENTER,
            )),
            [
                Paragraph(f"<b>{title}</b>", styles["body"]),
                Paragraph(body, ParagraphStyle(
                    "sb_b", fontName="Helvetica", fontSize=9.5, textColor=BODY, leading=13,
                )),
            ],
        ])

    sidebar_table = Table(rows, colWidths=[0.5 * inch, 6.5 * inch])
    sidebar_style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("SPAN", (0, 0), (-1, 0)),
        # Body rows
        ("BACKGROUND", (0, 1), (-1, -1), CREAM),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, white),
    ]
    sidebar_table.setStyle(TableStyle(sidebar_style))
    story.append(sidebar_table)

    story.append(PageBreak())
    return story


def build_section_4(styles):
    """Common Mortgage Types Explained (Page 9)."""
    story = []

    story.extend(section_heading(
        "SECTION 04  ·  LOAN TYPES",
        "Common Mortgage Types",
        styles,
    ))
    story.append(Paragraph(
        "Most Tampa Bay buyers use one of these four loan programs. "
        "Here's the plain-English summary of each.",
        styles["lead"],
    ))
    story.append(Spacer(1, 4))

    # Four loan type blocks as a 2x2 grid
    def loan_cell(name, tagline, body):
        return [
            Paragraph(
                f'<font name="Helvetica-Bold" color="#c41e2a" size="9">{tagline}</font>',
                styles["body"],
            ),
            Paragraph(name, ParagraphStyle(
                "ln", fontName="Times-Bold", fontSize=18, textColor=NAVY, leading=22, spaceAfter=6,
            )),
            Paragraph(body, ParagraphStyle(
                "lb", fontName="Helvetica", fontSize=9.5, textColor=BODY, leading=14,
            )),
        ]

    conv = loan_cell(
        "Conventional",
        "MOST COMMON",
        "3% to 20% down payment. Anything under 20% requires Private "
        "Mortgage Insurance (PMI), which drops off automatically once you "
        "reach 22% equity. Best for buyers with strong credit (700+).",
    )
    fha = loan_cell(
        "FHA",
        "FIRST-TIME FRIENDLY",
        "Just 3.5% down with credit scores as low as 580. Easier "
        "qualifying than conventional, but mortgage insurance (MIP) "
        "stays for the life of the loan unless you refinance. Good "
        "stepping stone.",
    )
    va = loan_cell(
        "VA",
        "FOR ELIGIBLE VETERANS",
        "Zero down. No PMI. Competitive rates. <b>Kevin's favorite for "
        "those who qualify.</b> Requires a DD-214 and Certificate of "
        "Eligibility. Funding fee can usually be rolled into the loan.",
    )
    usda = loan_cell(
        "USDA",
        "RURAL AREAS ONLY",
        "Zero down, but only in eligible USDA-designated areas. Around "
        "Tampa Bay, this means parts of Pasco, Polk, and Hernando "
        "counties — not the urban core. Income limits apply.",
    )

    grid = Table(
        [[conv, fha], [va, usda]],
        colWidths=[3.4 * inch, 3.4 * inch],
        rowHeights=[2.1 * inch, 2.1 * inch],
    )
    grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("TOPPADDING", (0, 0), (-1, -1), 16),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
        ("BACKGROUND", (0, 0), (-1, -1), CREAM),
        ("LINEABOVE", (0, 0), (-1, 0), 2, RED),
        ("LINEABOVE", (0, 1), (-1, 1), 2, RED),
        ("LINEAFTER", (0, 0), (0, -1), 0.6, white),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, white),
    ]))
    story.append(grid)

    story.append(Spacer(1, 18))

    # Footer note
    other_loans_box = Table(
        [[
            Paragraph(
                '<font name="Helvetica-Bold" color="#c41e2a">ALSO WORTH KNOWING:</font> '
                "There are <b>Jumbo loans</b> (over $766k in 2026 for most areas), "
                "<b>Doctor loans</b>, <b>Bank Statement loans</b> for the "
                "self-employed, and <b>DSCR loans</b> for investors. Ask "
                "Kevin which fits your situation.",
                ParagraphStyle("other", fontName="Helvetica", fontSize=10, leading=15, textColor=NAVY),
            )
        ]],
        colWidths=[7.0 * inch],
    )
    other_loans_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#fdf3f4")),
        ("LINEBEFORE", (0, 0), (0, -1), 3, RED),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(other_loans_box)

    story.append(PageBreak())
    return story


def build_section_5(styles):
    """Red Flags to Avoid (Page 10)."""
    story = []

    story.extend(section_heading(
        "SECTION 05  ·  WARNINGS",
        "Red Flags to Avoid",
        styles,
    ))
    story.append(Paragraph(
        "Six warning signs that should make you slow down — or walk away.",
        styles["lead"],
    ))
    story.append(Spacer(1, 4))

    warnings = [
        ("Lenders who say \"we don't pull credit yet\"",
         "They literally cannot give you a real pre-approval without a credit "
         "pull. What they're offering is a pre-qualification — a guess. "
         "Sellers will not take it seriously."),
        ("Rates that seem too good to be true",
         "Often there are hidden fees, short rate locks (15 days), or "
         "buy-downs baked in that you'll pay for at closing. Always compare "
         "the APR, not just the rate."),
        ("\"Buy down\" pitches without math",
         "Paying points to lower your rate can be smart — or terrible. "
         "Get the actual cost in dollars vs. the monthly savings, divide, "
         "and see how long it takes to break even. Some don't pencil out."),
        ("Pressure to close in under 21 days",
         "Sometimes legitimate (you'll lose the deal otherwise), but "
         "sometimes a sign the lender is hiding issues that will surface "
         "in underwriting. Ask why the rush."),
        ("Adjustable Rate Mortgages (ARMs) right now",
         "Fixed rates have been favorable in 2026. ARMs only make sense if "
         "you genuinely plan to sell or refinance in 5-7 years. For most "
         "buyers, the stability of a fixed rate is worth it."),
        ("Online-only lenders for first-time buyers",
         "When the loan hits a snag at 11pm three days before closing, "
         "you want a person you can call. For your first home, work with "
         "someone local who answers the phone."),
    ]

    for i, (header, body) in enumerate(warnings, 1):
        story.append(numbered_action(str(i), header, body, styles))

    story.append(PageBreak())
    return story


def build_section_6(styles):
    """Kevin's Preferred Lender Network (Page 11)."""
    story = []

    story.extend(section_heading(
        "SECTION 06  ·  REFERRALS",
        "Kevin's Preferred Lender Network",
        styles,
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Forty years of working with Tampa Bay lenders means a short list "
        "of names I trust completely.",
        styles["lead"],
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        "Kevin maintains relationships with 4-6 trusted Tampa Bay lenders who "
        "consistently close on time, communicate clearly, and offer competitive "
        "rates. Different lenders are better for different situations — first-time "
        "buyers, self-employed borrowers, jumbo loans, VA loans, and "
        "investor financing each have a specialist on the list.",
        styles["welcome_body"],
    ))

    story.append(Paragraph(
        "When you are ready to apply, Kevin will introduce you personally. "
        "These are not paid referrals — there are no kickbacks, no quotas, "
        "and no commissions exchanged. They are simply 40 years of trust "
        "with people who have earned it.",
        styles["welcome_body"],
    ))

    story.append(Paragraph(
        "Ask Kevin for the right introduction based on your situation. "
        "He'll send an email or text introducing you directly to the right "
        "person, share what you'll need, and then step back so you can have "
        "an honest conversation.",
        styles["welcome_body"],
    ))

    story.append(Spacer(1, 16))

    # Three principle cards
    principles = [
        ("01", "No kickbacks",
         "Kevin earns nothing from these introductions. The recommendation "
         "is based purely on the lender's track record."),
        ("02", "Always closes on time",
         "Every lender on the list has a multi-year history of closing on "
         "or before the contracted date with Kevin's clients."),
        ("03", "Answers the phone",
         "On nights, weekends, and the day before closing. The kind of "
         "service you cannot get from an online-only lender."),
    ]

    cells = []
    for num, title, body in principles:
        cell = [
            Paragraph(num, ParagraphStyle(
                "pn", fontName="Times-Bold", fontSize=28, textColor=RED, leading=32, alignment=TA_LEFT, spaceAfter=4,
            )),
            Paragraph(title, ParagraphStyle(
                "pt", fontName="Helvetica-Bold", fontSize=11, textColor=NAVY, leading=14, alignment=TA_LEFT, spaceAfter=6,
            )),
            Paragraph(body, ParagraphStyle(
                "pb", fontName="Helvetica", fontSize=9.5, textColor=BODY, leading=13, alignment=TA_LEFT,
            )),
        ]
        cells.append(cell)

    principle_table = Table(
        [cells],
        colWidths=[2.27 * inch] * 3,
        rowHeights=[1.95 * inch],
    )
    principle_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("TOPPADDING", (0, 0), (-1, -1), 18),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
        ("BACKGROUND", (0, 0), (-1, -1), CREAM),
        ("LINEAFTER", (0, 0), (-2, -1), 0.6, white),
        ("LINEABOVE", (0, 0), (-1, 0), 2, RED),
    ]))
    story.append(principle_table)

    story.append(PageBreak())
    return story


def build_section_7(styles):
    """FAQ (Page 12)."""
    story = []

    story.extend(section_heading(
        "SECTION 07  ·  FAQ",
        "Frequently Asked Questions",
        styles,
    ))
    story.append(Paragraph(
        "The six questions Kevin hears most often from buyers.",
        styles["lead"],
    ))
    story.append(Spacer(1, 4))

    faqs = [
        ("How much should I get pre-approved for vs. how much should I actually spend?",
         "These are different answers. Kevin's rule: spend no more than 28% of "
         "your gross monthly income on PITI (Principal, Interest, Taxes, Insurance), "
         "even if the bank approves you for more. Banks approve based on what you "
         "<i>could</i> afford on paper — not what you can afford while still "
         "living comfortably."),
        ("What is PITI?",
         "Principal, Interest, Taxes, and Insurance — the four components of your "
         "monthly mortgage payment. Property taxes in Hillsborough County are roughly "
         "1.1% of value; Pinellas is around 0.97%. Homeowners insurance in Tampa Bay "
         "is high — $3,500 to $8,000 per year is normal in 2026, especially in "
         "coastal areas. Budget accordingly."),
        ("Should I pay points to lower my rate?",
         "Math depends on how long you'll stay. If you'll be in the home 7+ years, "
         "often yes. Under 5 years, usually no. Ask your lender for the break-even "
         "point in months — that's the only number that matters."),
        ("What's the difference between pre-qualification and pre-approval?",
         "Pre-qualification is a quick guess based on what you tell the lender — no "
         "verification. Pre-approval involves credit pull, income docs, and asset "
         "review. Sellers will not take pre-quals seriously, especially in "
         "multiple-offer situations."),
        ("Can I close in my LLC?",
         "Yes for investment properties — and often the best way to structure them. "
         "Usually not for a primary residence, because conventional financing requires "
         "you take title individually. Commercial-style DSCR loans allow LLC ownership "
         "but at higher rates. Kevin can walk you through the trade-offs."),
        ("What if I'm self-employed?",
         "You have options. Bank statement loans use 12-24 months of deposits to "
         "qualify. P&amp;L loans use a CPA-prepared profit and loss. DSCR loans for "
         "investors qualify on the property's income, not yours. Plan on 24 months "
         "of business tax returns for traditional financing."),
    ]

    for q, a in faqs:
        story.append(Paragraph(f'<font color="#c41e2a">Q.</font> &nbsp; {q}', styles["q"]))
        story.append(Paragraph(a, styles["a"]))

    story.append(PageBreak())
    return story


def build_section_8(styles):
    """Glossary (Page 13)."""
    story = []

    story.extend(section_heading(
        "SECTION 08  ·  GLOSSARY",
        "Plain-English Mortgage Terms",
        styles,
    ))
    story.append(Paragraph(
        "Print this page, or fold the corner. You'll come back to it.",
        styles["lead"],
    ))
    story.append(Spacer(1, 4))

    glossary = [
        ("PITI",
         "Principal, Interest, Taxes, and Insurance — the four parts of your monthly payment."),
        ("LTV (Loan-to-Value)",
         "The size of your loan as a percentage of the home's value. 80% LTV means you put 20% down."),
        ("DTI (Debt-to-Income)",
         "Your monthly debt payments divided by your gross monthly income. Most loans require DTI under 43-50%."),
        ("APR vs. Rate",
         "The interest rate is what you pay on the loan. APR includes the rate plus fees, expressed annually — a truer comparison number."),
        ("PMI (Private Mortgage Insurance)",
         "Required on conventional loans when you put less than 20% down. Drops off automatically at 22% equity."),
        ("MI / MIP (Mortgage Insurance Premium)",
         "FHA's version of PMI. Stays for the life of the loan unless you refinance to a conventional product."),
        ("Escrow",
         "A neutral third-party account. Used both for earnest money during the contract, and for taxes/insurance after closing (paid monthly with your mortgage)."),
        ("Title",
         "Legal ownership of the home. A title company verifies the title is clean and issues title insurance to protect you and the lender."),
        ("Points (Discount Points)",
         "Pre-paid interest that buys down your rate. One point equals 1% of the loan amount and typically lowers the rate 0.25%."),
        ("Origination Fee",
         "The lender's fee for processing the loan. Usually 0.5% to 1% of the loan amount. Negotiable."),
        ("Earnest Money",
         "A good-faith deposit (typically 1-3% of the purchase price in Tampa Bay) held in escrow when your offer is accepted."),
        ("Appraisal Contingency",
         "A contract clause that lets you walk away (or renegotiate) if the home appraises for less than your offer."),
        ("Inspection Contingency",
         "A clause that lets you back out, ask for repairs, or renegotiate based on the home inspection findings."),
    ]

    # Build a two-column layout for compactness
    rows = []
    for term, definition in glossary:
        rows.append([
            Paragraph(term, styles["glossary_term"]),
            Paragraph(definition, styles["glossary_def"]),
        ])

    t = Table(
        rows,
        colWidths=[1.7 * inch, 5.3 * inch],
    )
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, GRAY_BORDER),
    ]))
    story.append(t)

    story.append(PageBreak())
    return story


def build_cta(styles):
    """Final CTA page (Page 14)."""
    story = []

    story.append(Spacer(1, 0.3 * inch))

    # Eyebrow
    story.append(Paragraph(
        '<para align="center"><font color="#c41e2a"><b>READY TO START</b></font></para>',
        ParagraphStyle("cta_eye", fontName="Helvetica-Bold", fontSize=10, textColor=RED, leading=12, alignment=TA_CENTER, spaceAfter=10),
    ))

    # Headline
    story.append(Paragraph("Let's make a plan.", styles["cta_h"]))
    story.append(Paragraph(
        "No pressure. No pitch. Just an honest conversation about your goals.",
        styles["cta_sub"],
    ))

    # Center the photo placeholder using a table
    photo_table = Table(
        [[CircleInitials(size=1.6 * inch, initials="KF")]],
        colWidths=[7.0 * inch],
        rowHeights=[1.6 * inch],
    )
    photo_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(photo_table)
    story.append(Spacer(1, 16))

    # Name and title
    story.append(Paragraph(
        '<para align="center"><font name="Times-Bold" size="18" color="#111111">Kevin Freel</font></para>',
        ParagraphStyle("name", fontSize=18, leading=22, alignment=TA_CENTER),
    ))
    story.append(Paragraph(
        '<para align="center"><font name="Helvetica" size="9" color="#6b7280">REALTOR  ·  CENTURY 21 BEGGINS</font></para>',
        ParagraphStyle("title", fontSize=9, leading=14, alignment=TA_CENTER, spaceAfter=20),
    ))

    # Phone (large)
    story.append(Paragraph("727-410-8599", styles["cta_phone"]))
    story.append(Spacer(1, 14))

    # Other contact lines
    story.append(Paragraph("KevinFreel@c21be.com", styles["cta_meta"]))
    story.append(Paragraph("kevinfreel.com", styles["cta_meta"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("1501 South Dale Mabry A1  ·  Tampa, FL 33629", styles["cta_meta"]))

    story.append(Spacer(1, 30))

    # Divider
    div_table = Table(
        [[HorizontalRule(width=2.4 * inch, color=RED, thickness=1.5)]],
        colWidths=[7.0 * inch],
    )
    div_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(div_table)
    story.append(Spacer(1, 14))

    # Tagline
    story.append(Paragraph(
        "Tampa Bay's most experienced Realtor.",
        styles["cta_tag"],
    ))
    story.append(Paragraph(
        '<font name="Times-BoldItalic" color="#c41e2a">Real advice. No pressure.</font>',
        styles["cta_tag"],
    ))

    return story


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build():
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)

    doc = SimpleDocTemplate(
        OUT_PATH,
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.95 * inch,
        bottomMargin=0.85 * inch,
        title="Mortgage & Financing Roadmap",
        author="Kevin Freel",
        subject="A buyer's guide to mortgage financing in Tampa Bay",
    )

    styles = make_styles()

    story = []
    story.extend(build_cover(styles))
    story.extend(build_welcome(styles))
    story.extend(build_toc(styles))
    story.extend(build_section_1(styles))
    story.extend(build_section_2(styles))
    story.extend(build_section_3(styles))
    story.extend(build_section_4(styles))
    story.extend(build_section_5(styles))
    story.extend(build_section_6(styles))
    story.extend(build_section_7(styles))
    story.extend(build_section_8(styles))
    story.extend(build_cta(styles))

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)

    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    build()
