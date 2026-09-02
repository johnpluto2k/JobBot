"""Phase 4 CLI: generate a tailored application package for a job.

Produces, under data/applications/<company>_<role>/:
  - resume.docx + resume.pdf   (ATS-clean, one page, selected/reordered bullets)
  - cover_letter.docx + .txt
  - checklist.md               (application to-dos)
  - before/after ATS score so you can see the lift from tailoring.

Usage:
    python -m job_bot.generate --file jd.txt
    python -m job_bot.generate --file jd.txt --url https://... --no-llm
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import config
from .applications import classify_field
from .ats_engine import load_profile, profile_text, score
from .cover_letter import cover_letter_to_docx, generate_cover_letter
from .jd_parser import parse_jd
from .render_docx import render_docx
from .render_pdf import render_pdf
from .tailor import resume_to_text, tailor_resume
from .template_select import renderer_for_field


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "job").lower()).strip("-")[:50] or "job"


def _read_jd(args) -> str:
    if args.file:
        return Path(args.file).read_text(encoding="utf-8", errors="replace")
    if args.text:
        return args.text
    if not sys.stdin.isatty():
        data = sys.stdin.read()
        if data.strip():
            return data
    raise SystemExit("Provide a JD via --file PATH, --text \"...\", or piped stdin.")


# docs/resume_track_contract.md, Acceptance Criteria. A tick mark next to a
# score that misses the gate is the generator lying to itself, so the checklist
# reports against the gate rather than against "better than before".
ATS_GATE = 85.0


def _ats_verdict(after: float) -> str:
    if after >= ATS_GATE:
        return f"✅ meets the {ATS_GATE:.0f} gate"
    return f"❌ BELOW the {ATS_GATE:.0f} gate (short by {ATS_GATE - after:.0f})"


def _checklist(job, app_dir: Path, before: float, after: float) -> str:
    return f"""# Application checklist — {job.title or 'role'} @ {job.company or ''}

