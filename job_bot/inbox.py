"""Inbox triage: classify recruiting emails into a pipeline category + next
action, and update the tracker.

Pure-logic classifier (works offline on any email text). It can be fed by a
LinkedIn/Gmail export, pasted text, or the Gmail MCP — whatever surfaces the
sender/subject/body. Updates the `tracked_emails` table and, for interview
invites, can seed the `interviews` table.
"""

from __future__ import annotations

import re

from .db import connect
from .skills_ontology import KNOWN_COMPANIES

# category -> (subject/body signal patterns, default next action)
SIGNALS: list[tuple[str, list[str], str]] = [
    # A bare r"\boffer\b" used to lead this list. It matched consumer marketing
    # ("make the most of this 160K Bonus Points offer") and filed Hilton, Amex and
    # Coinbase blasts as job offers, which then propagated into the funnel the
    # coach treats as canonical. Every pattern here must carry employment context.
    ("offer", [r"pleased to offer", r"offer letter", r"offer of employment",
               r"employment offer", r"\bjob offer\b", r"formal offer", r"verbal offer",
               r"contingent offer", r"offer (?:package|documents)",
               r"extend(?:ing)? (?:you )?an offer"],
     "Review the offer; run the offer-comparison checklist and prep negotiation."),
    ("rejection", [r"\bunfortunately\b", r"not (?:be )?moving forward", r"decided to pursue other",
                   r"will not be progressing", r"other candidates", r"won'?t be moving forward",
                   r"regret to inform", r"not (?:be )?proceeding", r"no longer (?:able to )?consider",
                   r"not (?:been )?selected", r"application incomplete", r"do not have an appropriate",
                   r"decided to (?:progress|move forward) with other", r"position (?:has been |is )?filled",
                   r"position (?:has been )?cancelled", r"do not meet the", r"not (?:be )?able to consider",
                   r"we are sorry to let you know", r"sorry to (?:inform|let you know)"],
     "Log the rejection; capture stage + ATS score for the rejection-analysis report."),
    ("interview_invite", [r"invite you to (?:a |an )?(?:first|phone|video|virtual|on)",
                          r"invite you to interview", r"invitation to interview", r"interview confirmation",
                          r"interview invitation", r"phone screen", r"video interview", r"virtual interview",
                          r"would like to meet", r"schedule (?:a|your) (?:call|interview|time)",
                          r"book a time", r"superday", r"super day", r"selected to interview",
                          r"pleased to invite you", r"complete a .* video interview", r"on-demand .* interview",
                          r"thank you for interviewing", r"details of your video conference interview",
                          r"looks forward to speaking"],
     "Confirm a time, then generate a prep plan (python -m job_bot.pipeline --prep-plan)."),
    ("assessment", [r"hirevue", r"online assessment", r"\bOA\b", r"coding (?:test|challenge)",
                    r"take-home", r"hackerrank", r"codility", r"numerical reasoning",
                    r"complete (?:your |an |the )?(?:skills |online )?assessment", r"received your video",
                    r"online screening", r"pre-interview assessment"],
     "Schedule a focused block; practice the matching question type (interview --drill)."),
    ("recruiter_reply", [r"recruiter", r"talent acquisition", r"following up", r"thanks? for applying",
                         r"thank you for applying", r"thank you for your application",
                         r"received your (?:job )?application", r"application (?:has been |was )?received",
                         r"thank you for your interest", r"thank you for expressing interest",
                         r"congratulations on applying", r"application is now complete",
                         r"confirming your .{0,30}application", r"successfully (?:applied|submitted)",
                         r"thank you for completing", r"reaching out", r"connect", r"\bapplied\b"],
     "Reply promptly; if warm, ask about timeline and next steps."),
]

CATEGORY_TO_STATUS = {
    "interview_invite": "interview",
    "assessment": "interview",
    "recruiter_reply": "networking",
    "rejection": "rejected",
    "offer": "offer",
}


# ATS / mail-infra domains and generic local-parts that are NOT the employer.
ATS_DOMAINS = {"myworkday", "myworkdayjobs", "workday", "otp", "icims", "talent", "nurture",
               "avature", "jobvite", "lever", "hire", "greenhouse", "successfactors",
               "smartrecruiters", "ashbyhq", "brassring", "oraclecloud", "icloud"}
