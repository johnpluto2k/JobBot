"""FastAPI read layer for the React dashboard.

A thin JSON facade over the same SQLite store and reconciliation logic the
Streamlit dashboard uses — so every number the React app shows is computed from
the *same* source of truth (``applications.summary`` / ``build_applications``),
never a second, drifting copy.

Run (from the project root)::

    uvicorn job_bot.api:app --reload --port 8000
    (or)  python -m job_bot.api

The Vite dev server (http://localhost:5173) talks to this over CORS. In
production you'd serve the built ``web/dist`` behind the same origin and drop
the CORS allowance.
"""

from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import applications, config
from .db import DB_PATH, connect

app = FastAPI(title="Job Bot API", version="1.0.0")

# The Vite dev server origins. Loosened here for local dev; tighten for deploy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)


def _avatar_data_uri() -> str | None:
    """Inline the profile photo as a data URI (mirrors the Streamlit resolver)."""
    for ext in ("png", "jpg", "jpeg", "webp"):
        path = config.OUTPUT_DIR / f"profile_photo.{ext}"
        if path.is_file():
            mime = mimetypes.guess_type(str(path))[0] or "image/jpeg"
            data = base64.b64encode(path.read_bytes()).decode("ascii")
            return f"data:{mime};base64,{data}"
    return None


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "db": DB_PATH.exists()}


@app.get("/api/profile")
def profile() -> dict:
    """Header identity: name, contact, location, avatar."""
    if not config.PROFILE_JSON.exists():
        return {"found": False}
    data = json.loads(config.PROFILE_JSON.read_text(encoding="utf-8"))
    p = data.get("personal", {})
    return {
        "found": True,
        "name": p.get("name"),
        "email": p.get("email"),
        "location": p.get("location"),
        "headline": p.get("headline") or p.get("title"),
        "avatar": _avatar_data_uri(),
    }


@app.get("/api/summary")
def summary() -> dict:
    """Reconciled funnel counts, rates, and field mix (single source of truth)."""
    if not DB_PATH.exists():
        return {"total": 0, "by_status": {}, "by_field": {}}
    s = applications.summary()
    # Attach human labels so the client doesn't hard-code the status vocabulary.
    s["status_labels"] = applications.STATUS_LABEL
    return s


@app.get("/api/applications")
def applications_list() -> list[dict]:
    """One reconciled record per company applied to (for the applications table)."""
    if not DB_PATH.exists():
        return []
    apps = applications.build_applications()
    labels = applications.STATUS_LABEL
    for a in apps:
        a["status_label"] = labels.get(a["status"], a["status"])
    return apps


