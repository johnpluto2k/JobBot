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
import re
import sys
from pathlib import Path

from . import config
from .ats_engine import load_profile, profile_text, score
from .cover_letter import cover_letter_to_docx, generate_cover_letter
from .jd_parser import parse_jd
from .render_docx import render_docx
from .render_pdf import render_pdf
from .tailor import resume_to_text, tailor_resume


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


def _checklist(job, app_dir: Path, before: float, after: float) -> str:
    return f"""# Application checklist — {job.title or 'role'} @ {job.company or ''}

- [ ] Review tailored resume: `{app_dir / 'resume.pdf'}`
- [ ] Review cover letter: `{app_dir / 'cover_letter.docx'}`
- [ ] Confirm one-page length and no typos
- [ ] ATS match: {before:.0f} → {after:.0f} after tailoring{' ✅' if after >= before else ''}
- [ ] Verify required keywords are genuinely supported (never fabricate)
- [ ] Detected ATS: {job.ats_platform} — format accordingly
- [ ] Run `python -m job_bot.decide --file <jd>` for the network/cold-apply call
- [ ] Submit on {job.ats_platform or 'the company portal'} / save confirmation
- [ ] Set a 5–7 day follow-up reminder
"""


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
    ap.add_argument("--renderer", choices=["docx", "rendercv"], default="docx",
                    help="PDF pipeline: docx=reportlab (default), rendercv=YAML->LaTeX "
                         "(git-diffable resume.yaml, Overleaf-compatible)")
    ap.add_argument("--out", type=Path, help="Output directory (default data/applications/<slug>)")
    args = ap.parse_args()

    jd_text = _read_jd(args)
    profile = load_profile(args.profile)
    use_llm = False if args.no_llm else None

    job = parse_jd(jd_text, url=args.url, use_llm=use_llm)
    if args.company:
        job.company = args.company

    # before: master profile vs JD
    before = score(job, profile).overall_score

    print(f"Tailoring resume for: {job.title or 'role'} @ {job.company or '—'} "
          f"(ATS: {job.ats_platform})")
    resume = tailor_resume(profile, job, use_llm=use_llm)

    # after: tailored resume text vs JD (re-score using a profile-shaped view)
    tailored_profile = _resume_as_profile(resume, profile)
    after = score(job, tailored_profile).overall_score

    slug = f"{_slug(job.company)}_{_slug(job.title)}".strip("_") or "application"
    app_dir = Path(args.out) if args.out else config.OUTPUT_DIR / "applications" / slug
    app_dir.mkdir(parents=True, exist_ok=True)

    docx_path = render_docx(resume, app_dir / "resume.docx")
    pdf_path = None
    if args.renderer == "rendercv":
        try:
            from .render_rendercv import render_rendercv
            pdf_path = render_rendercv(resume, app_dir / "resume.pdf")
            print(f"  · rendered via RenderCV (source: {app_dir / 'resume.yaml'})")
        except Exception as exc:
            print(f"  ! RenderCV render failed ({exc}); falling back to reportlab PDF")
    if pdf_path is None:
        try:
            pdf_path = render_pdf(resume, app_dir / "resume.pdf")
        except Exception as exc:
            print(f"  ! PDF render failed ({exc}); DOCX still produced")

    letter = generate_cover_letter(profile, job, use_llm=use_llm)
    (app_dir / "cover_letter.txt").write_text(letter, encoding="utf-8")
    cover_letter_to_docx(letter, app_dir / "cover_letter.docx")

    (app_dir / "checklist.md").write_text(_checklist(job, app_dir, before, after), encoding="utf-8")

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


def _resume_as_profile(resume, base_profile: dict) -> dict:
    """Shape a tailored resume back into the profile dict structure so the ATS
    engine can re-score it (keyword presence + quantification)."""
    def roles(group):
        return [{
            "role": r.role, "organization": r.organization,
            "bullets": [{"text": b, "quantified": bool(re.search(r"[%$]|\d{2,}", b)),
                         "keyword_tags": []} for b in r.bullets],
        } for r in group]

    return {
        "personal": base_profile.get("personal", {}),
        "education": base_profile.get("education", []),
        "experience": roles(resume.experience),
        "leadership": roles(resume.leadership),
        "projects": [{"name": p.organization, "description": "",
                      "technologies": [], "bullets": [{"text": b} for b in p.bullets]}
                     for p in resume.projects],
        "skills": [{"category": "all", "skills": resume.skills}],
        "certifications": resume.certifications,
        "targets": base_profile.get("targets", {}),
    }


if __name__ == "__main__":
    main()