FREEMAIL = {"gmail", "outlook", "yahoo", "icloud", "hotmail", "proton"}
GENERIC_PREFIXES = {"noreply", "no-reply", "donotreply", "do-not-reply", "notification",
                    "notifications", "globalhr", "hr", "careers", "talent", "recruiting",
                    "candidate", "jobs", "mail", "email", "info", "hello", "apply", "team",
                    "systemmessage", "echosign", "interviews", "bizx", "opportunities", "learn",
                    "updates-noreply", "talentcentral", "join-our-team", "workday", "onlineapplication"}
# Second-level domains of generic ATS / e-sign / mail-relay providers — never a company name.
DOMAIN_NOISE = {"invalidemail", "myworkday", "workday", "echosign", "paycomonline", "msg",
                "jobvite", "ripplematch", "oracle", "workflow", "modernhire", "shl", "yello",
                "jotform", "newtonsoftware", "recruitix", "greenhouse-mail", "lever", "hire",
                "icims", "talent", "nurture", "avature", "beehiiv", "linkedin", "paycom"}
# Local-part codes that map to a specific employer.
SENDER_PREFIX_MAP = {"wf": "Wells Fargo", "rb": "Federal Reserve Bank", "cbh": "Cherry Bekaert",
                     "aba": "American Bankers Association", "uhyus": "UHY",
                     "osv_enterprise": "Enterprise Bank & Trust"}

# Sender host (substring of the part after @) that maps cleanly to one employer —
# used when the body/subject doesn't spell the company out (relay/ATS senders).
SENDER_DOMAIN_MAP = {"gt.com": "Grant Thornton", "thekrogerco.com": "Kroger",
                     "alaskaair.com": "Alaska Airlines", "claconnect.com": "CLA",
                     "schgroup.com": "SC&H Group", "castroco.com": "Castro & Company",
                     "uviewapts.com": "University View Apartments", "robinhood.com": "Robinhood",
                     "bofa.com": "Bank of America", "frb.gov": "Federal Reserve Board",
                     "jpmchase.com": "JPMorgan", "amazon.jobs": "Amazon", "cbiz.com": "CBIZ"}

# Employer names not in the skills ontology but worth resolving from subject/body text.
COMPANY_HINTS = {"the scion group": "The Scion Group", "scion group": "The Scion Group",
                 "citrin cooperman": "Citrin Cooperman", "alaska airlines": "Alaska Airlines",
                 "bank of america": "Bank of America", "federal reserve board": "Federal Reserve Board",
                 "jpmorganchase": "JPMorgan", "jpmorgan chase": "JPMorgan", "goldman sachs": "Goldman Sachs",
                 "dun & bradstreet": "Dun & Bradstreet", "cerity partners": "Cerity Partners",
                 "uline": "Uline", "usaa": "USAA", "crowe": "Crowe", "kroger": "Kroger",
                 "citrin": "Citrin Cooperman", "raymond james": "Raymond James", "pepsico": "PepsiCo"}

# Account-setup / credential / newsletter mail that should NOT be tracked as a status.
NOISE_PATTERNS = [
    r"verify your (candidate )?(email|account)", r"confirm your email", r"reset your password",
    r"password reset", r"completing your form later", r"return to the form",
    r"activate your account", r"what'?s new at", r"\bnewsletter\b",
    # one-time-passcode / identity confirmation (an ATS login step, not a status change)
    r"confirm your identity", r"one-?time pass\s?code", r"verification code",
    # employer-brand / PR blasts that match a company name but carry no application signal
    r"great place to work", r"is hiring", r"we'?re hiring", r"join our talent",
    r"talent (?:community|network) (?:update|newsletter)", r"upcoming (?:event|webinar)",
    # Consumer marketing blasts - loyalty programs, retail promos, product upsells.
    # These carry no application signal, and before the offer patterns above were
    # tightened they were landing in the funnel as offers.
    r"bonus points", r"reward points", r"cash ?back", r"\d+% off",
    r"limited[- ]time", r"ends (?:today|tonight|soon)", r"shop now", r"free shipping",
    r"save (?:up to )?\$?\d+", r"redeem your", r"exclusive (?:deal|savings)",
    r"your (?:statement|balance) is ready", r"price drop", r"flash sale",
]


