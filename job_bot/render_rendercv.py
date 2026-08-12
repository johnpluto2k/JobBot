"""RenderCV renderer: TailoredResume -> RenderCV YAML -> typeset PDF.

Alternative to render_docx/render_pdf: the resume becomes a plain-text,
git-diffable `resume.yaml` (RenderCV's schema) rendered to a polished PDF by
the `rendercv` CLI. The same YAML opens in Overleaf via RenderCV's published
templates, so layout tweaks happen in a versioned text file, not Python
drawing code.

Theme: `engineeringresumes` — RenderCV's ATS-safe theme (single column, no
icons/graphics/tables in the text layer). If you switch themes, re-verify the
PDF's text extraction (`pdftotext`) still reads cleanly: some themes render
contact info as icon glyphs that ATS extractors can't parse.

Requires `pip install rendercv` (see requirements.txt). Callers should catch
exceptions and fall back to the reportlab renderer — generate.py does.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .resume_models import TailoredResume
from .writing_style import split_metrics

DEFAULT_THEME = "engineeringresumes"


def _bold_metrics_md(text: str) -> str:
    """Playbook: bold all metrics. RenderCV highlights accept markdown bold."""
    return "".join(f"**{c}**" if m else c for c, m in split_metrics(text))


# ----------------------------------------------------------------- contact line
def _parse_contact(contact_line: str) -> dict:
    """Split the resume's joined contact line back into RenderCV cv.* fields."""
    out: dict = {}
    for bit in (b.strip() for b in contact_line.split("•")):
        if not bit:
            continue
        low = bit.lower()
        if "@" in bit and "linkedin" not in low:
            out.setdefault("email", bit)
        elif "linkedin" in low:
            user = bit.rstrip("/").split("/")[-1]
            if user and "linkedin" not in user.lower():
                out.setdefault("social_networks", []).append(
                    {"network": "LinkedIn", "username": user})
        elif sum(c.isdigit() for c in bit) >= 7:
            digits = re.sub(r"\D", "", bit)
            if len(digits) == 10:          # RenderCV validates phones; use E.164
                out.setdefault("phone", f"+1{digits}")
            elif len(digits) == 11 and digits.startswith("1"):
                out.setdefault("phone", f"+{digits}")
        else:
            out.setdefault("location", bit)
    return out


# ------------------------------------------------------------------- sections
def _edu_entries(resume: TailoredResume) -> list[dict]:
    entries = []
    for e in resume.education:
        area = e.degree or "—"
        if e.secondary:
            area = f"{area} · {e.secondary}"
        highlights = []
        if e.gpa:
            highlights.append(f"GPA: {e.gpa}")
        if e.coursework:
            highlights.append("Coursework: " + ", ".join(e.coursework))
        entry = {"institution": e.school or "—", "area": area}
        if e.graduation_date:
            entry["date"] = str(e.graduation_date)   # free-text date field
        if highlights:
            entry["highlights"] = highlights
        entries.append(entry)
    return entries


def _role_entries(roles) -> list[dict]:
    entries = []
    for r in roles:
        entry = {"company": r.organization or "—", "position": r.role or "—"}
        if r.location:
            entry["location"] = r.location
        if r.dates:
            entry["date"] = r.dates                  # free-text date field
        if r.bullets:
            entry["highlights"] = [_bold_metrics_md(b) for b in r.bullets]
        entries.append(entry)
    return entries


def _project_entries(projects) -> list[dict]:
    entries = []
    for p in projects:
        entry = {"name": p.organization or p.role or "Project"}
        if p.bullets:
            entry["highlights"] = [_bold_metrics_md(b) for b in p.bullets]
        entries.append(entry)
    return entries


def resume_to_rendercv_dict(resume: TailoredResume,
                            theme: str = DEFAULT_THEME) -> dict:
    """Map a TailoredResume into RenderCV's input schema (as a plain dict)."""
    cv: dict = {"name": resume.name or "Candidate"}
    cv.update(_parse_contact(resume.contact_line or ""))

    sections: dict = {}
    if resume.summary:
        sections["summary"] = [resume.summary]       # TextEntry list
    if resume.education:
        sections["education"] = _edu_entries(resume)
    if resume.experience:
        sections["experience"] = _role_entries(resume.experience)
    if resume.leadership:
        sections["leadership"] = _role_entries(resume.leadership)
    if resume.projects:
        sections["projects"] = _project_entries(resume.projects)
    if resume.skills:
        sections["skills"] = [{"label": "Skills",
                               "details": ", ".join(resume.skills)}]
    if resume.certifications:
        sections["certifications"] = [{"label": "Certifications",
                                       "details": ", ".join(resume.certifications)}]
    cv["sections"] = sections

    # Compact design overrides so a full profile fits one page (the same
    # content volume the docx renderer fits): tight margins, no footer or
    # "last updated" note, slightly smaller body type, tighter section gaps.
    design = {
        "theme": theme,
        "page": {"top_margin": "0.4in", "bottom_margin": "0.4in",
                 "left_margin": "0.55in", "right_margin": "0.55in",
                 "show_footer": False, "show_top_note": False},
        "typography": {"line_spacing": "0.4em",
                       "font_size": {"body": "9pt", "name": "16pt"}},
        "section_titles": {"space_above": "0.25cm", "space_below": "0.12cm"},
        "sections": {"space_between_regular_entries": "0.5em"},
        "header": {"space_below_name": "0.25cm",
                   "space_below_connections": "0.25cm"},
    }
    return {"cv": cv, "design": design}


