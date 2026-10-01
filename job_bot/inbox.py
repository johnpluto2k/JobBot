"""Inbox triage: classify recruiting emails into a pipeline category + next
action, and update the tracker.

Pure-logic classifier (works offline on any email text). It can be fed by a
LinkedIn/Gmail export, pasted text, or the Gmail MCP — whatever surfaces the
sender/subject/body. Updates the `tracked_emails` table and, for interview
invites, can seed the `interviews` table.
"""

from __future__ import annotations

import html
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
    ("rejection", [r"not (?:be )?moving forward", r"decided to pursue other",
                   r"will not be progressing", r"other candidates", r"won'?t be moving forward",
                   r"regret to inform", r"not (?:be )?proceeding", r"no longer (?:able to )?consider",
                   r"not (?:been )?selected", r"application incomplete",
                   r"no longer (?:being )?considered", r"do not have an appropriate",
                   r"decided to (?:progress|move forward) with other", r"position (?:has been |is )?filled",
                   r"position (?:has been )?cancelled", r"do not meet the", r"not (?:be )?able to consider",
                   r"we are sorry to let you know", r"sorry to (?:inform|let you know)",
                   # "Unfortunately" alone is everyday prose - a Deloitte campus
                   # recruiter's "Unfortunately I am not able to meet one on one"
                   # was filed as a rejection. It only counts next to application context.
                   r"\bunfortunately\b[^.]{0,160}\b(?:application|candidacy|position|role\b|"
                   r"offer|opportunit|move forward|proceed)"],
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
                    r"online screening", r"pre-interview assessment",
                    r"assessments? for completion", r"(?:skills|recorded|video) assessment"],
     "Schedule a focused block; practice the matching question type (interview --drill)."),
    # Bare r"connect" and r"\bapplied\b" used to sit in this list. "connect"
    # matches "Coinbase Connect", "connect your wallet", every newsletter
    # footer; a Coinbase Bytes crypto newsletter was filed as a recruiter reply
    # and reached the applications funnel. Sender-side cues ("talent
    # acquisition") stay, but is_noise() now runs before any of these, so an
    # event registration receipt from "IBM Talent Acquisition" is dropped first.
    ("recruiter_reply", [r"recruiter", r"talent acquisition", r"following up", r"thanks? for applying",
                         r"thank you for applying", r"thank you for your application",
                         r"received your (?:job )?application", r"application (?:has been |was )?received",
                         r"thank you for your interest", r"thank you for expressing interest",
                         r"congratulations on applying", r"application is now complete",
                         r"confirming your .{0,30}application", r"successfully (?:applied|submitted)",
                         r"thank you for completing", r"reaching out",
                         r"(?:would|'d) (?:love|like) to connect", r"connect with you",
                         r"(?:you|you've|you have) applied (?:to|for)", r"applied for the"],
     "Reply promptly; if warm, ask about timeline and next steps."),
]

CATEGORY_TO_STATUS = {
    "interview_invite": "interview",
    # An online assessment is a step of the application, not an interview: it
    # used to flip the owner's logged EY positions to 'interview'.
    "recruiter_reply": "networking",
    "rejection": "rejected",
    "offer": "offer",
}

# How far along a jobs.status is. record_email() only moves a row to a HIGHER
# rank, so an inbound receipt can't push 'applied' back to 'networking'.
STATUS_RANK = {"new": 0, "saved": 0, "networking": 1, "applied": 2, "interview": 3,
               "rejected": 4, "offer": 4}
TERMINAL_STATUSES = {"offer", "rejected"}


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
DOMAIN_NOISE = {"invalidemail", "myworkday", "workday", "echosign", "paycomonline", "msg", "tal",
                "zmail", "greenhouse-jobs",
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
                     "jpmchase.com": "JPMorgan", "amazon.jobs": "Amazon", "cbiz.com": "CBIZ",
                     "afs.com": "Accenture Federal Services", "ibm.com": "IBM"}

