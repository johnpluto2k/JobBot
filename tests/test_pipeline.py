"""Regression test for the tailoring/rendering pipeline (no LLM, no network).

Runs the Phase 4 pipeline against a fixture JD and asserts every renderer
(docx, reportlab PDF, RenderCV PDF) produces a valid one-page file — so
renderer changes can't silently break output.

Run either way:
    python -m tests.test_pipeline        # plain script, no pytest needed
    python -m pytest tests/              # if pytest is installed

Skips (doesn't fail) when an optional piece is missing: the built profile
(data/master_profile.json) or the rendercv package.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

FIXTURE_JD = PROJECT_ROOT / "data" / "sample_jd_deloitte_itrisk.txt"


def _skip(msg: str):
    print(f"SKIP: {msg}")
    try:
        import pytest
        pytest.skip(msg)
    except ImportError:
        pass


def _load() -> tuple[dict, object] | None:
    from job_bot import config
    from job_bot.jd_parser import parse_jd

    if not config.PROFILE_JSON.exists():
        _skip("no data/master_profile.json — run job_bot.build_profile first")
        return None
    if not FIXTURE_JD.exists():
        _skip(f"fixture JD missing: {FIXTURE_JD}")
        return None
    import json
    profile = json.loads(config.PROFILE_JSON.read_text(encoding="utf-8"))
    job = parse_jd(FIXTURE_JD.read_text(encoding="utf-8"), use_llm=False)
    return profile, job


def _pdf_pages(path: Path) -> int:
    import fitz
    with fitz.open(path) as doc:
        return len(doc)


def test_tailor_and_docx():
    loaded = _load()
    if not loaded:
        return
    profile, job = loaded
    from job_bot.render_docx import render_docx
    from job_bot.tailor import tailor_resume

    resume = tailor_resume(profile, job, use_llm=False)
    assert resume.experience, "tailored resume has no experience roles"
    assert resume.skills, "tailored resume has no skills"

    with tempfile.TemporaryDirectory() as tmp:
        out = render_docx(resume, Path(tmp) / "resume.docx")
        assert out.exists() and out.stat().st_size > 5000, "docx missing/empty"
        import docx
        text = "\n".join(p.text for p in docx.Document(str(out)).paragraphs)
        # render_docx uppercases the name
        assert resume.name and resume.name.lower() in text.lower(), \
            "name missing from docx"
    print("ok: tailor + docx")


def test_reportlab_pdf_one_page():
    loaded = _load()
    if not loaded:
        return
    profile, job = loaded
    from job_bot.render_pdf import render_pdf
    from job_bot.tailor import tailor_resume

    resume = tailor_resume(profile, job, use_llm=False)
    with tempfile.TemporaryDirectory() as tmp:
        out = render_pdf(resume, Path(tmp) / "resume.pdf")
        assert out.exists() and out.stat().st_size > 1000, "pdf missing/empty"
        assert _pdf_pages(out) == 1, "reportlab PDF is not one page"
    print("ok: reportlab pdf (1 page)")


def test_rendercv_pdf_one_page_and_parseable():
    loaded = _load()
    if not loaded:
        return
    profile, job = loaded
    try:
        import rendercv  # noqa: F401
    except ImportError:
        _skip("rendercv not installed")
        return
    from job_bot.render_rendercv import render_rendercv
    from job_bot.tailor import tailor_resume

    resume = tailor_resume(profile, job, use_llm=False)
    with tempfile.TemporaryDirectory() as tmp:
        out = render_rendercv(resume, Path(tmp) / "resume.pdf")
        assert out.exists() and out.stat().st_size > 1000, "pdf missing/empty"
        assert (out.parent / "resume.yaml").exists(), "resume.yaml not written"
        assert _pdf_pages(out) == 1, "RenderCV PDF is not one page"
        # ATS-safety: extracted text must be clean and complete
        import fitz
        with fitz.open(out) as doc:
            text = "\n".join(p.get_text() for p in doc)
        assert resume.name and resume.name in text, "name missing from PDF text"
        for section in ("Education", "Experience", "Skills"):
            assert section.lower() in text.lower(), f"{section} missing from PDF text"
        bad = [c for c in text if 0xE000 <= ord(c) <= 0xF8FF or c == "�"]
        assert not bad, f"{len(bad)} unparseable glyphs in PDF text layer"
    print("ok: rendercv pdf (1 page, clean text layer)")


def test_docx_fills_one_page_with_clear_section_rules():
    """The DOCX must fill one page and no more: content trimmed to fit, type
    scaled up to close any leftover gap, and section rules held clear of the
    heading text instead of sitting on its descender line."""
    loaded = _load()
    if not loaded:
        return
    profile, job = loaded
    from job_bot import resume_fit
    from job_bot.render_docx import render_docx
    from job_bot.tailor import tailor_resume

    resume = tailor_resume(profile, job, use_llm=False)
    fitted, dropped = resume_fit.trim_to_fit(resume)
    # Measure through `layout()` — the same call `render_docx` makes. Building
    # the blocks by hand here skipped `assign_tracking`, so the test was sizing
    # a layout that is never rendered: untracked text wraps onto lines the real
    # DOCX doesn't have, reading ~35pt taller. That error was invisible while
    # the profile was thin and became a false failure as soon as it grew.
    blocks, sizes = resume_fit.layout(fitted)
    height = resume_fit.estimate_height(blocks, sizes)

    assert height <= resume_fit.USABLE_H,         f"docx layout overflows one page ({height:.0f}pt of {resume_fit.USABLE_H:.0f})"
    assert height >= resume_fit.USABLE_H * 0.85,         f"docx layout leaves {resume_fit.USABLE_H - height:.0f}pt of dead space"
    assert fitted.experience and fitted.skills, "trimming gutted the resume"

    with tempfile.TemporaryDirectory() as tmp:
        out = render_docx(resume, Path(tmp) / "resume.docx")
        import docx
        from docx.oxml.ns import qn
        doc = docx.Document(str(out))
        spaces = [int(b.get(qn("w:space")))
                  for p in doc.paragraphs
                  for pbdr in p._p.findall(qn("w:pPr") + "/" + qn("w:pBdr"))
                  for b in pbdr.findall(qn("w:bottom"))]
        assert spaces, "no section rules found in the docx"
        assert min(spaces) >= 2,             f"section rule sits {min(spaces)}pt under the heading — it will cut into it"
        # Word's 1.15 default line spacing is what made the old output look
        # padded with blank half-lines; every paragraph must pin it to single.
        assert doc.styles["Normal"].paragraph_format.line_spacing == 1.0
    print(f"ok: docx fills one page ({height:.0f}pt, {len(dropped)} cuts)")


def test_short_resume_is_not_padded_out():
    """A thin resume grows toward the page rather than being stretched past
    readable type, and never sprouts a second page."""
    from job_bot import resume_fit
    from job_bot.resume_models import (TailoredEducation, TailoredResume,
                                       TailoredRole)

    thin = TailoredResume(
        name="Test Candidate", contact_line="a@b.com | Somewhere, MD",
        education=[TailoredEducation(school="A University", degree="B.S.",
                                     graduation_date="May 2027")],
        experience=[TailoredRole(organization="Org", role="Analyst",
                                 dates="2025 - Present",
                                 bullets=["Did a thing that mattered."])],
        skills=["Excel"],
    )
    fitted, dropped = resume_fit.trim_to_fit(thin)
    assert not dropped, "nothing should be trimmed from a short resume"
    sizes = resume_fit.fit_sizes(fitted)
    assert sizes["_t"] == 1.0, "a short resume should open up to the max scale"
    assert sizes["body"][0] <= resume_fit.BODY_PT * 1.2,         "short resumes must not be blown up to absurd type to fill the page"
    print("ok: short resume opens up without overreaching")


def test_business_track_contract():
    """Guards the business-track rules in docs/resume_track_contract.md that a
    renderer change could silently break: no Summary, contract section order,
    uniform bullet counts, and body type inside the 10-11pt band."""
    loaded = _load()
    if not loaded:
        return
    profile, job = loaded
    from job_bot import resume_fit
    from job_bot.tailor import tailor_resume

    resume = tailor_resume(profile, job, use_llm=False)
    fitted, _ = resume_fit.trim_to_fit(resume)
    fitted.summary = None                      # what generate.py ships
    blocks, sizes = resume_fit.layout(fitted)

    heads = [b.text for b in blocks if b.kind == "head"]
    assert "SUMMARY" not in heads, "business track must not render a Summary"
    expected = ["EXPERIENCE", "LEADERSHIP & ACTIVITIES", "EDUCATION",
                "PROJECTS", "TECHNICAL SKILLS"]
    assert heads == [h for h in expected if h in heads],         f"section order violates the track contract: {heads}"

    for kind, entries in (("experience", fitted.experience),
                          ("leadership", fitted.leadership),
                          ("projects", fitted.projects)):
        counts = {len(e.bullets) for e in entries if e.bullets}
        assert len(counts) <= 1, f"{kind} bullet counts are ragged: {counts}"

    assert resume_fit.BODY_MIN_PT <= sizes["_body_pt"] <= resume_fit.BODY_MAX_PT,         f"body type {sizes['_body_pt']:.2f}pt is outside the contract's 10-11pt band"
    print(f"ok: business contract ({sizes['_body_pt']:.1f}pt, sections {heads})")


def test_skill_groups_survive_tailoring():
    """The master profile's skill categories must reach the page — flattening
    them buries the hard skills among the soft ones."""
    loaded = _load()
    if not loaded:
        return
    profile, job = loaded
    from job_bot.tailor import tailor_resume

    resume = tailor_resume(profile, job, use_llm=False)
    labels = [g.label for g in resume.skill_groups]
    assert labels, "skill groups were flattened away"
    assert len(set(labels)) == len(labels), f"duplicate skill group labels: {labels}"
    flat = {s for g in resume.skill_groups for s in g.skills}
    assert flat == set(resume.skills), "grouped skills differ from the flat list"
    print(f"ok: skill groups {labels}")


def test_renderer_for_field():
    """Field -> template mapping: tech fields render on the CS/tech (rendercv)
    template, business/audit fields keep the VMH docx template."""
    from job_bot.template_select import renderer_for_field
    assert renderer_for_field("Data & Analytics") == "rendercv"
    assert renderer_for_field("Software / Engineering") == "rendercv"
    assert renderer_for_field("Tax") == "docx"
    assert renderer_for_field("Audit & Assurance") == "docx"
    # IT Audit / Tech Risk is intentionally business/VMH by default.
    assert renderer_for_field("IT Audit / Tech Risk") == "docx"
    assert renderer_for_field("Other") == "docx"
    print("ok: renderer_for_field field->template mapping")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    test_tailor_and_docx()
    test_reportlab_pdf_one_page()
    test_docx_fills_one_page_with_clear_section_rules()
    test_short_resume_is_not_padded_out()
    test_business_track_contract()
    test_skill_groups_survive_tailoring()
    test_rendercv_pdf_one_page_and_parseable()
    test_renderer_for_field()
    print("\nall pipeline regression tests passed")
