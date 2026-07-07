"""LinkedIn Profile Optimizer (Recommendation #6).

Audits John's profile against the same JD/keyword logic the ATS scorer uses and
proposes concrete LinkedIn edits — headline, About section, Skills, and
experience bullets — so the profile mirrors the resume strategically and pulls
more inbound recruiter traffic.

Inputs: the master profile (source of truth) plus an optional target JD or a
target role. Output: ready-to-paste headline + About draft, a ranked skills
list, per-role bullet suggestions, and a keyword-gap list. Template-based;
Claude-polished for the About section when a key is present.
"""

from __future__ import annotations

from . import config
from .ats_engine import load_profile
from .writing_style import STYLE_RULES

GRAD = "2027"


def _all_profile_skills(profile: dict) -> list[str]:
    out: list[str] = []
    for grp in profile.get("skills", []):
        out += grp.get("skills", [])
    # de-dup, preserve order
    seen, uniq = set(), []
    for s in out:
        k = s.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(s)
    return uniq


def _target_role(profile: dict, override: str | None) -> str:
    if override:
        return override
    roles = (profile.get("targets") or {}).get("target_roles") or []
    return roles[0] if roles else "Technology Risk Analyst"


def _missing_keywords(profile: dict, jd_text: str | None) -> list[str]:
    """Required JD keywords not yet evidenced in the profile (gap to add)."""
    if not jd_text:
        return []
    from .ats_engine import score
    from .jd_parser import parse_jd
    job = parse_jd(jd_text, use_llm=False)
    report = score(job, profile)
    return [h.keyword for h in report.missing_keywords if h.importance == "required"]


HEADLINE_MAX = 220  # LinkedIn's hard limit


def _short_major(raw: str | None) -> str:
    """Collapse a verbose degree string to a concise field name."""
    if not raw:
        return ""
    s = raw.split(" - ")[0].split(",")[-1] if "," in raw else raw.split(" - ")[0]
    s = s.replace("Bachelor of Science", "").replace("Bachelor of Arts", "")
    s = s.replace("B.S.", "").replace("B.A.", "").strip(" .")
    return s or raw.strip()


def headline(profile: dict, role: str) -> str:
    # Playbook format: "Accounting & Information Science Student at the
    # University of Maryland | <positioning> | <topic> | <topic>"
    edu = (profile.get("education") or [{}])[0]
    major = _short_major(edu.get("major")) or "Accounting"
    second = _short_major(edu.get("secondary_major"))
    field = f"{major} & {second}" if second else major
    picks: list[str] = []
    for s in _all_profile_skills(profile):
        low = s.lower()
        if "suite" in low:  # generic office suites add no search signal
            continue
        if any(low in p.lower() or p.lower() in low for p in picks):
            continue  # skip near-duplicates (Excel vs Microsoft Excel)
        picks.append(s)
        if len(picks) == 2:
            break
    spotlight = " | ".join(picks) if picks else "Audit | Data Analytics"
    text = (f"{field} Student at the University of Maryland | "
            f"Aspiring {role} | {spotlight}")
    if len(text) > HEADLINE_MAX:  # drop the spotlight, then trim
        text = f"{field} Student at the University of Maryland | Aspiring {role}"[:HEADLINE_MAX]
    return text


def about_section(profile: dict, role: str, add_keywords: list[str]) -> str:
    name = profile.get("personal", {}).get("name", "John Bae")
    edu = (profile.get("education") or [{}])[0]
    summary = profile.get("summary") or (
        f"I'm a University of Maryland student studying {edu.get('major','Accounting')}"
        + (f" and {edu.get('secondary_major')}" if edu.get("secondary_major") else "")
        + f", graduating {edu.get('graduation_date', GRAD)}.")
    interests = (f"I'm focused on becoming a {role}, working at the intersection of "
                 "accounting, controls, and data analytics.")
    proof = "Recent work spans audit support, data analysis, and leadership in PSE/IEFS/TerpTax."
    kw = ""
    if add_keywords:
        kw = ("\n\nCore areas: " + ", ".join(add_keywords[:10]) + ".")
    cta = "\n\nOpen to internships and full-time opportunities — feel free to connect."
    return f"{summary}\n\n{interests} {proof}{kw}{cta}"


def ranked_skills(profile: dict, add_keywords: list[str]) -> list[str]:
    """LinkedIn lets you pin ~50 skills; surface the highest-signal first."""
    have = _all_profile_skills(profile)
    # Put JD-required additions first (these are the gaps recruiters search), then yours.
    ordered = [k for k in add_keywords if k.lower() not in {h.lower() for h in have}] + have
    seen, out = set(), []
    for s in ordered:
        k = s.lower()
        if k not in seen:
            seen.add(k)
            out.append(s)
    return out[:50]