# Employer names not in the skills ontology but worth resolving from subject/body text.
COMPANY_HINTS = {"the scion group": "The Scion Group", "scion group": "The Scion Group",
                 "citrin cooperman": "Citrin Cooperman", "alaska airlines": "Alaska Airlines",
                 "bank of america": "Bank of America", "federal reserve board": "Federal Reserve Board",
                 "jpmorganchase": "JPMorgan", "jpmorgan chase": "JPMorgan", "goldman sachs": "Goldman Sachs",
                 "dun & bradstreet": "Dun & Bradstreet", "cerity partners": "Cerity Partners",
                 "uline": "Uline", "usaa": "USAA", "crowe": "Crowe", "kroger": "Kroger",
                 "citrin": "Citrin Cooperman", "raymond james": "Raymond James", "pepsico": "PepsiCo",
                 "mastercard": "Mastercard", "deutsche bank": "Deutsche Bank", "blackrock": "BlackRock",
                 "accenture federal services": "Accenture Federal Services",
                 "sumter advertising": "Sumter Advertising", "navy federal": "Navy Federal Credit Union"}

# Employer names that are also everyday words ("block the time", "meta tags").
# Like short aliases they only count in the subject or sender: a LinkedIn
# notification and a Mastercard promo were both filed under "Block".
AMBIGUOUS_ALIASES = {"block", "meta", "apple", "plaid", "stripe", "google", "amazon", "eaton"}

# ATS relay hosts whose first label is the employer: noreply@blackrock.tal.net
# is BlackRock, not "Tal".
EMPLOYER_SUBDOMAIN_HOSTS = {"tal.net", "myworkdayjobs.com", "icims.com", "avature.net",
                            "taleo.net", "brassring.com"}
_CANON_SLUGS = {"blackrock": "BlackRock", "morganstanley": "Morgan Stanley",
                "goldmansachs": "Goldman Sachs", "jpmorgan": "JPMorgan", "kpmg": "KPMG",
                "pwc": "PwC", "ey": "EY"}