- [ ] Review + SUBMIT this file: `{app_dir / 'resume.docx'}`  (business track ships .docx)
- [ ] `resume.pdf` is a preview only — it is a separate render and will not line-break identically
- [ ] Review cover letter: `{app_dir / 'cover_letter.docx'}`
- [ ] Confirm one-page length and no typos
- [ ] ATS match: {before:.0f} → {after:.0f} after tailoring — {_ats_verdict(after)}
- [ ] Verify required keywords are genuinely supported (never fabricate)
- [ ] Detected ATS: {job.ats_platform} — format accordingly
- [ ] Run `python -m job_bot.decide --file <jd>` for the network/cold-apply call
- [ ] Submit on {job.ats_platform or 'the company portal'} / save confirmation
- [ ] Set a 5–7 day follow-up reminder
"""


def run_generate(jd_text: str, *, url: str | None = None,
                  company_override: str | None = None,
                  title_override: str | None = None,
                  profile_path: Path | None = None,
                  use_llm: bool | None = None,
                  renderer: str | None = None,
                  out_dir: Path | None = None) -> dict:
    """Core Phase-4 pipeline: parse -> score(before) -> tailor -> score(after)
    -> render -> save application folder. Used by both the CLI and the API —
    do not duplicate this logic anywhere else."""
    try:
        # The print statements below use non-ASCII characters (e.g. '->' as
        # a real arrow). stdout defaults to cp1252 on Windows outside a real
        # console (e.g. uvicorn's redirected stdout), which can't encode
        # them — reconfigure defensively here too, not just in main(), since
        # this function is also called directly from the API process.
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    profile = load_profile(profile_path)

    job = parse_jd(jd_text, url=url, use_llm=use_llm)
    if company_override:
        job.company = company_override
    if title_override:
        job.title = title_override

    # Template auto-selection: the JD's career field picks the résumé format
    # (tech fields -> RenderCV/CS template, everything else -> docx/VMH). An
    # explicit renderer always wins over the auto-pick.
    field = classify_field(job.title or "", job.raw_text or "")
    chosen_renderer = renderer or renderer_for_field(field)

    # before: master profile vs JD
    before_report = score(job, profile)
    before = before_report.overall_score

    print(f"Tailoring resume for: {job.title or 'role'} @ {job.company or '—'} "
          f"(ATS: {job.ats_platform})")
    print(f"  · field: {field} -> renderer: {chosen_renderer}"
          + ("  (via --renderer)" if renderer else "  (auto)"))
    resume = tailor_resume(profile, job, use_llm=use_llm)

    # Fit to one page ONCE, here, and score that. The renderers used to do their
    # own trimming after the score was computed, so the printed "after" number
    # described a fuller resume than the one in the folder. Whatever we score
    # has to be exactly what ships.
    from . import resume_fit
    shipped, trimmed = resume_fit.trim_to_fit(resume)
    if chosen_renderer != "rendercv":
        # The business/VMH template has no Summary section (see
        # docs/resume_track_contract.md), so the scored view must not have one
        # either — crediting a paragraph that isn't on the page is how a score
        # stops meaning anything.
        shipped.summary = None

    # after: shipped resume text vs JD (re-score using a profile-shaped view)
    tailored_profile = _resume_as_profile(shipped, profile)
    after_report = score(job, tailored_profile)
    after = after_report.overall_score

    slug = f"{_slug(job.company)}_{_slug(job.title)}".strip("_") or "application"
    app_dir = Path(out_dir) if out_dir else config.OUTPUT_DIR / "applications" / slug
    app_dir.mkdir(parents=True, exist_ok=True)

    docx_path = render_docx(shipped, app_dir / "resume.docx", prefitted=True)
    pdf_path = None
    if chosen_renderer == "rendercv":
        try:
            from .render_rendercv import render_rendercv
            pdf_path = render_rendercv(shipped, app_dir / "resume.pdf")
            print(f"  · rendered via RenderCV (source: {app_dir / 'resume.yaml'})")
        except Exception as exc:
            print(f"  ! RenderCV render failed ({exc}); falling back to reportlab PDF")
    if pdf_path is None:
        try:
            pdf_path = render_pdf(shipped, app_dir / "resume.pdf", prefitted=True)
        except Exception as exc:
            print(f"  ! PDF render failed ({exc}); DOCX still produced")

    letter = generate_cover_letter(profile, job, use_llm=use_llm)
    (app_dir / "cover_letter.txt").write_text(letter, encoding="utf-8")
    cover_letter_to_docx(letter, app_dir / "cover_letter.docx")

    (app_dir / "checklist.md").write_text(_checklist(job, app_dir, before, after), encoding="utf-8")
    # Record why this application used the template it did, so Resume Studio can
    # read the field/renderer decision back instead of only the CLI seeing it.
    (app_dir / "meta.json").write_text(
        json.dumps({"field": field, "renderer": chosen_renderer}, indent=2), encoding="utf-8")

    print("\n=== Application package generated ===")
    print(f"  dir          : {app_dir}")
    print(f"  resume       : {docx_path.name}" + (f" + {pdf_path.name}" if pdf_path else ""))
    print(f"  cover letter : cover_letter.docx + .txt")
    print(f"  checklist    : checklist.md")
    print(f"  ATS match    : {before:.1f} → {after:.1f}  "
          f"({'+' if after >= before else ''}{after - before:.1f})")
    print(f"  experience   : {len(resume.experience)} roles, "
          f"{sum(len(r.bullets) for r in resume.experience)} bullets selected")
    print(f"  skills order : {', '.join(resume.skills[:8])}{'…' if len(resume.skills) > 8 else ''}")
    if trimmed:
        print(f"  trimmed to fit one page ({len(trimmed)} cuts, weakest first):")
        for item in trimmed:
            print(f"     - {item}")

    return {
        "job": job,
        "field": field,
        "renderer": chosen_renderer,
        "before": before,
        "after": after,
        "before_report": before_report,
        "after_report": after_report,
        "resume": shipped,
        "app_dir": app_dir,
        "slug": slug,
        "docx_path": docx_path,
        "pdf_path": pdf_path,
        "trimmed": trimmed,
    }


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Generate a tailored application (Phase 4).")
    ap.add_argument("--file", type=Path, help="JD text file")
    ap.add_argument("--text", help="JD text inline")
    ap.add_argument("--url", help="Job posting URL")
    ap.add_argument("--company", help="Override company name")
    ap.add_argument("--profile", type=Path, help="Path to master_profile.json")
    ap.add_argument("--no-llm", action="store_true", help="Force heuristic (no Claude rewrite)")
    ap.add_argument("--renderer", choices=["docx", "rendercv"], default=None,
                    help="PDF pipeline: docx=reportlab (VMH/business template), "
                         "rendercv=RenderCV/Typst (CS/tech template, git-diffable "
                         "resume.yaml). Default: auto-picked from the JD's career "
                         "field (tech fields -> rendercv, else docx).")
    ap.add_argument("--out", type=Path, help="Output directory (default data/applications/<slug>)")
    args = ap.parse_args()

    jd_text = _read_jd(args)
    run_generate(
        jd_text, url=args.url, company_override=args.company,
        profile_path=args.profile, use_llm=(False if args.no_llm else None),
        renderer=args.renderer, out_dir=args.out,
    )


def _resume_as_profile(resume, base_profile: dict) -> dict:
    """Shape a tailored resume back into the profile dict structure so the ATS
    engine can re-score it (keyword presence + quantification).

    The `quantified` flag matters: it is 15% of the score. The master profile
    computes it with richer logic than a regex (see `extract.py`), so carry the
    stored value through wherever the bullet text still matches, and fall back
    to a regex only for LLM-rewritten text. Project bullets used to omit the key
    entirely, which counted every one of them as unquantified and was single-
    handedly responsible for tailoring *lowering* the score."""
    stored = _quantified_index(base_profile)

    def quantified(text: str) -> bool:
        hit = stored.get(_norm_bullet(text))
        if hit is not None:
            return hit
        # "6+ company types" is a metric; the old r"\d{2,}" missed every
        # single-digit one.
        return bool(re.search(r"[%$]|\d", text))

    def bullets(items):
        return [{"text": b, "quantified": quantified(b), "keyword_tags": []}
                for b in items]

    def roles(group):
        return [{
            "role": r.role, "organization": r.organization,
            "bullets": bullets(r.bullets),
        } for r in group]

    src_projects = {(p.get("name") or ""): p for p in base_profile.get("projects", [])}

    def project(p):
        # `organization` is "<name> — <tech, tech, ...>"; recover the source
        # entry so description/technologies survive the round-trip.
        name = (p.organization or "").split(" — ")[0]
        src = src_projects.get(name, {})
        return {"name": name or p.organization,
                "description": src.get("description", ""),
                "technologies": src.get("technologies", []),
                "bullets": bullets(p.bullets)}

    return {
        "personal": base_profile.get("personal", {}),
        # Education comes off the *shipped* resume, not the master profile:
        # coursework gets trimmed to fit the page and the score should only
        # credit what a reader can actually see.
        "education": [{"school": e.school, "degree": e.degree,
                       "gpa": e.gpa, "graduation_date": e.graduation_date,
                       "relevant_coursework": list(e.coursework)}
                      for e in resume.education],
        "summary": resume.summary or "",
        "experience": roles(resume.experience),
        "leadership": roles(resume.leadership),
        "projects": [project(p) for p in resume.projects],
        "skills": ([{"category": g.label, "skills": g.skills}
                    for g in resume.skill_groups]
                   or [{"category": "all", "skills": resume.skills}]),
        "certifications": resume.certifications,
        "targets": base_profile.get("targets", {}),
    }


def _norm_bullet(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _quantified_index(profile: dict) -> dict:
    """text -> stored `quantified` flag, for every bullet in the master profile."""
    out: dict[str, bool] = {}
    for key in ("experience", "leadership", "projects"):
        for entry in profile.get(key, []):
            for b in entry.get("bullets", []):
                if isinstance(b, dict) and b.get("text"):
                    out[_norm_bullet(b["text"])] = bool(b.get("quantified"))
    return out


if __name__ == "__main__":
    main()
