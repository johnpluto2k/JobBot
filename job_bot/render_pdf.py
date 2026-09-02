"""Render a TailoredResume to an ATS-clean one-page PDF via reportlab.

The business track's shipping artifact is the DOCX (per
`docs/resume_track_contract.md`); this is the on-screen preview of the same
content, and it deliberately mirrors the DOCX's structure — same section order,
same absence of a Summary, same organization-left / dates-right and role-left /
location-right entry headers, same categorized skills.

Sizing is two-sided. `resume_fit` first evens the bullet counts and trims any
tail content that cannot fit one page — the same trim the DOCX applies, so the
two formats always carry identical text — and then the scale search below picks
the *largest* type and spacing that still fit a single page. The old version
only ever shrank, so a short profile came out floating in a band of white space.

Each candidate scale is laid out by reportlab itself into memory and its page
count read back, so the fit is exact rather than estimated — no page-two
surprises, and no second copy of reportlab's spacing rules to keep in sync.
"""

from __future__ import annotations

from pathlib import Path

from . import resume_fit
from .resume_models import TailoredResume
from .writing_style import split_metrics

# Scale bounds for the PDF's own type. 1.0 is the historical size (9.5pt body).
MIN_SCALE, MAX_SCALE = 0.78, 1.30


def render_pdf(resume: TailoredResume, out_path: Path,
               trimmed: list[str] | None = None,
               prefitted: bool = False) -> Path:
    if not prefitted:
        resume, dropped = resume_fit.trim_to_fit(resume)
        if trimmed is not None:
            trimmed.extend(dropped)

    lo, hi = MIN_SCALE, MAX_SCALE
    if _fits(resume, hi):
        best = hi
    elif not _fits(resume, lo):
        best = lo                      # too long even fully compressed
    else:
        for _ in range(18):
            mid = (lo + hi) / 2
            if _fits(resume, mid):
                lo = mid
            else:
                hi = mid
        best = lo

    _render_at_scale(resume, out_path, best)
    return out_path


def _margins(scale: float) -> tuple[float, float]:
    """Margins tighten with the type, but never past the 0.5" ATS floor."""
    return max(36.0, 36.0 * scale), max(36.0, 43.0 * scale)


def _fits(resume: TailoredResume, scale: float) -> bool:
    """Exact: lay the flow out with reportlab itself and ask how many pages it
    took. Building to memory is cheap (a few ms), and it removes every class of
    "my height model disagrees with the layout engine" bug."""
    from io import BytesIO

    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate

    vmargin, hmargin = _margins(scale)
    doc = SimpleDocTemplate(BytesIO(), pagesize=letter,
                            topMargin=vmargin, bottomMargin=vmargin,
                            leftMargin=hmargin, rightMargin=hmargin)
    doc.build(_build_flow(resume, scale))
    return doc.page <= 1


def _render_at_scale(resume: TailoredResume, out_path: Path, scale: float) -> Path:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate

    out_path.parent.mkdir(parents=True, exist_ok=True)
    vmargin, hmargin = _margins(scale)
    doc = SimpleDocTemplate(str(out_path), pagesize=letter,
                            topMargin=vmargin, bottomMargin=vmargin,
                            leftMargin=hmargin, rightMargin=hmargin)
    doc.build(_build_flow(resume, scale))
    return out_path