# Account-setup / credential / newsletter mail that should NOT be tracked as a status.
NOISE_PATTERNS = [
    r"completing your form later", r"return to the form",
    r"what'?s new at", r"\bnewsletter\b",
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

# Subject-only noise. These words are common inside legitimate recruiting mail
# ("join our webinar before your interview"), so they are only trusted when they
# ARE the subject.
SUBJECT_NOISE_PATTERNS = [
    # Account / credential steps. Subject-only: "forgot your password? reset
    # your password here" sits in the footer of every Deloitte receipt, and
    # both of the owner's 2026-09-14 Deloitte applications were dropped as noise.
    r"verify your (candidate )?(email|account)", r"confirm your email", r"reset your password",
    r"password reset", r"activate your account",
    # one-time-passcode / identity confirmation (an ATS login step, not a status change)
    r"confirm your identity", r"one-?time pass\s?code", r"verification code",
    # Crypto / brokerage account chatter (Coinbase, Robinhood consumer mail).
    r"price alert", r"top mover", r"your (?:crypto )?portfolio", r"buying guide",
    # Event / webinar registration receipts. "Registration Confirmation for The
    # Consulting Edge" from IBM Talent Acquisition is an event RSVP, not an
    # application, and was landing in the funnel as one.
    r"registration confirm", r"thank you for registering", r"you(?:'re| are) (?:now )?registered",
    r"registered for", r"event (?:confirmation|registration|reminder)", r"save the date",
    r"\bwebinar\b", r"info(?:rmation)? session", r"virtual session", r"career fair",
    # Out-of-office bounces and LinkedIn social notifications carry no status;
    # "Congratulate X for starting a new position" kept Grant Thornton looking
    # recently active.
    r"^(?:re: )?automatic reply", r"^out of (?:the )?office", r"^auto[- ]?reply",
    r"reacted to (?:this|your) post", r"^congratulate .*(?:new position|anniversary)",
    r"one more step to get started", r"talent community opt.?in",
]

# Sender local-parts that are marketing/newsletter streams, never a recruiter.
# Checked against the address only, so "Coinbase Bytes <newsletter@mail.coinbase.com>"
# is noise even when the subject carries no newsletter wording.
NEWSLETTER_SENDERS = {"newsletter", "newsletters", "news", "marketing", "promo", "promotions",
                      "digest", "bytes", "insights", "community", "events", "event", "webinars",
                      "updates-noreply", "notifications-noreply", "messages-noreply",
                      "invitations", "jobalerts-noreply"}


def is_noise(subject: str, body: str = "", sender: str = "") -> bool:
    t = f"{subject} {body}".lower()
    if any(re.search(p, t) for p in NOISE_PATTERNS):
        return True
    s = (subject or "").lower()
    if any(re.search(p, s) for p in SUBJECT_NOISE_PATTERNS):
        return True
    if m := re.search(r"([a-z0-9_\-.+]+)@", sender.lower()):
        local = m.group(1).split("+")[0]
        if local in NEWSLETTER_SENDERS or local.startswith("newsletter"):
            return True
    return False


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
        field = strong if (len(key) <= SHORT_ALIAS_MAX or key in AMBIGUOUS_ALIASES) else hay
        if re.search(rf"(?<![a-z]){re.escape(key)}(?![a-z])", field):
            return disp
    # 2. Sender host maps cleanly to one employer (relay/ATS domains).
    host = sender.lower().split("@")[-1].strip().strip(">").rstrip(".")
    for frag, disp in SENDER_DOMAIN_MAP.items():
        if frag in host:
            return disp
    labels = [x for x in host.split(".") if x]
    if len(labels) >= 3 and ".".join(labels[-2:]) in EMPLOYER_SUBDOMAIN_HOSTS:
        sub = labels[0]
        if sub not in GENERIC_PREFIXES and len(sub) >= 2:
            return _CANON_SLUGS.get(sub, sub.capitalize())
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


# Application receipts. A message matching one of these proves the owner
# applied, whatever else it goes on to ask ("...next, complete an assessment").
# Patterns starting with ^ are tested against the subject alone.
APPLIED_PATTERNS = [
    r"thank(?:s| you) for (?:applying|your application|submitting (?:an |your )?application)",
    r"application (?:has been |was )?(?:received|submitted)",
    r"(?:we(?:['’]ve| have) )?received your (?:job )?application",
    r"application is (?:now )?complete", r"successfully (?:applied|submitted)",
    r"confirming your .{0,30}application", r"congratulations on applying",
    r"you(?:['’]ve| have) applied\b", r"excited to see that you have applied",
    r"^[\w&.' ]{2,40} application\s*[-\u2013:|]\s*\S",  # "KPMG Application - <role>"
    r"^your recent job application for",
]

# Role title inside a receipt / status email. First match wins.
_ROLE_PATTERNS = [
    r"application for the role:?\s*(?P<r>[^\n(]{3,140}?)\s*(?:\(|\n|$|\s\.(?:\s|$))",
    r"for the position of\s+(?P<r>[^\n]{3,140}?)(?:,\s*\d{4,}|\.\s|\n|$)",
    r"applying to the role of\s+(?P<r>[^\n]{3,140}?)(?:\s*-\s*\d{4,})?\s+at\b",
    r"applying (?:for|to) the (?:\d{4,} )?(?P<r>[^\n]{3,140}?) (?:position|role)\b",
    r"applying (?:for|to) the (?:\d{4,} )?(?P<r>[^\n]{3,140}?) at [A-Z]",
    r"applied to our (?P<r>[^\n.]{3,100}?\bprogram)\b",
    r"applied for the (?P<r>[^\n]{3,140}?) (?:position|role)\b",
    r"interest in the (?P<r>[^\n]{3,140}?) (?:position|role)\b",
    r"interest in (?P<r>[^\n.]{0,60}\b(?:program|internship|intern)\b[^\n.]{0,60}?\d{4})",
    r"^[\w&.' ]{2,40} application\s*[-\u2013:|]\s*(?P<r>[^\n]{3,140}?)(?:\s+position\b|,\s*job\s*#|$)",
    r"^your recent job application for\s+(?P<r>[^\n]{3,140}?)(?:\s+-\s+\d{3,})?$",
    r"^[\w&.' ]{2,20}'s (?P<r>[^\n]{3,140}?) - thank you for applying",
    r"^you have successfully submitted your .{0,20}application - (?P<r>[^\n]{3,140})$",
]
_ROLE_REJECT = re.compile(r"(?i)^(?:(?:our|this|the|a|your) (?:organization|company|role|position|team)|next steps?|update|status)$")


def strip_quoted(body: str) -> str:
    """Drop the quoted history under a reply so an old message can't set the
    status of a new one ("> Unfortunately ..." from three emails ago)."""
    if not body:
        return ""
    body = html.unescape(body).replace("\xa0", " ")
    cut = re.split(r"\n\s*(?:On .{5,160}wrote:|-{2,}\s*Original Message|\*?From:\*?\s.{1,160}\n\s*\*?Sent:)",
                   body, maxsplit=1)[0]
    return "\n".join(line for line in cut.splitlines() if not line.lstrip().startswith(">"))


def extract_role(subject: str, body: str = "") -> str | None:
    """Best-effort role title named in an application email."""
    for text, is_subject in ((subject or "", True), ((body or "")[:2000], False)):
        flat = re.sub(r"[ \t\r]+", " ", text).strip()
        for pat in _ROLE_PATTERNS:
            if pat.startswith("^") and not is_subject:
                continue
            m = re.search(pat, flat, re.I | re.M)
            if not m:
                continue
            role = m.group("r").strip(" -\u2013|:,.\"'")
            role = re.sub(r"\s+(?:position|role)$", "", role, flags=re.I).strip()
            if 3 <= len(role) <= 140 and not _ROLE_REJECT.match(role):
                return role
    return None


def _first_signal(text: str) -> tuple[str, str] | None:
    for cat, patterns, act in SIGNALS:
        if any(re.search(p, text, re.I) for p in patterns):
            return cat, act
    return None


_RECEIPT_ACTION = "Application received; nothing to do until they respond."


def classify_email(subject: str, body: str = "", sender: str = "") -> dict:
    body = strip_quoted(body)
    subj = (subject or "").strip()
    text = f"{subj}\n{body}"
    category, action = "other", "Review and file; no clear action."
    applied = False
    # Noise first. gmail_sync already pre-filters with is_noise(), but every
    # other caller (CLI triage, tests, pasted text) reached SIGNALS directly and
    # newsletters could still earn a recruiting label.
    if not is_noise(subject, body, sender):
        applied = any(re.search(p, subj if p.startswith("^") else text, re.I | re.M)
                      for p in APPLIED_PATTERNS)
        # The subject is the sender's own summary of the message, so a real
        # signal there wins over the body. IBM's "Action Required: IBM
        # Assessments for completion" was filed as a rejection off body text.
        hit = _first_signal(subj)
        if hit and hit[0] == "recruiter_reply":
            hit = None  # weakest label: let a stronger body signal through
        if not hit:
            body_hit = _first_signal(text)
            # "Congratulations on applying ... we look forward to speaking" is a
            # receipt, not an invitation (KPMG, Sept 2026).
            if body_hit and body_hit[0] == "interview_invite" and applied:
                body_hit = None
            hit = body_hit
        if hit:
            category, action = hit
        elif applied:
            category, action = "recruiter_reply", _RECEIPT_ACTION
        if category in ("rejection", "offer"):
            applied = False
    return {
        "category": category,
        "action": action,
        "company": detect_company(f"{subject} {body}", sender, subject=subject),
        "status_hint": CATEGORY_TO_STATUS.get(category),
        "applied": applied,
        "role": extract_role(subject, body) if category != "other" else None,
    }


_ROLE_STOP = {"the", "a", "an", "and", "of", "for", "to", "in", "at", "with", "position", "role",
              "program", "usa", "us", "req", "job", "summer", "fall", "spring", "winter"}


def _role_tokens(title: str | None) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (title or "").lower())
    return {w for w in words if w not in _ROLE_STOP and len(w) > 1
            and not (w.isdigit() and len(w) != 4)}


