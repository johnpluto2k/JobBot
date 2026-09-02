"""Tests for the bullet workbench (job_bot.bullets) — no LLM, no network.

The workbench is the "I format my own resume" path: it must parse a pasted
resume, rank each bullet against a JD, and hand back text that is a faithful
copy of what was pasted. These tests pin the two properties that make it
trustworthy: nothing is invented without an API key, and the keep/cut line
matches the generator's own bullet budget.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from job_bot.bullets import CUT, LEAD, parse_resume_text, tailor_bullets  # noqa: E402
from job_bot.line_fit import measure  # noqa: E402
from job_bot.jd_parser import parse_jd  # noqa: E402
from job_bot.tailor import MAX_BULLETS  # noqa: E402

RESUME = """John Bae
College Park, MD | john@example.com

EDUCATION
University of Maryland, College Park, MD
B.S. Accounting  Expected May 2027

EXPERIENCE
CowSync | Full-Stack Developer  June 2026 - Present
- Designed Postgres schemas and wrote SQL queries powering reporting dashboards
- Built REST API endpoints in Node and Express for a genetics SaaS platform
- Shipped a Playwright test suite that cut manual regression checking
- Collaborated with the founder to scope features and prioritize the roadmap

The Scion Group | Leasing Consultant  August 2025 - May 2026
- Processed 60+ lease applications, verifying documentation for compliance
- Reconciled monthly rent ledgers in Excel and flagged discrepancies

LEADERSHIP
Smith Consulting Club | Analyst  September 2025 - Present
- Delivered a market-entry recommendation using data from 6+ company types

PROJECTS
Pantry Plate | React, Node, Supabase
- Built a full-stack recipe app matching pantry inventory for 100+ users

SKILLS
Technical: Python, SQL, JavaScript, Node, Git
Analytical: Data Analysis, Excel, Tableau
"""

JD = """IT Audit Associate — Technology Risk
KPMG, Washington, DC

- Perform IT general controls testing over access and change management
- Support SOX 404 compliance engagements
- Analyze data sets using SQL and Excel to identify control exceptions

Qualifications: Bachelor's in Accounting or Information Systems; SQL, Excel.
"""


def _job():
    return parse_jd(JD, use_llm=False)


def test_parses_every_pasted_bullet():
    parsed = parse_resume_text(RESUME)
    counts = {k: sum(len(b) for _, b in parsed[k])
              for k in ("experience", "leadership", "projects")}
    assert counts == {"experience": 6, "leadership": 1, "projects": 1}
    assert "SQL" in parsed["skills"]
    # Category labels ("Technical:") are stripped, not kept as a pseudo-skill.
    assert not any(s.lower().startswith("technical") for s in parsed["skills"])


def test_no_llm_never_invents_text():
    """Without an API key the tailored text must be the original, restyled at
    most by the deterministic house rules — never new claims."""
    wb = tailor_bullets(_job(), resume_text=RESUME, use_llm=False)
    assert wb.source == "resume"
    assert wb.rewritten is False
    for b in wb.bullets:
        assert not b.changed, f"unchanged run altered a bullet: {b.original!r}"
        # "and" -> "&" is the only licensed edit; the words themselves survive.
        assert b.tailored.replace("&", "and").rstrip(".") == b.original.rstrip(".")


def test_verdicts_respect_the_generator_bullet_budget():
    wb = tailor_bullets(_job(), resume_text=RESUME, use_llm=False)
    cow = [b for b in wb.bullets if b.entry.startswith("CowSync")]
    assert len(cow) == 4
    kept = [b for b in cow if b.verdict != CUT]
    assert len(kept) == MAX_BULLETS["experience"]
    # Exactly one lead per entry, and it is the highest-scoring bullet.
    assert [b.verdict for b in cow].count(LEAD) == 1
    assert cow[0].verdict == LEAD
    assert cow[0].relevance == max(b.relevance for b in cow)


def test_jd_relevant_bullets_outrank_generic_ones():
    wb = tailor_bullets(_job(), resume_text=RESUME, use_llm=False)
    cow = [b for b in wb.bullets if b.entry.startswith("CowSync")]
    sql_bullet = next(b for b in cow if "SQL" in b.original)
    founder_bullet = next(b for b in cow if "founder" in b.original)
    assert sql_bullet.relevance > founder_bullet.relevance
    assert "sql" in sql_bullet.keywords
    assert founder_bullet.verdict == CUT


def test_skills_lead_with_jd_matches():
    wb = tailor_bullets(_job(), resume_text=RESUME, use_llm=False)
    assert wb.skills, "skills section was not parsed"
    matched = {"SQL", "Excel", "Data Analysis"} & set(wb.skills)
    assert matched, "no JD-matching skill found"
    last_match = max(wb.skills.index(s) for s in matched)
    first_unmatched = min(wb.skills.index(s) for s in wb.skills if s not in matched)
    assert last_match < first_unmatched, f"unordered: {wb.skills}"


def test_falls_back_to_master_profile_when_nothing_pasted():
    from job_bot import config

    if not config.PROFILE_JSON.exists():
        try:
            import pytest
            pytest.skip("no master_profile.json built")
        except ImportError:
            return
    wb = tailor_bullets(_job(), resume_text=None, use_llm=False)
    assert wb.source == "profile"
    assert wb.bullets




def test_polish_strips_markdown_emphasis():
    """The rewrite model likes to bold metrics. Those asterisks would land
    verbatim in a LaTeX or .docx bullet."""
    from job_bot.writing_style import polish_bullet

    assert polish_bullet("Improved accuracy by **18%**") == "Improved accuracy by 18%"
    assert polish_bullet("Managed __$380K__ budget") == "Managed $380K budget"
    assert "*" not in polish_bullet("Cut waste by **12%** and **$25K**")


def test_best_fitting_never_picks_a_worse_variant():
    """Selection competes the current wording against every variant, so a model
    that returns something longer or emptier cannot make the bullet worse."""
    from job_bot.bullets import _best_fitting

    current = ("Managed compliance-ready lease, payment, & regulatory records for 800+ "
               "tenants, strengthening internal controls & audit preparedness")
    assert measure(current).lines == 2
    # A ladder of junk: longer, empty, and non-string entries.
    junk = [current + " across every property in the portfolio every single month", "", None]
    assert _best_fitting(current, junk) == current
    # A genuinely shorter one wins.
    better = "Managed lease & payment records for 800+ tenants, strengthening internal controls"
    assert _best_fitting(current, junk + [better]) == better


def test_best_fitting_prefers_the_fullest_line_among_equals():
    """Among variants that cost the same number of lines, keep the one that
    says the most — shortest-wins would strip the distinctive detail."""
    from job_bot.bullets import _best_fitting

    current = ("Prepared & reviewed 30+ individual & family tax returns under IRS "
               "VITA/TCE standards, ensuring regulatory compliance & accurate "
               "documentation for every filing")
    terse = "Reviewed 30+ tax returns"
    fuller = "Reviewed 30+ individual & family tax returns under IRS VITA/TCE standards"
    assert measure(current).lines == 2
    assert measure(terse).lines == measure(fuller).lines == 1
    # Both are legitimate deletions, so both are eligible...
    assert len(terse) < len(fuller) < len(current)
    # ...and the one that actually fills the line wins.
    assert _best_fitting(current, [terse, fuller]) == fuller


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
