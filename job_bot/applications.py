"""Canonical application tracker — the single source of truth for "where do I
stand with everywhere I applied".

The raw data is spread across, and disagrees between, several tables: `jobs`
(rows John imported from his tracker + Gmail, with duplicates and inconsistent
company spellings), `tracked_emails` (the comprehensive Gmail outcome history),
`interviews`, `rejections`, and `offers`. This module reconciles them into ONE
deduped, name-normalized list — one row per company John actually applied to —
with a single derived status, so every number in the dashboard can be computed
from the same place and nothing is "off".

Status (mutually exclusive outcomes, so they always sum to the total):
    offer        — an offer is on the table
    rejected     — at least one rejection (a company can reject several roles)
    ghosted      — applied, no response in GHOST_DAYS, no rejection/interview
    interviewing — reached interview/assessment and still active
    in_review    — applied, still within the response window, no outcome yet
`reached_interview` is tracked separately (a cross-cutting flag) so the funnel
can show how many applications got to an interview regardless of final outcome.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from .db import connect

# Days of silence after the last contact before an open application is "ghosted".
GHOST_DAYS = 45

# Company-name canonicalization: (regex tested against the lowercased name) -> display.
# First match wins; order longer/more-specific patterns first.
_CANON: list[tuple[str, str]] = [
    (r"alvera|alvarez", "Alvarez & Marsal"),
    (r"cherry\s*bekaert", "Cherry Bekaert"),
    (r"cliftonlarsonallen|^cla$", "CLA"),
    (r"eisneramper", "EisnerAmper"),
    (r"j\.?p\.?\s*morgan|jpmorgan", "JPMorgan"),
    (r"federal reserve boar", "Federal Reserve Board"),
    (r"federal reserve bank", "Federal Reserve Bank"),
    (r"grant thornton", "Grant Thornton"),
    (r"bank of america", "Bank of America"),
    (r"goldman", "Goldman Sachs"),
    (r"citrin", "Citrin Cooperman"),
    (r"castro", "Castro & Company"),
    (r"sc&h|schgroup", "SC&H Group"),
    (r"kroger", "Kroger"),
    (r"citigroup|^citi$", "Citi"),
    (r"cohnreznick", "CohnReznick"),
    (r"tighe", "Tighe & Bond"),
    (r"blackrock", "BlackRock"),
    (r"robinhood", "Robinhood"),
    (r"samramajid|recruitix", "RecruitiX"),
    (r"raymond james", "Raymond James"),
    (r"enterprise bank", "Enterprise Bank & Trust"),
    (r"american bankers", "American Bankers Association"),
]

# Names that should render with specific casing rather than Title-case/UPPER.
_DISPLAY_FIX = {"pwc": "PwC", "ey": "EY", "kpmg": "KPMG", "rsm": "RSM", "bdo": "BDO",
                "uhy": "UHY", "usaa": "USAA", "cbiz": "CBIZ", "aba": "ABA", "cla": "CLA"}

# Not part of the internship / full-time career search — campus part-time jobs,
# relay junk, or unresolved senders. Excluded from the applications view.
_EXCLUDE = {"the scion group", "scion", "university view apartments", "university view",
            "michaels", "echo", "echosign", "us", "eino.fa.sender", "eino.bi.sender.2",
            "invalidemail", "workday", "msg", "campuscareers", "jobalerts", "systemmessage",
            "recruitix", ""}

# tracked_emails categories that prove John actually applied (not just marketing).
_APPLIED_CATS = ("recruiter_reply", "rejection", "interview_invite", "assessment", "offer")

# Career-field classification by role title. Ordered: first match wins, so the
# more specific fields (IT audit, tax, internal audit) are tested before the
# broad ones (audit, finance).
_FIELD_SIGNALS: list[tuple[str, list[str]]] = [
    ("IT Audit / Tech Risk", ["it audit", "it assurance", "technology risk", "tech risk",
                              "it risk", "itgc", "information security", "cyber", "digital risk",
                              "information systems", "sox it", "technology audit"]),
    ("Tax", ["tax", "vita"]),
    ("Internal Audit", ["internal audit", "internal auditor"]),
    ("Risk & Compliance", ["risk", "compliance", "controls", "enterprise risk", "operational risk",
                           "regulatory"]),
    ("Data & Analytics", ["data analyst", "data analytics", "analytics", "business analyst",
                          "business intelligence", "data scientist", "data engineer", "reporting analyst"]),
    ("Software / Engineering", ["software engineer", "software developer", "full stack",
                                "full-stack", "backend", "back-end", "frontend", "front-end",
                                "web developer", "devops", "cloud engineer", "site reliability",
                                "programmer", "mobile developer", "systems analyst", "it support",
                                "help desk", "qa engineer", "sdet", "developer", "software",
                                "systems engineer", "network engineer", "security engineer",
                                "platform engineer", "test engineer", "machine learning engineer",
                                "ml engineer", "ai engineer", "embedded", "salesforce"]),
    ("Audit & Assurance", ["audit", "assurance", "external audit"]),
    ("Finance / FP&A", ["financial analyst", "fp&a", "finance", "financial planning", "treasury",
                        "wealth", "accounting", "financial reporting", "fund", "investment"]),
]


# Fallback field for companies whose application emails never named the role
# (generic ATS confirmations). Based on the role John actually applied to there.
_COMPANY_FIELD_HINTS = {
    "Goldman Sachs": "Internal Audit", "JPMorgan": "Risk & Compliance", "Amazon": "Tax",
    "EY": "Audit & Assurance", "USAA": "Internal Audit", "Federal Reserve Bank": "Internal Audit",
    "Robinhood": "Finance / FP&A", "Comcast": "Finance / FP&A", "Bank of America": "Internal Audit",
    "Raymond James": "Finance / FP&A", "UHY": "Audit & Assurance", "Citi": "Internal Audit",
    "Baker Tilly": "Audit & Assurance", "Protiviti": "IT Audit / Tech Risk",
    "Northwestern Mutual": "Finance / FP&A", "T. Rowe Price": "Finance / FP&A",
    "Cornerstone Research": "Data & Analytics", "L3Harris": "Internal Audit",
    "MissionSquare Retirement": "Internal Audit",
}


def classify_field(title: str | None, extra: str = "") -> str:
    """Map a role title (and optional extra text) to one of John's career fields."""
    hay = f"{title or ''} {extra}".lower()
    for field, pats in _FIELD_SIGNALS:
        if any(p in hay for p in pats):
            return field
    return "Other"


