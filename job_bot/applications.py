"""Canonical application tracker — the single source of truth for "where do I
stand with everywhere I applied".

The raw data is spread across, and disagrees between, several tables: `jobs`
(rows the owner imported from their tracker + Gmail, with duplicates and inconsistent
company spellings), `tracked_emails` (the comprehensive Gmail outcome history),
`interviews`, `rejections`, and `offers`. This module reconciles them into ONE
deduped, name-normalized list — one row per company the owner actually applied to —
with a single derived status, so every number in the dashboard can be computed
from the same place and nothing is "off".

Status (mutually exclusive outcomes, so they always sum to the total):
    offer        — an offer is on the table
    rejected     — at least one rejection, and nothing applied to since. A fresh
                   application dated after the latest rejection starts a new
                   cycle: the company is back to in_review (Robinhood rejected the
                   Summer 2026 intern app in Nov 2025; the Sept 2026 New Grad app
                   must not inherit that).
    ghosted      — applied, no response in GHOST_DAYS, no rejection/interview
    interviewing — reached interview/assessment and still active
    in_review    — applied, still within the response window, no outcome yet
`reached_interview` is tracked separately (a cross-cutting flag) so the funnel
can show how many applications got to an interview regardless of final outcome.
"""

from __future__ import annotations

import re
from contextlib import closing
from datetime import date, datetime, timedelta

from .db import connect, connect_readonly

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

# tracked_emails categories that prove the owner actually applied (not just marketing).
#
# `recruiter_reply` is deliberately NOT here. The inbox classifier hands out that
# label on loose cues ("talent acquisition" in the sender, "connect" in a body),
# so a Coinbase crypto newsletter and an IBM event-registration receipt both
# became "applications" in the funnel. A recruiter reply only counts as applied
# evidence when its subject is an actual application confirmation
# (_CONFIRMATION_RE) or the company already has a job row the owner logged.
_STRONG_APPLIED_CATS = ("rejection", "interview_invite", "assessment", "offer")
_APPLIED_CATS = _STRONG_APPLIED_CATS  # kept for callers that import the old name

_CONFIRMATION_RE = re.compile(
    r"thank(?:s| you) for (?:applying|your application|submitting)"
    r"|application (?:has been |was )?(?:received|submitted)"
    r"|(?:we(?:'ve| have) )?received your (?:job )?application"
    r"|application is (?:now )?complete"
    r"|successfully (?:applied|submitted)"
    r"|confirming your .{0,30}application"
    r"|congratulations on applying",
    re.I,
)

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
# (generic ATS confirmations). Based on the role the owner actually applied to there.
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
    """Map a role title (and optional extra text) to one of the owner's career fields."""
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


def build_applications(ref_date: date | None = None, *, read_only: bool = False,
                       since: str | None = None) -> list[dict]:
    """Return one reconciled record per company the owner applied to.

    `since` (YYYY-MM-DD) limits the tracker to the current search season:
    evidence dated before it is ignored, so an old internship cycle neither
    shows up nor colours this season's status. It defaults to
    `config.TRACKER_SINCE` (env JOB_BOT_TRACKER_SINCE); pass "" for all history.
    """
    if since is None:
        from . import config
        since = config.TRACKER_SINCE
    with closing(connect_readonly() if read_only else connect()) as con:
        return _build_applications(con, ref_date, since=_d(since))


def _columns(con, table: str) -> set[str]:
    return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}


# jobs.status -> position status shown in the tracker.
_JOB_TO_POSITION = {"new": "applied", "networking": "applied", "applied": "applied",
                    "interview": "interview", "rejected": "rejected", "offer": "offer",
                    "saved": "saved"}
OPEN_POSITION = {"applied", "assessment", "interview"}
# A receipt this close after the ledger snapshot is one of the applications the
# ledger already lists (Deloitte's 2026-02-16 receipt vs the 2026-02-15 import).
LEDGER_GRACE_DAYS = 30


