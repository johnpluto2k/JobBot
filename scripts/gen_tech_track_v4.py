#!/usr/bin/env python3
"""Generate tech track resume v4 with custom section ordering.

Tech track order:
1. SKILLS (Python, SQL, Tableau, R, Node.js, React, FastAPI, SQLite)
2. PROJECTS (4+ bullets per project, architecture emphasized)
3. EDUCATION (UMD, 3.51 GPA, May 2027, expanded coursework)
4. EXPERIENCE (2 bullets max per role, technical emphasis)
5. CERTIFICATIONS

Usage:
    python scripts/gen_tech_track_v4.py
"""

from __future__ import annotations

import json
from pathlib import Path

from job_bot.resume_models import TailoredResume, TailoredRole, TailoredEducation
from job_bot.render_rendercv import (
    render_rendercv, write_rendercv_yaml, resume_to_rendercv_dict
)
from job_bot.writing_style import split_metrics


def load_master_profile(path: Path = None) -> dict:
    """Load master profile from JSON."""
    if path is None:
        path = Path("data/master_profile.json")
    return json.loads(path.read_text(encoding="utf-8"))


def _bold_metrics_md(text: str) -> str:
    """Bold all metrics in text using markdown."""
    return "".join(f"**{c}**" if m else c for c, m in split_metrics(text))


def _reorder_sections_for_tech_track(rendercv_dict: dict) -> dict:
    """Reorder sections in RenderCV dict for tech track: skills, projects, education, experience, certifications."""
    cv_sections = rendercv_dict.get("cv", {}).get("sections", {})

    # Tech track section order
    tech_order = ["skills", "projects", "education", "experience", "certifications"]

    # Build new sections dict in tech track order
    new_sections = {}
    for section_name in tech_order:
        if section_name in cv_sections:
            new_sections[section_name] = cv_sections[section_name]

    # Add any sections not in the tech order (leadership, summary, etc.)
    for section_name, content in cv_sections.items():
        if section_name not in new_sections:
            new_sections[section_name] = content

    # Update the dict in place
    rendercv_dict["cv"]["sections"] = new_sections
    return rendercv_dict


def build_tech_track_resume() -> TailoredResume:
    """Build tech track resume v4 from master profile."""
    profile = load_master_profile()

    # Personal info
    resume = TailoredResume(
        name=profile["personal"]["name"],
        contact_line=f"{profile['personal']['email']} • {profile['personal']['phone']} • "
                     f"{profile['personal']['location']} • {profile['personal']['linkedin']}",
        target_title="Data Analyst / Software Engineer (Tech Track)",
    )

    # ===== SKILLS (tech stack first, no duplicates) =====
    # Tech stack: Python, SQL, Tableau, R, Node.js, React, FastAPI, SQLite
    # Then supporting tools, then soft skills
    resume.skills = [
        "Python",
        "SQL",
        "Tableau",
        "R",
        "Node.js",
        "React",
        "FastAPI",
        "SQLite",
        "Plaid API",
        "PostgreSQL/Supabase",
        "Express.js",
        "JavaScript",
        "RenderCV/Typst",
        "Microsoft Excel",
        "Leadership",
        "Collaboration",
    ]

    # ===== PROJECTS (4+ bullets per project) =====
    resume.projects = []

    # Pathway
    pathway = profile["projects"][0]
    resume.projects.append(TailoredRole(
        role=pathway["name"],
        bullets=[
            _bold_metrics_md(pathway["bullets"][0]["text"]),  # 60+ modules, Claude API
            _bold_metrics_md(pathway["bullets"][1]["text"]),  # Dual-template, Gmail/Calendar MCP
            _bold_metrics_md(pathway["bullets"][2]["text"]),  # React + FastAPI dashboard, 13+ tabs
            _bold_metrics_md(pathway["bullets"][3]["text"]),  # Interview prep system
        ]
    ))

    # PersonalFinanceOS
    pfo = profile["projects"][1]
    resume.projects.append(TailoredRole(
        role=pfo["name"],
        bullets=[
            _bold_metrics_md(pfo["bullets"][0]["text"]),  # Zero-dependency Node.js, Plaid
            _bold_metrics_md(pfo["bullets"][1]["text"]),  # Transaction categorization, 50+ categories
            _bold_metrics_md(pfo["bullets"][2]["text"]),  # Net-worth tracking, SVG/canvas, CSV export
        ]
    ))

    # Pantry Plate
    pp = profile["projects"][2]
    resume.projects.append(TailoredRole(
        role=pp["name"],
        bullets=[
            _bold_metrics_md(pp["bullets"][0]["text"]),  # Food waste reduction
            _bold_metrics_md(pp["bullets"][1]["text"]),  # Node.js/Express backend, 5 REST endpoints
            _bold_metrics_md(pp["bullets"][2]["text"]),  # Supabase persistence, secrets, Spoonacular API
            _bold_metrics_md(pp["bullets"][3]["text"]),  # Interactive UI, Swiper, Chart.js
        ]
    ))

    # ===== EDUCATION (UMD, 3.51 GPA, May 2027, expanded coursework) =====
    edu = profile["education"][0]

    # Filter coursework to highlight programming/database/architecture (tech-focused, 8-10 courses)
    highlight_coursework = [
        "Object-Oriented Programming I",
        "Object-Oriented Programming for Information Science",
        "Database Design and Modeling",
        "Dynamic Web Applications",
        "Introduction to Computer Programming via the Web",
        "Introduction to Information Systems",
        "Technology Infrastructure & Architecture",
        "Statistics for Information Science",
    ]

    resume.education.append(TailoredEducation(
        school=edu["school"],
        degree=edu["degree"],
        secondary=edu["secondary_major"],
        gpa=edu["gpa"],
        graduation_date=edu["graduation_date"],
        coursework=highlight_coursework,
    ))

    # ===== EXPERIENCE (2 bullets max per role, technical emphasis) =====
    resume.experience = []

    # Scion: technical focus on CRM/data
    scion = profile["experience"][0]
    resume.experience.append(TailoredRole(
        role=scion["role"],
        organization=scion["organization"],
        dates="August 2025 – Present",
        bullets=[
            _bold_metrics_md(scion["bullets"][0]["text"]),  # Uses CRM reporting...18% accuracy
            _bold_metrics_md(scion["bullets"][1]["text"]),  # Manages compliance...800+ tenants
        ]
    ))

    # UMD TA: technical emphasis on dashboards
    ta = profile["experience"][1]
    resume.experience.append(TailoredRole(
        role=ta["role"],
        organization=ta["organization"],
        dates="August 2024 – May 2025",
        bullets=[
            _bold_metrics_md(ta["bullets"][0]["text"]),  # Supported faculty...dashboards
            _bold_metrics_md(ta["bullets"][1]["text"]),  # Increased satisfaction...15%
        ]
    ))

    # Kim's: 2 strongest bullets
    kims = profile["experience"][2]
    resume.experience.append(TailoredRole(
        role=kims["role"],
        organization=kims["organization"],
        dates="June 2017 – August 2025",
        bullets=[
            _bold_metrics_md(kims["bullets"][0]["text"]),  # $380K budget, $25K savings
            _bold_metrics_md(kims["bullets"][1]["text"]),  # Inventory tracking...12% waste reduction
        ]
    ))

    # ===== CERTIFICATIONS =====
    resume.certifications = profile["certifications"]

    return resume