def _app_field(texts: list[str]) -> str:
    """The dominant field across an application's role titles + email subjects."""
    from collections import Counter
    c = Counter(classify_field(t) for t in texts if t)
    # Prefer a specific field over the generic 'Other' when there's a mix.
    if len(c) > 1:
        c.pop("Other", None)
    return c.most_common(1)[0][0] if c else "Other"


def canon(name: str | None) -> str | None:
    """Normalize a company name to one canonical display form."""
    if not name:
        return None
    n = name.strip()
    low = n.lower()
    for pat, disp in _CANON:
        if re.search(pat, low):
            return disp
    # Default: tidy capitalization, with known acronyms cased correctly.
    if low in _DISPLAY_FIX:
        return _DISPLAY_FIX[low]
    return n[:1].upper() + n[1:] if n else n


def _d(s: str | None) -> str | None:
    """Best-effort YYYY-MM-DD out of a date-ish string."""
    if not s:
        return None
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(s))
    return m.group(1) if m else None


def _ref_date(con) -> date:
    """'Now' in the data's frame: the most recent tracked-email date (falls back
    to today). Using the data's own clock keeps 'ghosted' correct regardless of
    the machine's wall clock."""
    row = con.execute("SELECT MAX(received_at) FROM tracked_emails").fetchone()
    d = _d(row[0]) if row else None
    try:
        return datetime.strptime(d, "%Y-%m-%d").date() if d else date.today()
    except ValueError:
        return date.today()


