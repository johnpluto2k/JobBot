"""Posting legitimacy + liveness — career-ops "Block G", adapted for John.

Two independent checks that keep low-quality postings out of the pipeline so an
application is never wasted on a scam or a role that isn't actually open:

  1. assess()      — a text-heuristic scam + ghost-job score. No network. Flags
                     SCAM postings (personal-email contact, up-front payment,
                     WhatsApp/Telegram interviews, unrealistic pay) and GHOST /
                     evergreen postings (stale-but-still-open, "always hiring",
                     thin one-paragraph reqs, third-party staffing reposts).
  2. verify_live() — an OPTIONAL Playwright liveness check: opens the posting URL
                     and looks for "no longer accepting applications" / "position
                     filled" / a dead 404 page, so stale listings get pruned.
                     Degrades to "unknown" when Playwright isn't installed.

Philosophy borrowed straight from career-ops: your time is valuable and so is the
recruiter's — don't apply into scams or roles that have already closed. Scoring
is deterministic and debuggable (like ats_platforms), not a black box.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- SCAM signals: (compiled regex, penalty, human reason, guard) ------------
# guard=True signals are negation-checked: a match inside a disclaimer ("we never
# charge a fee") or a legitimate job duty is skipped. This avoids the classic false
# positives — a bank teller who "processes wire transfers", or an anti-scam notice.
_SCAM_SIGNALS: list[tuple[re.Pattern, int, str, bool]] = [
    (re.compile(r"\b(whats\s?app|telegram|signal app|google hangouts?)\b", re.I), 30,
     "asks to move the conversation to WhatsApp/Telegram/Hangouts", False),
    # Gift cards / Western Union / crypto payment are essentially never legit job content.
    (re.compile(r"\b(gift ?cards?|google play card|steam card|prepaid card|"
                r"western union|money\s?gram|crypto ?payment|payment in (crypto|bitcoin))\b", re.I), 40,
     "mentions gift-card / Western Union / crypto payment", False),
    # Candidate is asked to PAY a fee (verb-directed) — guarded against disclaimers.
    (re.compile(r"\b(pay|send|submit|deposit|purchase|cover|wire)\b[^.]{0,30}\bfee\b", re.I), 45,
     "appears to ask YOU to pay a fee — legitimate employers never do this", True),
    (re.compile(r"\bfee\b[^.]{0,20}\b(is )?(required|to (start|begin|apply|proceed))\b", re.I), 45,
     "a fee is described as required to start — a scam hallmark", True),
    (re.compile(r"(social security|ssn|passport number)[^.]{0,40}"
                r"(required|to start|upfront|up front|before|immediately)", re.I), 35,
     "asks for SSN/passport before an actual hire", False),
    (re.compile(r"(bank account|routing number|direct deposit)[^.]{0,40}"
                r"(to start|before|set ?up|upfront|up front)", re.I), 35,
     "asks for bank details before an actual hire", False),
    (re.compile(r"(no experience|no skills?)[^.]{0,30}(necessary|needed|required)"
                r"[^.]{0,50}(\$|earn|weekly pay|per week)", re.I), 22,
     "'no experience needed' paired with high pay", False),
    (re.compile(r"\$\s?\d{3,4}\s*(/|per)?\s*(day|week)\b", re.I), 25,
     "unusually high advertised day/week pay", False),
    (re.compile(r"[a-z0-9._%+-]+@(gmail|yahoo|hotmail|outlook|aol|proton|icloud)\.com", re.I), 25,
     "contact is a personal email address, not a company domain", False),
    (re.compile(r"(immediate start|urgent(ly)? hiring|start today|hiring asap|"
                r"limited slots|act now)", re.I), 10,
     "high-pressure urgency language", False),
    (re.compile(r"interview[^.]{0,25}(via|by|over)[^.]{0,15}(text|chat|whats\s?app|telegram)", re.I), 30,
     "offers a text/chat 'interview' instead of a call or video", False),
]

# Negation / legitimacy-disclaimer cues near a guarded match => it's not a scam signal.
_NEGATION = re.compile(r"\b(no|not|never|don'?t|do not|does not|won'?t|will not|without|"
                       r"free of|nor|charge any|any candidate|beware|scam|fraud)\b", re.I)


def _guarded_hit(pat: re.Pattern, hay: str) -> bool:
    """True only if a match exists that is NOT inside a negation/disclaimer window."""
    for m in pat.finditer(hay):
        window = hay[max(0, m.start() - 55):m.start()]
        if not _NEGATION.search(window):
            return True
    return False

# --- GHOST / evergreen signals ------------------------------------------------
_GHOST_SIGNALS: list[tuple[re.Pattern, int, str]] = [
    (re.compile(r"(always (hiring|looking)|evergreen|ongoing basis|"
                r"talent (pool|community|network|pipeline)|future (openings|opportunities)|"
                r"pipeline (req|role|posting)|general application|expression of interest)", re.I), 25,
     "evergreen 'always hiring' / talent-pool posting, not a specific opening"),
    (re.compile(r"(various|multiple|several) locations|nationwide|locations? across", re.I), 8,
     "generic multi-location listing"),
    (re.compile(r"(staffing|recruiting agency|our client|on behalf of a client|"
                r"confidential client|leading (company|firm) in)", re.I), 12,
     "third-party staffing repost — company is hidden"),
]

_GRADES = (
    (75, "legit", "✅ Likely legit"),
    (50, "caution", "⚠️ Verify first"),
    (0, "high risk", "🚩 High risk"),
)


@dataclass
class LegitFlag:
    kind: str      # "scam" | "ghost"
    reason: str
    penalty: int


@dataclass
class LegitReport:
    legit_score: int
    grade: str            # ✅ / ⚠️ / 🚩 label
    risk: str             # legit | caution | high risk
    flags: list[LegitFlag] = field(default_factory=list)

    @property
    def scam_flags(self) -> list[LegitFlag]:
        return [f for f in self.flags if f.kind == "scam"]

    @property
    def ghost_flags(self) -> list[LegitFlag]:
        return [f for f in self.flags if f.kind == "ghost"]

    def summary(self) -> str:
        if not self.flags:
            return "No scam or ghost-job signals found."
        return "; ".join(f.reason for f in self.flags)


def assess(text: str, *, title: str | None = None, company: str | None = None,
           days_since: int | None = None) -> LegitReport:
    """Score a posting 0-100 for legitimacy (higher = safer). No network."""
    hay = " ".join(x for x in (title, company, text) if x)
    score = 100
    flags: list[LegitFlag] = []

    for pat, penalty, reason, guard in _SCAM_SIGNALS:
        hit = _guarded_hit(pat, hay) if guard else bool(pat.search(hay))
        if hit:
            score -= penalty
            flags.append(LegitFlag("scam", reason, penalty))

    for pat, penalty, reason in _GHOST_SIGNALS:
        if pat.search(hay):
            score -= penalty
            flags.append(LegitFlag("ghost", reason, penalty))

    # Staleness: a posting still open long after it went up is a classic ghost.
    if days_since is not None:
        if days_since > 60:
            p = 25
            flags.append(LegitFlag("ghost", f"posted {days_since} days ago and still open", p))
            score -= p
        elif days_since > 30:
            p = 12
            flags.append(LegitFlag("ghost", f"posted {days_since} days ago", p))
            score -= p

    # Suspiciously thin description (real reqs are rarely this short).
    body = (text or "").strip()
    if 0 < len(body) < 350:
        p = 15
        flags.append(LegitFlag("ghost", "unusually thin job description", p))
        score -= p

    score = max(0, min(100, score))
    for cutoff, risk, grade in _GRADES:
        if score >= cutoff:
            return LegitReport(score, grade, risk, flags)
    return LegitReport(score, "🚩 High risk", "high risk", flags)


# --- Optional Playwright liveness verification -------------------------------
_DEAD_MARKERS = [
    "no longer accepting applications", "no longer available", "position has been filled",
    "position filled", "this job is closed", "posting is closed", "job posting expired",
    "this position is no longer", "we are no longer accepting", "job not found",
    "page not found", "404", "this listing has expired", "role has been filled",
    "applications are closed", "this opportunity is no longer available",
]


def _playwright_available() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except Exception:
        return False


def verify_live(url: str, *, timeout: float = 15.0) -> dict:
    """Open the posting and judge whether it's still live.

    Returns {"status": live|closed|dead|unknown, "detail": ...}. Uses Playwright
    if available; otherwise returns "unknown" (never blocks the pipeline).
    """
    if not url:
        return {"status": "unknown", "detail": "no URL to check"}
    if not _playwright_available():
        return {"status": "unknown",
                "detail": "Playwright not installed — run `python -m playwright install chromium`"}
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover
        return {"status": "unknown", "detail": f"Playwright import failed: {exc}"}

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            resp = page.goto(url, timeout=int(timeout * 1000), wait_until="domcontentloaded")
            status_code = resp.status if resp else 0
            body = (page.content() or "").lower()
            browser.close()
    except Exception as exc:
        return {"status": "unknown", "detail": f"could not open the page ({exc})"}

    if status_code and status_code >= 400:
        return {"status": "dead", "detail": f"HTTP {status_code} — page is gone"}
    for marker in _DEAD_MARKERS:
        if marker in body:
            return {"status": "closed", "detail": f"page says: '{marker}'"}
    return {"status": "live", "detail": f"HTTP {status_code or 200}, no closed/expired markers"}


def main() -> None:
    import argparse
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Posting legitimacy + liveness check (career-ops Block G).")
    ap.add_argument("--file", help="Path to a job description text file")
    ap.add_argument("--text", help="Paste a job description inline")
    ap.add_argument("--title")
    ap.add_argument("--company")
    ap.add_argument("--days", type=int, help="Days since the posting went up")
    ap.add_argument("--verify-url", help="Also run a Playwright liveness check on this URL")
    args = ap.parse_args()

    text = args.text or ""
    if args.file:
        from pathlib import Path
        text = Path(args.file).read_text(encoding="utf-8", errors="replace")

    if text.strip():
        rep = assess(text, title=args.title, company=args.company, days_since=args.days)
        print("\n" + "=" * 60)
        print(f"LEGITIMACY  {rep.grade}   ({rep.legit_score}/100, {rep.risk})")
        print("=" * 60)
        if rep.flags:
            for f in rep.flags:
                print(f"  [{f.kind:>5}] -{f.penalty:<3} {f.reason}")
        else:
            print("  No scam or ghost-job signals found.")
        print("=" * 60 + "\n")

    if args.verify_url:
        live = verify_live(args.verify_url)
        print(f"LIVENESS: {live['status'].upper()} — {live['detail']}\n")


if __name__ == "__main__":
    main()