def _plus(day: str | None, n: int) -> str | None:
    if not day:
        return None
    return (datetime.strptime(day, "%Y-%m-%d").date() + timedelta(days=n)).isoformat()


def _build_applications(con, ref_date: date | None, since: str | None = None) -> list[dict]:
    from .inbox import same_role

    ref = ref_date or _ref_date(con)
    ghost_cutoff = (ref - timedelta(days=GHOST_DAYS)).isoformat()

    hidden: set[str] = set()
    if _columns(con, "tracker_hidden"):
        hidden = {(r[0] or "").lower() for r in con.execute("SELECT company FROM tracker_hidden")}

    apps: dict[str, dict] = {}

    def before_season(when: str | None) -> bool:
        return bool(since) and (_d(when) or "") < since

    def slot(company: str | None) -> dict | None:
        disp = canon(company)
        if not disp or disp.lower() in _EXCLUDE or disp.lower() in hidden:
            return None
        return apps.setdefault(disp, {
            "company": disp, "roles": set(), "subjects": set(), "n_jobs": 0, "n_emails": 0,
            "first_seen": None, "last_seen": None, "reached_interview": False,
            "has_offer": False, "any_applied_signal": False,
            # Rejections that close the whole cycle (no role named, or a ledger /
            # rejections-table entry). A rejection with no usable date stays sticky.
            "cycle_rejected": False, "last_rejected": None, "undated_rejection": False,
            # Ledger rows all carry the import date (2026-02-15 for 100 rows), so a
            # ledger rejection can't be ordered against emails precisely.
            "ledger_rejected_at": None, "ledger_date": None,
            # A rejection naming one role closes that position only.
            "role_rejections": [], "interview_dates": [],
            "positions": [], "receipts": [],
        })

    def touch(a: dict, when: str | None):
        w = _d(when)
        if not w:
            return
        a["first_seen"] = w if not a["first_seen"] else min(a["first_seen"], w)
        a["last_seen"] = w if not a["last_seen"] else max(a["last_seen"], w)

    def cycle_rejected_on(a: dict, when: str | None):
        a["cycle_rejected"] = True
        w = _d(when)
        if not w:
            a["undated_rejection"] = True
        elif not a["last_rejected"] or w > a["last_rejected"]:
            a["last_rejected"] = w

    # 1) Positions the owner logged (tracker) or imported (ledger / email).
    for r in con.execute("SELECT id, company, title, status, date_posted, site, url FROM jobs "
                         "WHERE site IN ('email','tracker','ledger')"):
        a = slot(r["company"])
        if a is None:
            continue
        if since and (r["site"] != "tracker" or before_season(r["date_posted"])):
            continue  # imported history predates any season
        pstatus = _JOB_TO_POSITION.get((r["status"] or "applied").lower(), "applied")
        if pstatus == "saved":
            continue  # bookmarked, not applied
        a["n_jobs"] += 1
        if r["title"]:
            a["roles"].add(r["title"].strip())
        a["any_applied_signal"] = True
        d = _d(r["date_posted"])
        logged = r["site"] == "tracker"
        a["positions"].append({
            "role": (r["title"] or "").strip() or None, "applied_on": d if logged else None,
            "source": "logged" if logged else "imported", "status": pstatus,
            "job_id": r["id"], "url": r["url"] if logged else None, "gmail_id": None,
        })
        if pstatus == "interview":
            a["reached_interview"] = True
        if logged:
            touch(a, d)
            continue
        if d and (not a["ledger_date"] or d > a["ledger_date"]):
            a["ledger_date"] = d
        if pstatus == "rejected":
            a["cycle_rejected"] = True
            if d and (not a["ledger_rejected_at"] or d > a["ledger_rejected_at"]):
                a["ledger_rejected_at"] = d
            elif not d:
                a["undated_rejection"] = True
        touch(a, d)

    # 2) Gmail history.
    ecols = _columns(con, "tracked_emails")
    extra = ", ".join(c for c in ("role", "applied", "gmail_id") if c in ecols)
    role_scoped_rejections: set[tuple[str, str]] = set()
    for r in con.execute("SELECT company, category, received_at, subject"
                         + (f", {extra}" if extra else "") + " FROM tracked_emails"):
        if before_season(r["received_at"]):
            continue
        a = slot(r["company"])
        if a is None:
            continue
        cat = r["category"]
        keys = r.keys()
        role = r["role"] if "role" in keys else None
        receipt = cat in ("recruiter_reply", "assessment") and (
            ("applied" in keys and bool(r["applied"]))
            or bool(_CONFIRMATION_RE.search(r["subject"] or "")))
        a["n_emails"] += 1
        if cat == "other":
            continue  # unclassified mail says nothing about where things stand
        if r["subject"]:
            a["subjects"].add(r["subject"])
        touch(a, r["received_at"])
        # In a season view a rejection alone doesn't prove a *this-season*
        # application - BlackRock's Sept 2026 "no" was for a 2025 application.
        if cat in _STRONG_APPLIED_CATS and not (since and cat == "rejection"):
            a["any_applied_signal"] = True
        if receipt:
            a["any_applied_signal"] = True
            a["receipts"].append({"role": role, "day": _d(r["received_at"]),
                                  "gmail_id": r["gmail_id"] if "gmail_id" in keys else None})
        # A real interview invite counts as reaching the interview stage; a bare
        # online assessment does not (kept consistent with the interviews table).
        if cat == "interview_invite":
            a["reached_interview"] = True
            a["interview_dates"].append((_d(r["received_at"]), role))
        if cat == "rejection":
            if role:
                a["role_rejections"].append((_d(r["received_at"]), role))
                role_scoped_rejections.add((a["company"], _d(r["received_at"]) or ""))
            else:
                cycle_rejected_on(a, r["received_at"])
        if cat == "offer":
            a["has_offer"] = True

    # 3) interviews + rejections + offers tables (authoritative for those signals).
    for r in con.execute("SELECT company, scheduled_at FROM interviews"):
        if before_season(r["scheduled_at"]):
            continue
        a = slot(r["company"])
        if a:
            a["reached_interview"] = True
            a["any_applied_signal"] = True
    for r in con.execute("SELECT company, rejected_on FROM rejections"):
        if since and before_season(r["rejected_on"] or ""):
            continue
        a = slot(r["company"])
        if not a:
            continue
        if not since:
            a["any_applied_signal"] = True
        # Already counted, scoped to its role, from the email that logged it.
        if (a["company"], _d(r["rejected_on"]) or "") in role_scoped_rejections:
            continue
        cycle_rejected_on(a, r["rejected_on"])
    for r in con.execute("SELECT company FROM offers WHERE status='open'"
                         + (" AND created_at >= ?" if since else ""), (since,) if since else ()):
        a = slot(r["company"])
        if a:
            a["has_offer"] = True

    out = []
    for a in apps.values():
        if not a["any_applied_signal"]:
            continue  # company we only ever got marketing from — not an application
        positions = a["positions"]

        # Receipts → positions. A receipt for a position already listed attaches
        # to it; a receipt from the ledger's own era is one of the ledger's rows.
        ledger_cover = _plus(a["ledger_date"], LEDGER_GRACE_DAYS)
        # Receipts that name a role first, so a same-day "thanks for applying"
        # without one folds into that position instead of becoming a phantom.
        for rc in sorted(a["receipts"], key=lambda x: (x["role"] is None, x["day"] or "")):
            day, role = rc["day"], rc["role"]
            match = None
            for p in positions:
                if role and p["role"] and same_role(p["role"], role):
                    match = p
                elif not role and p["source"] in ("logged", "gmail") and p["applied_on"] and day \
                        and abs((datetime.strptime(p["applied_on"], "%Y-%m-%d")
                                 - datetime.strptime(day, "%Y-%m-%d")).days) <= 3:
                    match = p
                if match:
                    break
            if match:
                match["applied_on"] = match["applied_on"] or day
                match["gmail_id"] = match["gmail_id"] or rc["gmail_id"]
                if role and not match["role"]:
                    match["role"] = role
                continue
            if ledger_cover and day and day <= ledger_cover:
                continue
            positions.append({"role": role, "applied_on": day, "source": "gmail",
                              "status": "applied", "job_id": None, "url": None,
                              "gmail_id": rc["gmail_id"]})
            if role:
                a["roles"].add(role)

        # Later signals that name a role move that position.
        for day, role in a["role_rejections"]:
            hit = [p for p in positions if p["role"] and same_role(p["role"], role)]
            for p in hit:
                if p["status"] in OPEN_POSITION:
                    p["status"] = "rejected"
            if not hit:
                a["roles"].add(role)
        for day, role in a["interview_dates"]:
            for p in positions:
                if p["status"] == "applied" and p["applied_on"] and day and day >= p["applied_on"] \
                        and (not role or (p["role"] and same_role(p["role"], role))):
                    p["status"] = "interview"

        # Which positions are live in the current cycle?
        def is_new_open(p: dict) -> bool:
            if p["status"] not in OPEN_POSITION or p["source"] == "imported":
                return False
            if not a["cycle_rejected"]:
                return True
            if a["undated_rejection"] or not p["applied_on"]:
                return False
            if a["last_rejected"] and p["applied_on"] <= a["last_rejected"]:
                return False
            if a["ledger_rejected_at"]:
                bar = a["ledger_rejected_at"] if p["source"] == "logged" else _plus(
                    a["ledger_rejected_at"], LEDGER_GRACE_DAYS)
                if p["applied_on"] <= bar:
                    return False
            return True

        open_now = [p for p in positions if is_new_open(p)]
        for p in positions:
            # A cycle rejection dated after an open position closes it too.
            if p["status"] in OPEN_POSITION and p["source"] != "imported" and p not in open_now \
                    and a["cycle_rejected"]:
                p["status"] = "rejected"
        has_rejection = a["cycle_rejected"] or any(p["status"] == "rejected" for p in positions) \
            or bool(a["role_rejections"])
        reapplied = bool(a["cycle_rejected"] and open_now)
        cycle_start = min((p["applied_on"] for p in open_now if p["applied_on"]), default=None)
        interviewing_now = any(p["status"] == "interview" for p in open_now) or (
            a["reached_interview"] and not reapplied) or any(
            d and cycle_start and d >= cycle_start for d, _ in a["interview_dates"])
        last_applied = max((p["applied_on"] for p in positions if p["applied_on"]), default=None)

        if a["has_offer"]:
            status = "offer"
        elif has_rejection and not open_now:
            status = "rejected"
        elif a["last_seen"] and a["last_seen"] < ghost_cutoff:
            status = "ghosted"
        elif interviewing_now:
            status = "interviewing"
        else:
            status = "in_review"

        positions.sort(key=lambda p: (p["status"] not in OPEN_POSITION, -(int((p["applied_on"] or "0").replace("-", "")))))
        rec = {
            "company": a["company"], "status": status,
            "reached_interview": a["reached_interview"],
            # True when an earlier cycle at this company was rejected and the owner
            # has since applied again - the UI can show the history without the
            # old outcome hiding the live application.
            "reapplied": reapplied,
            # positions = distinct application instances (each ledger row is one
            # posting/job-ID), NOT deduped titles — a firm applied to at several
            # locations counts each separately.
            "positions": max(len(positions), 1),
            "open_positions": len(open_now) if (open_now or has_rejection) else
            sum(1 for p in positions if p["status"] in OPEN_POSITION),
            "positions_detail": positions,
            "roles": sorted(a["roles"]),
            "emails": a["n_emails"], "first_seen": a["first_seen"],
            "last_seen": a["last_seen"], "last_applied": last_applied,
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