def build_applications(ref_date: date | None = None) -> list[dict]:
    """Return one reconciled record per company John applied to."""
    con = connect()
    ref = ref_date or _ref_date(con)
    ghost_cutoff = (ref - timedelta(days=GHOST_DAYS)).isoformat()

    apps: dict[str, dict] = {}

    def slot(company: str | None) -> dict | None:
        disp = canon(company)
        if not disp or disp.lower() in _EXCLUDE:
            return None
        return apps.setdefault(disp, {
            "company": disp, "roles": set(), "subjects": set(), "n_jobs": 0, "n_emails": 0,
            "first_seen": None, "last_seen": None, "reached_interview": False,
            "has_offer": False, "has_rejection": False, "any_applied_signal": False,
        })

    def touch(a: dict, when: str | None):
        w = _d(when)
        if not w:
            return
        a["first_seen"] = w if not a["first_seen"] else min(a["first_seen"], w)
        a["last_seen"] = w if not a["last_seen"] else max(a["last_seen"], w)

    # 1) positions ledger (one row per distinct position applied to — verified from
    #    application-confirmation emails' job IDs/locations + his tracker).
    for r in con.execute("SELECT company, title, status, date_posted FROM jobs "
                         "WHERE site IN ('email','tracker','ledger')"):
        a = slot(r["company"])
        if a is None:
            continue
        a["n_jobs"] += 1
        a["any_applied_signal"] = True
        if r["title"]:
            a["roles"].add(r["title"].strip())
        if r["status"] == "rejected":
            a["has_rejection"] = True
        touch(a, r["date_posted"])

    # 2) Gmail outcome history.
    for r in con.execute("SELECT company, category, received_at, subject FROM tracked_emails"):
        a = slot(r["company"])
        if a is None:
            continue
        a["n_emails"] += 1
        if r["subject"]:
            a["subjects"].add(r["subject"])
        touch(a, r["received_at"])
        if r["category"] in _APPLIED_CATS:
            a["any_applied_signal"] = True
        # A real interview invite counts as reaching the interview stage; a bare
        # online assessment does not (kept consistent with the interviews table).
        if r["category"] == "interview_invite":
            a["reached_interview"] = True
        if r["category"] == "rejection":
            a["has_rejection"] = True
        if r["category"] == "offer":
            a["has_offer"] = True

    # 3) interviews + rejections + offers tables (authoritative for those signals).
    for r in con.execute("SELECT company FROM interviews"):
        a = slot(r["company"])
        if a:
            a["reached_interview"] = True
            a["any_applied_signal"] = True
    for r in con.execute("SELECT company FROM rejections"):
        a = slot(r["company"])
        if a:
            a["has_rejection"] = True
            a["any_applied_signal"] = True
    for r in con.execute("SELECT company FROM offers WHERE status='open'"):
        a = slot(r["company"])
        if a:
            a["has_offer"] = True
    con.close()

    out = []
    for a in apps.values():
        if not a["any_applied_signal"]:
            continue  # company we only ever got marketing from — not an application
        if a["has_offer"]:
            status = "offer"
        elif a["has_rejection"]:
            status = "rejected"
        elif a["last_seen"] and a["last_seen"] < ghost_cutoff:
            status = "ghosted"
        elif a["reached_interview"]:
            status = "interviewing"
        else:
            status = "in_review"
        rec = {
            "company": a["company"], "status": status,
            "reached_interview": a["reached_interview"],
            # positions = distinct application instances (each ledger row is one
            # posting/job-ID), NOT deduped titles — a firm applied to at several
            # locations counts each separately.
            "positions": max(a["n_jobs"], len(a["roles"]), 1),
            "roles": sorted(a["roles"]),
            "emails": a["n_emails"], "first_seen": a["first_seen"],
            "last_seen": a["last_seen"],
        }
        field = _app_field(list(a["roles"]) + list(a["subjects"]))
        if field == "Other" and a["company"] in _COMPANY_FIELD_HINTS:
            field = _COMPANY_FIELD_HINTS[a["company"]]
        rec["field"] = field
        out.append(rec)
    # Sort: most-advanced / most-recent first.
    rank = {"offer": 0, "interviewing": 1, "in_review": 2, "ghosted": 3, "rejected": 4}
    out.sort(key=lambda x: (rank.get(x["status"], 9), x["last_seen"] or "", x["company"]),
             reverse=False)
    return out


# Human-friendly labels for the status codes.
STATUS_LABEL = {"offer": "Offer", "interviewing": "Interviewing", "in_review": "In review",
                "ghosted": "Ghosted", "rejected": "Rejected"}


def summary(apps: list[dict] | None = None) -> dict:
    """Reconciled funnel counts — every number derives from the same list."""
    apps = build_applications() if apps is None else apps
    by_status = {k: 0 for k in STATUS_LABEL}
    for a in apps:
        by_status[a["status"]] = by_status.get(a["status"], 0) + 1
    total = len(apps)
    positions = sum(a["positions"] for a in apps)
    reached = sum(1 for a in apps if a["reached_interview"])
    active = by_status["in_review"] + by_status["interviewing"]
    # Field mix: companies per career field + how many reached an interview there.
    by_field: dict[str, dict] = {}
    for a in apps:
        f = by_field.setdefault(a["field"], {"companies": 0, "interviewed": 0})
        f["companies"] += 1
        f["interviewed"] += 1 if a["reached_interview"] else 0
    by_field = dict(sorted(by_field.items(), key=lambda kv: -kv[1]["companies"]))
    return {
        "total": total,
        "positions": positions,
        "by_status": by_status,
        "by_field": by_field,
        "reached_interview": reached,
        "active": active,
        "rejected": by_status["rejected"],
        "ghosted": by_status["ghosted"],
        "offers": by_status["offer"],
        # response rate = anything other than silence (ghosted) / total
        "response_rate": round(100 * (total - by_status["ghosted"]) / total) if total else 0,
        # interview rate = reached interview / total
        "interview_rate": round(100 * reached / total) if total else 0,
    }


def main() -> None:
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    apps = build_applications()
    s = summary(apps)
    print(f"\nAPPLICATIONS — {s['total']} companies "
          f"({s['reached_interview']} reached an interview, "
          f"{s['interview_rate']}% interview rate)\n")
    print("  " + "  ".join(f"{STATUS_LABEL[k]}={v}" for k, v in s["by_status"].items()))
    print()
    for a in apps:
        itv = " ★interviewed" if a["reached_interview"] else ""
        print(f"  {STATUS_LABEL[a['status']]:13} {a['company'][:26]:26} "
              f"{a['positions']} role(s)  {a['first_seen'] or '?'}→{a['last_seen'] or '?'}{itv}")


if __name__ == "__main__":
    main()