# -------------------------------------------------------------------- render
def write_rendercv_yaml(resume: TailoredResume, yaml_path: Path,
                        theme: str = DEFAULT_THEME) -> Path:
    """Write the RenderCV input file. JSON is a strict subset of YAML, so we
    emit JSON — valid input for RenderCV's YAML parser with no PyYAML dep."""
    data = resume_to_rendercv_dict(resume, theme=theme)
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    yaml_path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                         encoding="utf-8")
    return yaml_path


def render_rendercv(resume: TailoredResume, out_path: Path,
                    theme: str = DEFAULT_THEME) -> Path:
    """Render `out_path` (a .pdf) via the rendercv CLI. Also leaves the
    editable source at `<out_dir>/resume.yaml`. Raises RuntimeError with a
    clear message if rendercv is unavailable or the render fails."""
    out_path = Path(out_path)
    yaml_path = write_rendercv_yaml(resume, out_path.with_name("resume.yaml"),
                                    theme=theme)

    try:
        import rendercv  # noqa: F401
    except Exception:
        raise RuntimeError(
            "rendercv is not installed — `pip install rendercv` "
            "(then re-run with --renderer rendercv)")

    # rendercv's CLI prints ✓ marks that crash under Windows' cp1252 console
    # encoding when captured — force UTF-8 in the child process.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    with tempfile.TemporaryDirectory() as tmp:
        # --pdf-path is resolved relative to the input file (v2 CLI); the yaml
        # sits next to out_path, so the bare filename lands the PDF in app_dir.
        cmd = [sys.executable, "-m", "rendercv", "render", str(yaml_path),
               "--output-folder", tmp,
               "--pdf-path", out_path.name,
               "--dont-generate-markdown", "--dont-generate-html",
               "--dont-generate-png"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                              encoding="utf-8", errors="replace", env=env)
        if proc.returncode != 0:
            # Older/newer CLIs vary their flags — retry bare and copy the PDF out.
            proc = subprocess.run(
                [sys.executable, "-m", "rendercv", "render", str(yaml_path)],
                capture_output=True, text=True, timeout=300,
                encoding="utf-8", errors="replace", env=env,
                cwd=str(out_path.parent))
            if proc.returncode != 0:
                tail = (proc.stderr or proc.stdout or "").strip()[-400:]
                raise RuntimeError(f"rendercv render failed: {tail}")
            found = sorted(out_path.parent.glob("rendercv_output/*.pdf"))
            if not found:
                raise RuntimeError("rendercv succeeded but produced no PDF")
            shutil.copyfile(found[0], out_path)

        # Preserve the Typst intermediate (git-diffable source RenderCV used to
        # typeset the PDF) before `tmp` is cleaned up — otherwise it's silently
        # discarded even though rendercv already produced it. Best-effort: skip
        # silently if the CLI didn't leave a .typ behind.
        typs = sorted(Path(tmp).glob("*.typ"))
        if typs:
            shutil.copyfile(typs[0], out_path.with_suffix(".typ"))

    if not out_path.exists():
        raise RuntimeError("rendercv did not write the expected PDF")
    return out_path


def render_yaml_file(yaml_path: Path, out_dir: Path) -> dict:
    """Render an existing (possibly hand-edited) RenderCV YAML file.

    This is the Resume Studio entry point: the YAML is the source of truth
    (edited as text in the dashboard), and unlike ``render_rendercv`` the
    intermediate typesetting source is kept. RenderCV 2.x compiles via Typst,
    so that source is a ``.typ`` file — there is no LaTeX/.tex in v2.

    Returns ``{"yaml": Path, "pdf": Path, "typ": Path | None}``; raises
    RuntimeError with the CLI's tail output on failure.
    """
    yaml_path, out_dir = Path(yaml_path), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in list(out_dir.glob("*.pdf")) + list(out_dir.glob("*.typ")):
        old.unlink(missing_ok=True)   # don't let a stale render masquerade as this one

    try:
        import rendercv  # noqa: F401
    except Exception:
        raise RuntimeError("rendercv is not installed — `pip install rendercv`")

    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    cmd = [sys.executable, "-m", "rendercv", "render", str(yaml_path),
           "--output-folder", str(out_dir),
           "--dont-generate-markdown", "--dont-generate-html",
           "--dont-generate-png"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                          encoding="utf-8", errors="replace", env=env)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-600:]
        raise RuntimeError(f"rendercv render failed: {tail}")

    pdfs = sorted(out_dir.glob("*.pdf"))
    if not pdfs:
        raise RuntimeError("rendercv succeeded but produced no PDF")
    typs = sorted(out_dir.glob("*.typ"))
    return {"yaml": yaml_path, "pdf": pdfs[0], "typ": typs[0] if typs else None}