def is_noise(subject: str, body: str = "") -> bool:
    t = f"{subject} {body}".lower()
    return any(re.search(p, t) for p in NOISE_PATTERNS)


# Aliases this short ("EY", "BDO", "CLA") collide with ordinary words and URL
# fragments, so they only count when they appear in the subject or the sender -
# never loose in a body. Hilton Honors mail used to register as an EY offer via
# a stray two-letter match deep in the message text.
SHORT_ALIAS_MAX = 3


def detect_company(text: str, sender: str = "", subject: str = "") -> str | None:
    hay = f"{sender} {text}".lower()
    strong = f"{sender} {subject}".lower() if subject else hay
    # 1. Known employer name in subject/body/sender — match longest alias first.
    #    Merge the ontology with local hints for names the ontology doesn't carry.
    aliases = {**COMPANY_HINTS, **KNOWN_COMPANIES}
    for key, disp in sorted(aliases.items(), key=lambda kv: -len(kv[0])):
        field = strong if len(key) <= SHORT_ALIAS_MAX else hay
        if re.search(rf"(?<![a-z]){re.escape(key)}(?![a-z])", field):
            return disp
    # 2. Sender host maps cleanly to one employer (relay/ATS domains).
    host = sender.lower().split("@")[-1]
    for frag, disp in SENDER_DOMAIN_MAP.items():
        if frag in host:
            return disp
    # 3. Sender local-part (before @, stripped of +tags) — code map, then literal.
    if m := re.match(r"([a-z0-9_\-.+]+)@", sender.lower()):
        local = m.group(1).split("+")[0]
        if local in SENDER_PREFIX_MAP:
            return SENDER_PREFIX_MAP[local]
        if (local not in GENERIC_PREFIXES and not local.startswith("no")
                and "." not in local and len(local) >= 3):
            return local.replace("-", " ").title()
    # 4. Domain fallback (skip ATS infra, freemail, and generic mail relays).
    # Use the registrable domain, not the first label: "noreply@h5.hilton.com" is
    # Hilton, not "H5", and "noreply@mail.coinbase.com" is Coinbase, not "Mail".
    if "@" in sender:
        host = sender.lower().split("@")[-1].strip().strip(">").rstrip(".")
        labels = [x for x in host.split(".") if x]
        if len(labels) >= 2:
            dom = labels[-2]
            if (dom not in ATS_DOMAINS and dom not in FREEMAIL and dom not in DOMAIN_NOISE
                    and len(dom) >= 3 and not dom.isdigit()):
                return dom.capitalize()
    return None


def classify_email(subject: str, body: str = "", sender: str = "") -> dict:
    text = f"{subject}\n{body}".lower()
    category, action = "other", "Review and file; no clear action."
    for cat, patterns, act in SIGNALS:
        if any(re.search(p, text, re.I) for p in patterns):
            category, action = cat, act
            break
    return {
        "category": category,
        "action": action,
        "company": detect_company(f"{subject} {body}", sender, subject=subject),
        "status_hint": CATEGORY_TO_STATUS.get(category),
    }


# One email is a status update about one application. If a detected name somehow
# still resolves to more rows than this, treat it as a misdetection and touch none.
MAX_JOBS_PER_EMAIL = 10


def _matching_jobs(con, company: str | None) -> list:
    """Job rows whose company is the SAME EMPLOYER as `company`, most advanced first.

    Compares on `applications.canon()` - the same normalization the funnel uses -
    rather than a substring match, so "EY" can never select "Morgan Stanley".
    """
    if not company:
        return []
    from .applications import canon

    # canon() returns None for blank/unparseable names, so coerce before comparing.
    target = (canon(company) or "").strip().lower()
    if not target:
        return []
    rows = con.execute("SELECT id, company, status FROM jobs ORDER BY priority DESC").fetchall()
    return [r for r in rows if (canon(r["company"] or "") or "").strip().lower() == target]