def _build_flow(resume: TailoredResume, scale: float) -> list:
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import HRFlowable, Paragraph, Table, TableStyle

    def s(v: float) -> float:
        return round(v * scale, 2)

    _, hmargin = _margins(scale)
    avail_w = 612.0 - 2 * hmargin

    styles = getSampleStyleSheet()

    def style(name, size, **kw):
        # Leading is always derived from the size. The old styles inherited a
        # fixed 12pt leading from Normal, so scaled type either overlapped the
        # line above or floated in an oversized box.
        kw.setdefault("leading", round(size * 1.2, 2))
        return ParagraphStyle(name, parent=styles["Normal"], fontSize=size, **kw)

    name_s = style("name", s(17), fontName="Helvetica-Bold",
                   alignment=TA_CENTER, spaceAfter=s(2))
    contact_s = style("contact", s(9), alignment=TA_CENTER, spaceAfter=s(6))
    head_s = style("head", s(11), fontName="Helvetica-Bold",
                   spaceBefore=s(8), spaceAfter=s(3))
    # Justified so a wrapped line runs the full width of the column instead of
    # trailing off ragged halfway across.
    body_s = style("body", s(9.5), alignment=TA_JUSTIFY)
    left_s = style("left", s(9.5))
    right_s = style("right", s(9.5), alignment=2)          # TA_RIGHT
    bullet_s = style("bullet", s(9.5), leftIndent=s(14), bulletIndent=s(4),
                     spaceAfter=s(1.5), alignment=TA_JUSTIFY)

    flow: list = []

    def heading(t: str):
        flow.append(Paragraph(t.upper(), head_s))
        # spaceBefore here is the gap between the heading's descender line and
        # the rule; at 1pt (the old value) the rule read as cutting into the
        # letters, so it scales with the type like everything else.
        flow.append(HRFlowable(width="100%", thickness=0.6,
                               spaceBefore=s(2.5), spaceAfter=s(3.5),
                               color="black"))

    def two_col(left_html: str, right_html: str, pad_top: float = 0.0):
        """One entry line: content left, dates/location flush right.

        A borderless two-column table is the only reliable way to get a right
        margin flush in reportlab. It carries no table semantics into the PDF —
        extraction reads the cells in order — so it stays ATS-clean.
        """
        t = Table([[Paragraph(left_html, left_s), Paragraph(right_html, right_s)]],
                  colWidths=[avail_w * 0.68, avail_w * 0.32])
        t.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), pad_top),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        flow.append(t)

    def entry(left: str, right: str | None,
              sub: str | None = None, sub_right: str | None = None):
        two_col(f"<b>{_esc(left)}</b>", f"<b>{_esc(right or '')}</b>", pad_top=s(5))
        if sub or sub_right:
            two_col(f"<i>{_esc(sub or '')}</i>", f"<i>{_esc(sub_right or '')}</i>")

    def _bold_metrics(text: str) -> str:
        # Playbook: bold all metrics — recruiters scan numbers first.
        return "".join(f"<b>{_esc(c)}</b>" if m else _esc(c)
                       for c, m in split_metrics(text))

    def bullets(items):
        # A plain Paragraph with bulletText puts the glyph on the first line's
        # own baseline. The ListFlowable/ListItem nesting this replaces stacked
        # three separate indents and dropped the bullet below its text.
        for b in items:
            flow.append(Paragraph(_bold_metrics(b), bullet_s, bulletText="•"))

    flow.append(Paragraph((resume.name or "").upper(), name_s))
    flow.append(Paragraph(_esc(resume.contact_line), contact_s))

    # Section order per docs/resume_track_contract.md. No Summary section on
    # this track — deliberately.
    def role_section(title, roles):
        if not roles:
            return
        heading(title)
        for role in roles:
            entry(role.organization or role.role or "", role.dates,
                  sub=role.role if role.organization else None,
                  sub_right=role.location)
            if role.bullets:
                bullets(role.bullets)

    role_section("Experience", resume.experience)
    role_section("Leadership & Activities", resume.leadership)

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
                flow.append(Paragraph("<b>Relevant Coursework:</b> "
                                      + _esc(", ".join(e.coursework)), body_s))

    if resume.projects:
        heading("Projects")
        for p in resume.projects:
            entry(p.organization or p.role or "", None)
            if p.bullets:
                bullets(p.bullets)

    groups = resume_fit.display_skill_groups(resume)
    if groups or resume.skills:
        heading("Technical Skills")
        if groups:
            for g in groups:
                flow.append(Paragraph(f"<b>{_esc(g.label)}:</b> "
                                      + _esc(", ".join(g.skills)), body_s))
        else:
            flow.append(Paragraph(_esc(", ".join(resume.skills)), body_s))
    if resume.certifications:
        flow.append(Paragraph("<b>Certifications:</b> "
                              + _esc(", ".join(resume.certifications)), body_s))

    return flow


def _esc(t: str) -> str:
    return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