def experience_suggestions(profile: dict) -> list[dict]:
    """Surface each role's strongest, quantified bullets to mirror on LinkedIn."""
    out = []
    for e in profile.get("experience", []):
        bullets = sorted(e.get("bullets", []),
                         key=lambda b: (b.get("quantified", False), b.get("strength_score", 0)),
                         reverse=True)
        # Playbook: resume shows ~3 bullets per role, LinkedIn can carry 5-7.
        out.append({
            "role": e.get("role"), "organization": e.get("organization"),
            "top_bullets": [b.get("text", "") for b in bullets[:6]],
            "note": ("Show 5-7 bullets here (vs ~3 on the resume); lead with the "
                     "quantified ones — LinkedIn truncates after ~2 lines."
                     if bullets else "Add 5-7 quantified accomplishment bullets here."),
        })
    return out


def audit(profile: dict | None = None, jd_text: str | None = None,
          target_role: str | None = None, use_llm: bool | None = None) -> dict:
    profile = profile or load_profile(None)
    role = _target_role(profile, target_role)
    add = _missing_keywords(profile, jd_text)

    about = about_section(profile, role, add)
    if use_llm is None:
        use_llm = config.has_llm()
    if use_llm and config.has_llm():
        try:
            about = _llm_about(profile, role, add)
        except Exception as exc:  # pragma: no cover
            print(f"  ! LLM About polish failed ({exc}); using template")

    recs = []
    if add:
        recs.append(f"Add these JD-required keywords to your Skills + About: {', '.join(add[:8])}.")
    have = _all_profile_skills(profile)
    if len(have) < 10:
        recs.append("List at least 10-15 skills — recruiters filter by skill; you have "
                    f"only {len(have)} on file.")
    if not profile.get("personal", {}).get("linkedin"):
        recs.append("Add your LinkedIn URL to the master profile so the system can deep-link it.")
    recs.append("Set the headline below — it's the #1 search-ranked field on LinkedIn.")
    recs.append("Turn on 'Open to Work' (recruiters-only) for your target roles + DMV/remote.")

    return {
        "target_role": role,
        "headline": headline(profile, role),
        "about": about,
        "skills": ranked_skills(profile, add),
        "experience": experience_suggestions(profile),
        "keyword_gaps": add,
        "recommendations": recs,
    }


def _llm_about(profile: dict, role: str, add: list[str]) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    name = profile.get("personal", {}).get("name", "John Bae")
    prompt = (
        f"Write a first-person LinkedIn 'About' section for {name}, a UMD Accounting + "
        f"Information Science student (grad {GRAD}) aiming to be a {role}. "
        f"Naturally work in these keywords: {', '.join(add[:10]) or 'audit, data analytics, risk'}. "
        "Tell a story: why accounting, why information science, career goals, and "
        "what he's seeking now. Position him at the intersection of accounting, "
        "technology, and analytics — technical skills combined with client service, "
        "compliance, and business problem-solving. "
        "3 short paragraphs, ~140 words, confident but not boastful, end with a connect CTA. "
        "Use only real facts implied by the profile; invent nothing specific — "
        "including dates or recruiting-cycle years not given here.\n"
        + STYLE_RULES
    )
    msg = client.messages.create(model=config.ANTHROPIC_MODEL, max_tokens=450,
                                 messages=[{"role": "user", "content": prompt}])
    return "".join(b.text for b in msg.content if b.type == "text").strip()


def format_audit(a: dict) -> str:
    lines = ["\n" + "=" * 64,
             f"LINKEDIN PROFILE OPTIMIZER — target: {a['target_role']}",
             "=" * 64,
             "\nHEADLINE (paste into 'Headline', max 220 chars)",
             f"  {a['headline']}",
             f"  [{len(a['headline'])} chars]",
             "\nABOUT (paste into 'About')",
             "  " + a["about"].replace("\n", "\n  "),
             "\nSKILLS (add in this priority order)",
             "  " + ", ".join(a["skills"][:25]) + ("…" if len(a["skills"]) > 25 else "")]
    if a["keyword_gaps"]:
        lines += ["\nKEYWORD GAPS vs the target JD (add these first)",
                  "  " + ", ".join(a["keyword_gaps"])]
    lines.append("\nEXPERIENCE — bullets to mirror from your resume")
    for e in a["experience"]:
        lines.append(f"  {e['role']} @ {e['organization']}")
        for b in e["top_bullets"]:
            lines.append(f"     • {b}")
        lines.append(f"     ({e['note']})")
    lines.append("\nRECOMMENDATIONS")
    for r in a["recommendations"]:
        lines.append(f"  → {r}")
    lines.append("=" * 64 + "\n")
    return "\n".join(lines)


def main() -> None:
    import argparse
    import sys
    from pathlib import Path

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="LinkedIn profile optimizer (Recommendation #6).")
    ap.add_argument("--role", help="Target role (defaults to profile's first target role)")
    ap.add_argument("--file", type=Path, help="Target JD file to find keyword gaps against")
    ap.add_argument("--profile", type=Path)
    ap.add_argument("--no-llm", action="store_true")
    args = ap.parse_args()

    jd = args.file.read_text(encoding="utf-8", errors="replace") if args.file else None
    profile = load_profile(args.profile)
    a = audit(profile, jd_text=jd, target_role=args.role,
              use_llm=False if args.no_llm else None)
    print(format_audit(a))


if __name__ == "__main__":
    main()