@app.get("/api/jobs")
def jobs(status: str | None = None, limit: int = 100) -> list[dict]:
    """Live job pipeline (scraped/scored postings), ranked by priority."""
    if not DB_PATH.exists():
        return []
    con = connect()
    try:
        where, params = "", []
        if status:
            where = "WHERE status = ?"
            params.append(status)
        rows = con.execute(
            f"""SELECT id, title, company, location, site, url, date_posted,
                       market_tier, tier_num, ats_score, priority, status,
                       legit_score, legit_grade, recommendation, seniority
                FROM jobs {where}
                ORDER BY (priority IS NULL), priority DESC, ats_score DESC
                LIMIT ?""",
            (*params, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


@app.get("/api/overview")
def overview() -> dict:
    """Full profile detail for the Overview section: education, skills grouped
    by category, experience headlines, targets, certifications, summary."""
    if not config.PROFILE_JSON.exists():
        return {"found": False}
    d = json.loads(config.PROFILE_JSON.read_text(encoding="utf-8"))
    edu = d.get("education", [])
    exp = d.get("experience", [])
    return {
        "found": True,
        "summary": d.get("summary"),
        "education": edu,
        "skills": d.get("skills", []),
        "targets": d.get("targets", []),
        "certifications": d.get("certifications", []),
        "experience": [
            {
                "role": e.get("role"),
                "organization": e.get("organization"),
                "location": e.get("location"),
                "start_date": e.get("start_date"),
                "end_date": e.get("end_date"),
                "is_current": e.get("is_current"),
                "bullets": e.get("bullets", []),
            }
            for e in exp
        ],
    }


@app.get("/api/network")
def network() -> dict:
    """Company-by-company network coverage + gaps (network_map.build_map)."""
    if not DB_PATH.exists():
        return {"covered": [], "gaps": [], "total_contacts": 0, "companies_with_contacts": 0}
    from .network_map import build_map

    return build_map()


@app.get("/api/offers")
def offers(money: float = 0.5, growth: float = 0.25, fit: float = 0.25) -> dict:
    """COL-adjusted offer comparison under the given priority weights."""
    if not DB_PATH.exists():
        return {"offers": [], "winner": None, "insights": [], "weights": {}}
    from .offers import compare

    return compare({"money": money, "growth": growth, "fit": fit})


@app.get("/api/growth")
def growth() -> dict:
    """Prioritized growth plan (certs, projects, résumé variants, insights)."""
    if not config.PROFILE_JSON.exists():
        return {"per_field": [], "insights": [], "top_actions": []}
    from .growth import build_plan

    return build_plan()


@app.get("/api/decisions")
def decisions(limit: int = 50) -> list[dict]:
    """Logged network-vs-cold decisions (from the Score-a-JD tool)."""
    if not DB_PATH.exists():
        return []
    con = connect()
    try:
        rows = con.execute(
            """SELECT id, company, title, verdict, ats_score, competition, connection, created_at
               FROM decisions ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


class ScoreRequest(BaseModel):
    jd: str
    url: str | None = None
    company: str | None = None


@app.post("/api/score")
def score_jd(req: ScoreRequest) -> dict:
    """Run the live ATS + network decision on a pasted JD (Phases 2–3).

    Mirrors the Streamlit 'Score a JD' tool: parse → ATS score → connection
    match → network-vs-cold verdict. Logs the decision like the CLI does.
    """
    from .ats_engine import score as ats_score
    from .connections import matches_for_company
    from .decision_engine import decide
    from .jd_parser import parse_jd

    profile_data = (
        json.loads(config.PROFILE_JSON.read_text(encoding="utf-8"))
        if config.PROFILE_JSON.exists()
        else {}
    )
    job = parse_jd(req.jd, url=req.url or None, use_llm=config.has_llm())
    if req.company:
        job.company = req.company
    report = ats_score(job, profile_data)

    con = connect()
    try:
        matches = matches_for_company(con, job.company)
    finally:
        con.close()
    decision = decide(job, report.overall_score, matches)

    return {
        "job": {
            "title": job.title,
            "company": job.company,
            "market_tier": job.market_tier,
            "role_type": getattr(job, "role_type", None),
        },
        "ats": {
            "overall_score": round(report.overall_score, 1),
            "platform": report.ats_platform,
            "matched": [h.keyword for h in report.matched_keywords],
            "missing_required": [
                h.keyword for h in report.missing_keywords if h.importance == "required"
            ],
            "gap_analysis": [
                {
                    "keyword": g.keyword,
                    "importance": g.importance,
                    "impact": round(g.impact * 100, 1),
                    "action": g.action,
                }
                for g in report.gap_analysis[:8]
            ],
        },
        "decision": {
            "verdict": decision.verdict_label,
            "verdict_short": decision.verdict_label.split("—")[0].strip(),
            "rationale": decision.rationale,
            "actions": decision.recommended_actions,
            "matches": [
                {"name": m.name, "relationship": getattr(m, "relationship", None),
                 "warmth": getattr(m, "warmth", None)}
                for m in matches[:5]
            ],
        },
    }


@app.get("/api/cycles")
def cycles() -> dict:
    """Hiring cycles (derived from the profile's grad date) + career tracks,
    for the Find Jobs form."""
    from . import newgrad

    profile_data = (
        json.loads(config.PROFILE_JSON.read_text(encoding="utf-8"))
        if config.PROFILE_JSON.exists()
        else {}
    )
    edu = (profile_data.get("education") or [{}])[0]
    grad = newgrad.parse_grad_date(edu.get("graduation_date") or "May 2027")
    return {
        "graduation_date": grad.strftime("%B %Y"),
        "cycles": newgrad.available_cycles(grad),
        "tracks": list(newgrad.TRACKS.keys()),
        "default_tracks": newgrad.DEFAULT_TRACKS,
        "sites": ["indeed", "linkedin", "glassdoor", "google", "zip_recruiter"],
        "default_sites": ["indeed"],
    }


class SearchRequest(BaseModel):
    tracks: list[str]
    kind: str = "internship"  # internship | fulltime
    location: str = "Washington, DC"
    remote: bool = True
    results_per: int = 10
    hours_old: int = 168
    # Indeed-only by default (it tolerates JobSpy well); LinkedIn throttles
    # per-IP quickly, so the UI makes it deliberate opt-in — same guidance as
    # the Streamlit tab.
    sites: list[str] = ["indeed"]


@app.post("/api/search")
def search_jobs(req: SearchRequest) -> dict:
    """Run a live job-board search for the chosen tracks + cycle, score/route,
    and persist. Slow (scrapes boards) and may be rate-limited — same behavior
    as the Streamlit 'Search job boards' button."""
    from . import newgrad
    from .applications import classify_field

    queries = newgrad.build_track_queries(
        req.tracks, req.kind, remote_internships=req.remote
    )
    res = newgrad.run(
        location=req.location,
        hours_old=req.hours_old,
        results_per=min(req.results_per, 50),
        sites=req.sites or ["indeed"],
        queries=queries,
    )
    scored = res.get("scored", [])
    for r in scored:
        r["field"] = classify_field(r.get("title") or "")
    # On-target = a classified field other than 'Other'.
    on_target = [r for r in scored if r.get("field") != "Other"]
    return {
        "scraped": res.get("scraped", 0),
        "saved": res.get("saved", 0),
        "per_query": res.get("per_query", []),
        "on_target": sorted(on_target, key=lambda x: x.get("priority") or 0, reverse=True),
        "n_on_target": len(on_target),
        "n_total": len(scored),
    }


# --- Resume Studio ------------------------------------------------------------
# The resume-as-code flow: the RenderCV YAML is the editable source of truth,
# typeset via RenderCV 2.x (Typst — no LaTeX/.tex exists in v2, so no Overleaf).

def _studio_build_resume():
    """TailoredResume straight from the master profile (no target JD)."""
    from .ats_engine import load_profile
    from .jd_parser import parse_jd
    from .tailor import tailor_resume

    prof = load_profile(None)
    targets = (prof.get("targets") or {}).get("target_roles") or ["Analyst"]
    skills = ", ".join(s for g in prof.get("skills", []) for s in g.get("skills", []))
    jd = parse_jd(f"{targets[0]}. Skills: {skills}", use_llm=False)
    return tailor_resume(prof, jd, use_llm=False), prof


PROFILE_SOURCE = "profile"


def _studio_field_and_renderer(source: str) -> tuple[str, str]:
    """(career field, suggested renderer) for a studio source. Reads an
    application folder's meta.json when present; otherwise classifies the first
    target role from the master profile."""
    from .applications import classify_field
    from .ats_engine import load_profile
    from .template_select import renderer_for_field

    if source != PROFILE_SOURCE:
        meta = config.OUTPUT_DIR / "applications" / source / "meta.json"
        if meta.is_file():
            try:
                m = json.loads(meta.read_text(encoding="utf-8"))
                field = m.get("field")
                renderer = m.get("renderer")
                if field and renderer in ("rendercv", "docx"):
                    return field, renderer
                if field:
                    return field, renderer_for_field(field)
            except Exception:
                pass
    prof = load_profile(None)
    targets = (prof.get("targets") or {}).get("target_roles") or ["Analyst"]
    field = classify_field(targets[0])
    return field, renderer_for_field(field)


@app.get("/api/resume-studio/sources")
def studio_sources() -> dict:
    """Places a studio session can start from: the master profile, or any
    application folder whose generate run wrote an editable resume.yaml."""
    apps_root = config.OUTPUT_DIR / "applications"
    slugs = sorted(p.parent.name for p in apps_root.glob("*/resume.yaml")) \
        if apps_root.exists() else []
    return {
        "sources": [{"key": PROFILE_SOURCE,
                     "label": "Master profile (no target JD)"}]
                   + [{"key": s, "label": s} for s in slugs],
    }


@app.get("/api/resume-studio/yaml")
def studio_yaml(source: str = PROFILE_SOURCE) -> dict:
    """The starting RenderCV YAML for a source (JSON text — valid YAML), plus the
    classified career `field` and `suggested_renderer` so the UI can default its
    template control to match the application's field."""
    try:
        field, suggested = _studio_field_and_renderer(source)
        if source == PROFILE_SOURCE:
            from .render_rendercv import resume_to_rendercv_dict

            resume, _ = _studio_build_resume()
            return {"yaml": json.dumps(resume_to_rendercv_dict(resume),
                                       indent=2, ensure_ascii=False),
                    "field": field, "suggested_renderer": suggested}
    except SystemExit as exc:  # load_profile exits if master_profile.json is missing
        return {"error": str(exc)}
    path = config.OUTPUT_DIR / "applications" / source / "resume.yaml"
    if not path.is_file() or path.resolve().parent.parent != \
            (config.OUTPUT_DIR / "applications").resolve():
        return {"error": f"no resume.yaml for '{source}'"}
    return {"yaml": path.read_text(encoding="utf-8"),
            "field": field, "suggested_renderer": suggested}


class StudioRenderRequest(BaseModel):
    yaml: str


@app.post("/api/resume-studio/render")
def studio_render(req: StudioRenderRequest) -> dict:
    """Typeset an edited YAML. Returns the PDF (base64) and the Typst source
    text; slow (~15-30s, runs the rendercv CLI)."""
    from .render_rendercv import render_yaml_file

    work = config.OUTPUT_DIR / "resume_studio" / "web"
    work.mkdir(parents=True, exist_ok=True)
    ypath = work / "resume.yaml"
    ypath.write_text(req.yaml, encoding="utf-8")
    try:
        outs = render_yaml_file(ypath, work / "out")
    except Exception as exc:
        return {"error": str(exc)}
    from .ats_engine import load_profile
    from .tailor import resume_basename
    try:  # profile only feeds the download filename — don't fail a good render
        _person = (load_profile(None).get("personal") or {}).get("name")
    except SystemExit:
        _person = None
    return {
        "pdf_b64": base64.b64encode(outs["pdf"].read_bytes()).decode("ascii"),
        "typ": outs["typ"].read_text(encoding="utf-8") if outs.get("typ") else None,
        "pdf_name": resume_basename(_person, None) + ".pdf",
    }


@app.get("/api/resume-studio/docx")
def studio_docx(source: str = PROFILE_SOURCE) -> dict:
    """The classic .docx render (base64) — generate.py's python-docx path,
    kept as a renderer choice alongside the Typst PDF."""
    from .tailor import resume_basename
    try:
        if source == PROFILE_SOURCE:
            from .render_docx import render_docx

            resume, prof = _studio_build_resume()
            work = config.OUTPUT_DIR / "resume_studio" / "web"
            work.mkdir(parents=True, exist_ok=True)
            path = render_docx(resume, work / "resume.docx")
            person = (prof.get("personal") or {}).get("name")
            company = None
        else:
            path = config.OUTPUT_DIR / "applications" / source / "resume.docx"
            if not path.is_file() or path.resolve().parent.parent != \
                    (config.OUTPUT_DIR / "applications").resolve():
                return {"error": f"no resume.docx for '{source}' — re-run "
                                 "python -m job_bot.generate for it"}
            from .ats_engine import load_profile
            person = (load_profile(None).get("personal") or {}).get("name")
            company = source.split("_", 1)[0]  # slug is company_role
    except SystemExit as exc:  # load_profile exits if master_profile.json is missing
        return {"error": str(exc)}
    return {"docx_b64": base64.b64encode(path.read_bytes()).decode("ascii"),
            "name": resume_basename(person, company) + ".docx"}


class BriefRequest(BaseModel):
    company: str
    role: str = "this role"


@app.post("/api/brief")
def brief(req: BriefRequest) -> dict:
    """Structured company research brief (+ LLM narrative when a key is set)."""
    from .company_research import build_brief

    return build_brief(req.company, req.role, use_llm=config.has_llm())


class LinkedInRequest(BaseModel):
    target_role: str | None = None
    jd_text: str | None = None


@app.post("/api/linkedin")
def linkedin(req: LinkedInRequest) -> dict:
    """LinkedIn profile audit: headline, About, ranked skills, keyword gaps."""
    from .linkedin_optimizer import audit

    return audit(target_role=req.target_role, jd_text=req.jd_text, use_llm=config.has_llm())


class RecordingRequest(BaseModel):
    question: str = "Tell me about a time you improved a process"
    transcript: str
    duration_seconds: float | None = None


@app.post("/api/recording")
def recording(req: RecordingRequest) -> dict:
    """Analyze a practice-answer transcript: STAR, pacing, fillers, fixes."""
    from .recording import analyze_recording

    return analyze_recording(
        req.transcript, req.duration_seconds, req.question, use_llm=config.has_llm()
    )


# --- Career coach (live chat) ------------------------------------------------
@app.get("/api/coach/snapshot")
def coach_snapshot() -> dict:
    """Read-only live snapshot the coach is grounded in (funnel, interviews,
    follow-ups, recruiter email, fresh postings, growth). Backs the Coach tab's
    context strip; the chat rebuilds this itself each turn."""
    from . import coach

    return coach.build_snapshot()


class CoachMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class CoachRequest(BaseModel):
    messages: list[CoachMessage]


@app.post("/api/coach")
def coach_chat(req: CoachRequest) -> dict:
    """One coaching turn. Send the full conversation so far; get the reply.

    Grounded in COACH.md + a fresh pipeline snapshot every turn (see
    ``job_bot.coach``), so the coach answers from real numbers. Returns
    ``{"reply": None, "error": ...}`` instead of a 500 when the LLM isn't
    configured or the call fails, so the chat can show it inline.
    """
    from . import coach

    if not config.has_llm():
        return {
            "reply": None,
            "error": "No ANTHROPIC_API_KEY configured — set it in .env to enable the coach.",
        }
    msgs = [{"role": m.role, "content": m.content} for m in req.messages]
    try:
        return {"reply": coach.chat(msgs)}
    except Exception as exc:  # surface LLM/errors to the chat, don't 500
        return {"reply": None, "error": str(exc)}


class IntakeRequest(BaseModel):
    url: str
    company: str
    title: str
    portal: str = "other"
    status: str = "applied"
    notes: str | None = None


@app.post("/api/intake")
def intake(req: IntakeRequest) -> dict:
    """Log a job John found and applied to manually.

    Returns: { id, company_id, company_name, job_title, url, status, portal, logged_at }
    or { error: "..." } if validation fails.
    """
    from . import intake

    try:
        return intake.log_job(
            url=req.url,
            company_name=req.company,
            title=req.title,
            portal=req.portal,
            status=req.status,
            notes=req.notes,
        )
    except ValueError as exc:
        return {"error": str(exc)}


@app.get("/api/companies")
def companies_list(due_for_check: bool = False) -> list[dict]:
    """List all companies, or only those due for check.

    Returns: list of company records with all fields.
    """
    from . import companies

    if due_for_check:
        return companies.due_for_check()
    else:
        return companies.list_all()


@app.get("/api/companies/{company_id}")
def get_company(company_id: int) -> dict | None:
    """Get a single company by ID."""
    from . import companies

    return companies.get_by_id(company_id)


class MarkCheckedRequest(BaseModel):
    next_check_in_days: int = 7


@app.patch("/api/companies/{company_id}")
def mark_company_checked(company_id: int, req: MarkCheckedRequest) -> dict:
    """Mark a company as checked today, schedule next check."""
    from . import companies

    try:
        return companies.mark_checked(company_id, req.next_check_in_days)
    except ValueError as exc:
        return {"error": str(exc)}


# --- Serve the built React app (single-process mode) -------------------------
# When `web/dist` exists (after `cd web && npm run build`), the whole app —
# UI *and* API — is served from this one process on one port. No Vite, no CORS.
# Mounted last so the `/api/*` routes above always take priority. In dev you can
# still run Vite (5173) against this API; in that mode `dist` may be absent and
# this mount is simply skipped.
_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
if _DIST.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="web")


def main() -> None:
    import uvicorn

    uvicorn.run("job_bot.api:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
