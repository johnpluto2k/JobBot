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
    test_rendercv_pdf_one_page_and_parseable()
    test_renderer_for_field()
    print("\nall pipeline regression tests passed")
