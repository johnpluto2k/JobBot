"""Render a TailoredResume to an ATS-clean one-page DOCX (business / VMH track).

Format rules (from the master plan): single column, no tables/text boxes/
graphics, standard font (Calibri), black only, 0.5"+ margins, strong action
verbs, no pronouns. Section order and the 10–11pt type band come from
`docs/resume_track_contract.md`.

Layout is fitted rather than fixed: `resume_fit` evens the bullet counts, trims
whole uniform rows that cannot fit, and picks the type/spacing/margin scale that
fills exactly one page — so a long profile compresses instead of spilling onto a
half-empty second page and a short one opens up instead of leaving dead space.
"""

from __future__ import annotations

from pathlib import Path

from . import resume_fit
from .resume_fit import FONT, VMARGIN, Block, clean_text
from .resume_models import TailoredResume

BODY_PT = resume_fit.BODY_PT
NAME_PT = resume_fit.NAME_PT
HEAD_PT = resume_fit.HEAD_PT


def render_docx(resume: TailoredResume, out_path: Path,
                trimmed: list[str] | None = None,
                prefitted: bool = False) -> Path:
    """Write `resume` to `out_path` as a one-page DOCX.

    If `trimmed` is a list, the names of any content dropped to make the page
    fit are appended to it so the caller can report them. Pass `prefitted=True`
    when the caller has already run `resume_fit.trim_to_fit` — that is what
    lets the ATS re-score describe the document actually shipped rather than a
    fuller version of it.
    """
    import docx
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt, RGBColor

    if not prefitted:
        resume, dropped = resume_fit.trim_to_fit(resume)
        if trimmed is not None:
            trimmed.extend(dropped)
    blocks, sizes = resume_fit.layout(resume)
    hmargin = sizes["_hmargin"]

    doc = docx.Document()

    # Auto-hyphenation was tried here to tighten justified text and withdrawn:
    # Word split "SuccessFactors" into "SuccessFac-" / "tors" and left "ing II"
    # alone on a line under Education. Big 4 resumes do not contain mid-word
    # hyphenation, and a five-character orphan line reads as a corrupt file.
    # Justification is kept (an explicit user preference) with the measure held
    # at 0.75" margins, which is what actually keeps the word spacing sane.

    for section in doc.sections:
        section.top_margin = section.bottom_margin = Pt(VMARGIN)
        section.left_margin = section.right_margin = Pt(hmargin)

    # Word's docDefaults ship 1.15 line spacing and 10pt space-after. Both are
    # overridden explicitly — otherwise every paragraph carries an invisible
    # half-blank line and the whole resume reads as full of gaps.
    for style_name in ("Normal", "List Bullet"):
        try:
            st = doc.styles[style_name]
        except KeyError:
            continue
        st.font.name = FONT
        st.font.size = Pt(BODY_PT)
        st.font.color.rgb = RGBColor(0, 0, 0)
        pf = st.paragraph_format
        pf.space_before = Pt(0)
        pf.space_after = Pt(0)
        pf.line_spacing = 1.0

    def _track(run, points: float) -> None:
        """Condensed letter-spacing (Word's run-level w:spacing, in twentieths
        of a point). Used only where it wins back a whole line — see
        `resume_fit.assign_tracking`."""
        if not points:
            return
        rPr = run._r.get_or_add_rPr()
        el = OxmlElement("w:spacing")
        el.set(qn("w:val"), str(int(round(points * 20))))
        rPr.append(el)

    def add(blk: Block) -> None:
        pt, before, after, indent = sizes[blk.kind]
        p = doc.add_paragraph(style="List Bullet" if blk.kind == "bullet" else None)
        pf = p.paragraph_format
        pf.space_before = Pt(before)
        pf.space_after = Pt(after)
        pf.line_spacing = 1.0
        if indent:
            pf.left_indent = Pt(indent)
        if blk.kind in ("name", "contact"):
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif blk.kind in ("bullet", "body"):
            # Justified so a wrapped line runs the full width of the column
            # instead of trailing off ragged halfway across.
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        if blk.tail:
            pf.tab_stops.add_tab_stop(Pt(sizes["_usable_w"]), WD_TAB_ALIGNMENT.RIGHT)

        runs = []
        for text, bold, italic in blk.runs:
            r = p.add_run(clean_text(text))
            r.bold = bold
            r.italic = italic
            r.font.size = Pt(pt)
            runs.append(r)
        if blk.tail:
            r = p.add_run("\t" + blk.tail)
            # The date column matches the weight of the line it sits on: bold
            # beside the organization, italic beside the role.
            r.bold = blk.kind == "entry"
            r.italic = blk.kind == "sub"
            r.font.size = Pt(pt)
            runs.append(r)
        for r in runs:
            _track(r, blk.track)

        if blk.kind == "head":
            pbdr = OxmlElement("w:pBdr")
            bottom = OxmlElement("w:bottom")
            bottom.set(qn("w:val"), "single")
            bottom.set(qn("w:sz"), "6")                      # 0.75pt rule
            bottom.set(qn("w:space"), str(sizes["_border_space"]))
            bottom.set(qn("w:color"), "000000")
            pbdr.append(bottom)
            p._p.get_or_add_pPr().append(pbdr)

    for blk in blocks:
        add(blk)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    return out_path