def record_email(received_at: str, sender: str, subject: str, body: str = "",
                 gmail_id: str | None = None) -> dict:
    """Classify + persist one email; bump the matching job's status if known.

    If `gmail_id` is given and already recorded, this is a no-op (returns the
    classification with `skipped=True`) so re-scanning the inbox never double-logs.
    """
    result = classify_email(subject, body, sender)
    con = connect()
    if gmail_id:
        existing = con.execute("SELECT 1 FROM tracked_emails WHERE gmail_id=? LIMIT 1",
                               (gmail_id,)).fetchone()
        if existing:
            con.close()
            return {**result, "skipped": True}
    con.execute(
        "INSERT INTO tracked_emails (received_at, sender, subject, company, category, action, gmail_id) "
        "VALUES (?,?,?,?,?,?,?)",
        (received_at, sender, subject, result["company"], result["category"], result["action"],
         gmail_id),
    )
    # Which job rows does this email actually refer to?
    #
    # This used to be an unbounded `WHERE lower(company) LIKE '%name%'` UPDATE.
    # With no anchoring and no row cap, a Codecademy promo detected as "Itr"
    # rewrote MITRE and Citrin Cooperman, and a Hilton blast detected as "EY"
    # rewrote Morgan Stanley, Berkley, Eagle Eye, ICEYE and Kearney - 46 postings
    # John never applied to were left marked 'offer', in place, unrecoverably.
    # Match on the same canonical name the applications funnel uses, and refuse
    # to touch anything if one email somehow still resolves to a wide blast.
    matches = _matching_jobs(con, result["company"])
    prior_status = matches[0]["status"] if matches else None

    if result["status_hint"] and matches:
        if len(matches) > MAX_JOBS_PER_EMAIL:
            # Almost certainly a misdetection. Record the email, change nothing.
            matches = []
        else:
            ids = [m["id"] for m in matches]
            con.execute(
                "UPDATE jobs SET status=? WHERE id IN (%s) AND status NOT IN "
                "('offer','rejected')" % ",".join("?" * len(ids)),
                (result["status_hint"], *ids),
            )
    con.commit()
    con.close()

    # Auto-log rejections so they feed the rejection-analysis report.
    if result["category"] == "rejection" and result["company"]:
        from .rejections import STATUS_TO_STAGE, log_rejection
        log_rejection(result["company"], stage=STATUS_TO_STAGE.get(prior_status or "", "ats_screen"),
                      source="inbox", rejected_on=received_at or None)
    return {**result, "skipped": False}


def triage(emails: list[dict], drop_other: bool = False) -> list[dict]:
    """Classify a batch. Each email dict: {received_at, sender, subject, body, gmail_id?}.

    When `drop_other` is set (used by bulk historical scans), emails that carry no
    recruiting signal — classified as ``other`` with no known company — are
    classified but NOT persisted, so a wide Gmail sweep never logs stray
    newsletters/marketing as tracker rows. Genuinely actionable mail (any non-other
    category, or an ``other`` from a recognized employer) is still recorded.
    """
    out = []
    for e in emails:
        # Fold every thread participant into the classification text so company
        # detection can resolve a thread by its recruiter's domain even when the
        # latest message we picked is one John sent. Stored fields are unchanged.
        body = e.get("body", "")
        parts = e.get("participants", "")
        text = f"{body}\n{parts}".strip() if parts else body
        if drop_other:
            preview = classify_email(e.get("subject", ""), text, e.get("sender", ""))
            if preview["category"] == "other" and not preview["company"]:
                out.append({**e, **preview, "skipped": True, "dropped": True})
                continue
        r = record_email(e.get("received_at", ""), e.get("sender", ""),
                         e.get("subject", ""), text, e.get("gmail_id"))
        out.append({**e, **r})
    # surface the most actionable first
    order = {"offer": 0, "interview_invite": 1, "assessment": 2, "recruiter_reply": 3,
             "rejection": 4, "other": 5}
    out.sort(key=lambda x: order.get(x["category"], 9))
    return out
