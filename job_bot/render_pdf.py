"""Render a TailoredResume to an ATS-clean one-page PDF via reportlab.

If the content overflows a single page at the default scale, the renderer
automatically re-runs with progressively tighter type + spacing until it fits
one page (down to a readable floor) — so a slightly longer profile stays
one-page without hand-tuning constants.
"""

from __future__ import annotations

from pathlib import Path

from .resume_models import TailoredResume
from .writing_style import split_metrics


def render_pdf(resume: TailoredResume, out_path: Path) -> Path:
    # Try full size first, then compress toward a readable floor until it's one
    # page. reportlab can't report page count mid-build, so we render, count via
    # PyMuPDF, and retry at a smaller scale if needed.
    scales = (1.0, 0.94, 0.88, 0.82, 0.76)
    for i, scale in enumerate(scales):
        _render_at_scale(resume, out_path, scale)
        if i == len(scales) - 1:
            break  # last resort — keep whatever we produced
        try:
            import fitz
            with fitz.open(out_path) as doc:
                if len(doc) <= 1:
                    break
        except Exception:
            break  # can't measure (no PyMuPDF) — accept the default-scale render
    return out_path


def _render_at_scale(resume: TailoredResume, out_path: Path, scale: float) -> Path:
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        HRFlowable,
        ListFlowable,
        ListItem,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
    )

    def s(v: float) -> float:
        return round(v * scale, 2)

    styles = getSampleStyleSheet()
    name_s = ParagraphStyle("name", parent=styles["Normal"], fontName="Helvetica-Bold",
                            fontSize=s(17), alignment=TA_CENTER, spaceAfter=s(2))
    contact_s = ParagraphStyle("contact", parent=styles["Normal"], fontSize=s(9),
                               alignment=TA_CENTER, spaceAfter=s(6))
    head_s = ParagraphStyle("head", parent=styles["Normal"], fontName="Helvetica-Bold",
                            fontSize=s(11), spaceBefore=s(7), spaceAfter=s(2))
    body_s = ParagraphStyle("body", parent=styles["Normal"], fontSize=s(9.5), leading=s(11.5))
    entry_s = ParagraphStyle("entry", parent=body_s, fontName="Helvetica-Bold")
    italic_s = ParagraphStyle("italic", parent=body_s, fontName="Helvetica-Oblique")
    bullet_s = ParagraphStyle("bullet", parent=body_s, leftIndent=12, spaceAfter=s(1))

    flow = []

    def heading(t: str):
        flow.append(Paragraph(t.upper(), head_s))
        flow.append(HRFlowable(width="100%", thickness=0.6, spaceBefore=1, spaceAfter=3,
                               color="black"))

    def entry(left: str, right: str | None, sub: str | None = None):
        line = f"<b>{_esc(left)}</b>"
        if right:
            line += f' &nbsp;&nbsp;<font size=9>— {_esc(right)}</font>'
        flow.append(Paragraph(line, body_s))
        if sub:
            flow.append(Paragraph(f"<i>{_esc(sub)}</i>", italic_s))

    def _bold_metrics(text: str) -> str:
        # Playbook: bold all metrics — recruiters scan numbers first.
        return "".join(f"<b>{_esc(c)}</b>" if m else _esc(c)
                       for c, m in split_metrics(text))

    def bullets(items):
        flow.append(ListFlowable(
            [ListItem(Paragraph(_bold_metrics(b), bullet_s), leftIndent=12, value="•")
             for b in items],
            bulletType="bullet", start="•", leftIndent=10,
        ))

    flow.append(Paragraph((resume.name or "").upper(), name_s))
    flow.append(Paragraph(_esc(resume.contact_line), contact_s))

    if resume.summary:
        heading("Summary")
        flow.append(Paragraph(_esc(resume.summary), body_s))

    if resume.education:
        heading("Education")
        for e in resume.education:
            entry(e.school or "", e.graduation_date)
            deg = e.degree or ""
            if e.gpa:
                deg += f"  |  GPA: {e.gpa}"
            flow.append(Paragraph(_esc(deg), body_s))
            if e.secondary:
                flow.append(Paragraph(_esc(e.secondary), body_s))
            if e.coursework:
                flow.append(Paragraph("<b>Relevant Coursework:</b> " + _esc(", ".join(e.coursework)),
                                      body_s))

    def role_section(title, roles):
        if not roles:
            return
        heading(title)
        for role in roles:
            sub = None
            if role.role and role.organization:
                sub = role.role + (f"  |  {role.location}" if role.location else "")
            entry(role.organization or role.role or "", role.dates, sub)
            if role.bullets:
                bullets(role.bullets)

    role_section("Experience", resume.experience)
    role_section("Leadership & Activities", resume.leadership)

    if resume.projects:
        heading("Projects")
        for p in resume.projects:
            entry(p.organization or p.role or "", None)
            if p.bullets:
                bullets(p.bullets)

    if resume.skills:
        heading("Skills")
        flow.append(Paragraph(_esc(", ".join(resume.skills)), body_s))
    if resume.certifications:
        flow.append(Paragraph("<b>Certifications:</b> " + _esc(", ".join(resume.certifications)),
                              body_s))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Margins compress with scale too, but not below a sane minimum.
    vmargin = max(0.4, 0.5 * scale) * inch
    hmargin = max(0.5, 0.6 * scale) * inch
    doc = SimpleDocTemplate(str(out_path), pagesize=letter,
                            topMargin=vmargin, bottomMargin=vmargin,
                            leftMargin=hmargin, rightMargin=hmargin)
    doc.build(flow)
    return out_path


def _esc(t: str) -> str:
    return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