def same_role(a: str | None, b: str | None) -> bool:
    """Loose title match: "USA - Consulting - Technology Consulting - Staff (Req
    1741471)" and "USA - Consulting - Technology Consulting - Staff" are one role."""
    if not a or not b:
        return False
    ta, tb = _role_tokens(a), _role_tokens(b)
    if not ta or not tb:
        return False
    # Same requisition number on both sides settles it.
    ra, rb = set(re.findall(r"\b\d{5,}\b", a)), set(re.findall(r"\b\d{5,}\b", b))
    if ra and rb:
        return bool(ra & rb)
    # Compare the title itself, not the location/program tail after the first
    # comma, pipe or parenthesis: "Program Management Analyst I, Launch Program
    # 2027 – St. Louis" and "Technology Risk Analyst I, Launch Program 2027 –
    # St. Louis" share most words and are different jobs.
    ha = _role_tokens(re.split(r"[,|(]", a)[0]) or ta
    hb = _role_tokens(re.split(r"[,|(]", b)[0]) or tb
    small, big = sorted((ha, hb), key=len)
    return len(small & big) / len(small) >= 0.8


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
    rows = con.execute("SELECT id, company, title, status FROM jobs ORDER BY priority DESC").fetchall()
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
        "INSERT INTO tracked_emails (received_at, sender, subject, company, category, action, "
        "gmail_id, role, applied) VALUES (?,?,?,?,?,?,?,?,?)",
        (received_at, sender, subject, result["company"], result["category"], result["action"],
         gmail_id, result["role"], int(result["applied"])),
    )
    # Which job rows does this email actually refer to?
    #
    # This used to be an unbounded `WHERE lower(company) LIKE '%name%'` UPDATE.
    # With no anchoring and no row cap, a Codecademy promo detected as "Itr"
    # rewrote MITRE and Citrin Cooperman, and a Hilton blast detected as "EY"
    # rewrote Morgan Stanley, Berkley, Eagle Eye, ICEYE and Kearney - 46 postings
    # the owner never applied to were left marked 'offer', in place, unrecoverably.
    # Match on the same canonical name the applications funnel uses, and refuse
    # to touch anything if one email somehow still resolves to a wide blast.
    matches = _matching_jobs(con, result["company"])
    if result["role"] and matches:
        # The email names a position: only that position moves. A BlackRock
        # rejection for a 2026 internship must not close a 2027 application.
        matches = [m for m in matches if same_role(m["title"], result["role"])]
    prior_status = matches[0]["status"] if matches else None

    if result["status_hint"] and matches:
        if len(matches) > MAX_JOBS_PER_EMAIL:
            # Almost certainly a misdetection. Record the email, change nothing.
            matches = []
        else:
            # Only ever move a job FORWARD. A "thank you for applying" receipt
            # hints 'networking', which used to overwrite the 'applied' the owner had
            # just logged through intake - a downgrade in the tracker UI.
            hint_rank = STATUS_RANK.get(result["status_hint"], 0)
            ids = [m["id"] for m in matches
                   if STATUS_RANK.get(m["status"] or "new", 0) < hint_rank
                   and (m["status"] or "") not in TERMINAL_STATUSES]
            if ids:
                con.execute(
                    "UPDATE jobs SET status=? WHERE id IN (%s)" % ",".join("?" * len(ids)),
                    (result["status_hint"], *ids),
                )
    con.commit()
    con.close()

    # Auto-log rejections so they feed the rejection-analysis report.
    if result["category"] == "rejection" and result["company"]:
        from .rejections import STATUS_TO_STAGE, log_rejection
        log_rejection(result["company"], role_title=result["role"],
                      stage=STATUS_TO_STAGE.get(prior_status or "", "ats_screen"),
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
        # latest message we picked is one the owner sent. Stored fields are unchanged.
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