def write_tech_track_yaml(resume: TailoredResume, yaml_path: Path) -> Path:
    """Write RenderCV YAML with tech track section ordering."""
    data = resume_to_rendercv_dict(resume, theme="engineeringresumes")
    data = _reorder_sections_for_tech_track(data)
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    yaml_path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                         encoding="utf-8")
    return yaml_path


def render_tech_track_v4():
    """Render the tech track resume to PDF."""
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    print("Building tech track resume v4...")
    resume = build_tech_track_resume()

    out_path = Path("data/outputs/resume_tech_analyst_v4.pdf")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"  Name: {resume.name}")
    print(f"  Skills: {len(resume.skills)} items")
    print(f"  Projects: {len(resume.projects)} projects")
    print(f"  Education: {len(resume.education)} entries")
    print(f"  Experience: {len(resume.experience)} roles")
    print(f"  Certifications: {len(resume.certifications)} certs")

    # Write YAML source with tech track section order
    yaml_path = out_path.with_name("resume_tech_v4.yaml")
    write_tech_track_yaml(resume, yaml_path)
    print(f"\n  Source YAML: {yaml_path}")

    # Render via RenderCV
    print(f"  Rendering via RenderCV (theme: engineeringresumes)...")
    try:
        import rendercv
    except ImportError:
        print("ERROR: rendercv not installed. Run: pip install rendercv")
        raise

    # Use same approach as render_rendercv: temporary output folder
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [sys.executable, "-m", "rendercv", "render", str(yaml_path),
               "--output-folder", tmp,
               "--pdf-path", out_path.name,
               "--dont-generate-markdown", "--dont-generate-html",
               "--dont-generate-png"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                              encoding="utf-8", errors="replace", env=env)
        if proc.returncode != 0:
            # Try alternative approach
            proc = subprocess.run(
                [sys.executable, "-m", "rendercv", "render", str(yaml_path)],
                capture_output=True, text=True, timeout=300,
                encoding="utf-8", errors="replace", env=env,
                cwd=str(out_path.parent))
            if proc.returncode != 0:
                tail = (proc.stderr or proc.stdout or "").strip()[-400:]
                raise RuntimeError(f"rendercv render failed: {tail}")
            found = sorted(out_path.parent.glob("rendercv_output/*.pdf"))
            if found:
                shutil.copyfile(found[0], out_path)
        else:
            # PDF should be in tmp folder
            pdf_in_tmp = Path(tmp) / out_path.name
            if pdf_in_tmp.exists():
                shutil.copyfile(pdf_in_tmp, out_path)

    if not out_path.exists():
        raise RuntimeError("rendercv did not write the expected PDF")

    print(f"\nGenerated: {out_path}")
    print(f"  Source YAML: {yaml_path}")
    print(f"  Total pages: ~1 (9-10pt body)")
    return out_path


if __name__ == "__main__":
    render_tech_track_v4()
