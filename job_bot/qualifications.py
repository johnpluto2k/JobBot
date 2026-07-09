"""Qualification filtering — detect and penalize cert/degree gaps.

When a JD explicitly requires a certification or degree John doesn't have,
down-rank the job and log the gap. This prevents applications to roles that
have a hard blocker in the candidate profile.

Core logic:
1. Extract required certs/degrees from JD text (regex patterns + NLP)
2. Check candidate's master profile for matching credentials
3. Return: gap list + penalty score for ranking
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# Known certifications John has or is pursuing (from master_profile.json)
JOHN_CERTS = {
    "CPA",  # CPA Eligibility (Expected) — not yet obtained
    # Add as John pursues more: "Security+", "CMMC RP", etc.
}

# Degrees John has (from master_profile.json)
JOHN_DEGREES = {
    "Bachelor of Science",
    "BS",
    "B.S.",
    "Accounting",
    "Information Science",
}

# Common hard-requirement patterns (order: high → low confidence)
CERT_PATTERNS = {
    # Accounting/Finance
    "CPA": r"(CPA|Certified Public Accountant)",
    "CIA": r"(CIA|Certified Internal Auditor)",
    "CFA": r"(CFA|Chartered Financial Analyst)",
    "CISSP": r"(CISSP|Certified Information Systems Security Professional)",
    "Security+": r"(Security\+|Security Plus|CompTIA Security)",
    "CMMC RP": r"(CMMC\s+(?:Registered\s+)?Practitioner|CMMC RP|Cybersecurity Maturity Model)",
    "NIST": r"(NIST|NIST\s+SP\s+800-171|NIST Certified)",
    "CEH": r"(CEH|Certified Ethical Hacker)",
    "OSCP": r"(OSCP|Offensive Security Certified Professional)",
    "AWS": r"(AWS|Amazon Web Services|AWS Certified)",
    "Azure": r"(Azure|Microsoft Azure|Azure Certified)",
    "GCP": r"(GCP|Google Cloud|Google Cloud Certified)",
    "PMP": r"(PMP|Project Management Professional)",
    "Six Sigma": r"(Six Sigma|Black Belt|Green Belt)",
}

DEGREE_PATTERNS = {
    "Bachelor's": r"\b(Bachelor('?s)?|B\.?S\.?|BA|BS)\b",
    "Master's": r"\b(Master('?s)?|MBA|M\.?A\.?|M\.?S\.?|MSc)\b",
    "PhD": r"\b(PhD|Doctorate|D\.?Phil)\b",
    "Associate's": r"\b(Associate('?s)?|A\.?S\.?|A\.?A\.?)\b",
}

FIELD_PATTERNS = {
    "Computer Science": r"\b(Computer Science|CS|Software Engineering)\b",
    "Data Science": r"\b(Data Science|Data Analytics|Analytics)\b",
    "Finance": r"\b(Finance|Financial|Accounting)\b",
    "Information Technology": r"\b(Information Technology|IT|Computer Engineering)\b",
    "Business Administration": r"\b(Business Administration|MBA|Business)\b",
}


def extract_required_certs(text: str) -> dict[str, list[str]]:
    """Extract certifications mentioned as required/preferred from JD text.

    Returns: { "required": ["cert1", "cert2"], "preferred": ["cert3"] }
    """
    if not text:
        return {"required": [], "preferred": []}

    required = []
    preferred = []

    # Look for explicit "required" and "preferred" language AND standalone sections
    req_block = _extract_block(text, r"required.*?qualifications?", 1000)
    pref_block = _extract_block(text, r"preferred.*?qualifications?", 1000)
    req_certs_block = _extract_block(text, r"required.*?certifications?", 1000)
    cert_section = _extract_block(text, r"^.*?certifications?.*?$", 1000, multiline=True)

    # Check if words like "preferred" or "required" appear near cert mentions
    for cert_name, pattern in CERT_PATTERNS.items():
        # Check required sections
        if (re.search(pattern, req_block, re.I) or
            re.search(pattern, req_certs_block, re.I) or
            (re.search(pattern, cert_section, re.I) and
             re.search(r"required", cert_section[:200], re.I))):
            required.append(cert_name)
        # Check preferred sections
        elif (re.search(pattern, pref_block, re.I) or
              (re.search(pattern, cert_section, re.I) and
               re.search(r"preferred", cert_section[:200], re.I))):
            preferred.append(cert_name)
        # If cert is mentioned anywhere in cert section and we haven't classified it
        elif re.search(pattern, cert_section, re.I):
            # Default to preferred if mentioned but not explicitly required
            preferred.append(cert_name)

    return {"required": list(set(required)), "preferred": list(set(preferred))}


def extract_required_degrees(text: str) -> dict[str, list[str]]:
    """Extract degree requirements from JD text.

    Returns: { "required": ["Bachelor's"], "preferred": ["Master's"] }
    """
    if not text:
        return {"required": [], "preferred": []}

    required = []
    preferred = []

    req_block = _extract_block(text, r"required.*?education?", 1000)
    pref_block = _extract_block(text, r"preferred.*?education?", 1000)
    req_degree_block = _extract_block(text, r"required.*?degree", 1000)

    for degree_name, pattern in DEGREE_PATTERNS.items():
        if re.search(pattern, req_block, re.I) or re.search(pattern, req_degree_block, re.I):
            required.append(degree_name)
        elif re.search(pattern, pref_block, re.I):
            preferred.append(degree_name)

    return {"required": list(set(required)), "preferred": list(set(preferred))}


def check_qualifications(jd_text: str) -> dict:
    """Analyze a JD for qualification gaps against John's profile.

    Returns:
    {
        "certs_required": ["Security+", "CMMC RP"],
        "certs_missing": ["Security+", "CMMC RP"],
        "certs_preferred": ["AWS"],
        "degrees_required": ["Bachelor's"],
        "degrees_gap": None,  # None = no gap, or gap description
        "penalty_score": 0.0,  # Multiply by priority to down-rank
        "verdict": "PASS",  # PASS, WARN, BLOCK
    }
    """
    certs = extract_required_certs(jd_text)
    degrees = extract_required_degrees(jd_text)

    # Check cert gaps
    certs_missing = [c for c in certs["required"] if c not in JOHN_CERTS]
    certs_preferred_missing = [c for c in certs["preferred"] if c not in JOHN_CERTS]

    # Check degree gaps (simple: John has a Bachelor's in Accounting/Info Science)
    degree_gap = None
    if "Master's" in degrees["required"]:
        degree_gap = "JD requires Master's degree; John has Bachelor's (5+ years exp may substitute)"
    elif "PhD" in degrees["required"]:
        degree_gap = "JD requires PhD; John has Bachelor's"

    # Scoring: cert gap = -1 per required cert; degree gap = -2
    penalty = len(certs_missing) * 1.0 + len(certs_preferred_missing) * 0.25
    if degree_gap:
        penalty += 2.0

    # Verdict: block if multiple hard certs missing, warn if one, pass if none
    verdict = "PASS"
    if len(certs_missing) >= 2:
        verdict = "BLOCK"
    elif len(certs_missing) == 1 or degree_gap:
        verdict = "WARN"

    return {
        "certs_required": certs["required"],
        "certs_missing": certs_missing,
        "certs_preferred": certs["preferred"],
        "certs_preferred_missing": certs_preferred_missing,
        "degrees_required": degrees["required"],
        "degree_gap": degree_gap,
        "penalty_score": penalty,
        "verdict": verdict,
    }


def _extract_block(text: str, marker_pattern: str, window: int, multiline: bool = False) -> str:
    """Extract a text block starting at marker_pattern for up to window chars."""
    if not text:
        return ""
    flags = re.I | re.M if multiline else re.I
    m = re.search(marker_pattern, text, flags)
    if m:
        start = m.start()
        return text[start : start + window]
    return ""


# For testing: load profile and check a known JD
if __name__ == "__main__":
    from pathlib import Path

    # Example: check the business JD (Compliance Analyst)
    jd_path = Path(
        r"C:\Users\yohan\AppData\Local\Temp\claude\C--ClaudeProjects-Job-Bot\c7c15a21-4cb0-4e39-a947-60cb3ab0cd86\scratchpad\business_jd.txt"
    )
    if jd_path.exists():
        with open(jd_path) as f:
            jd_text = f.read()
        result = check_qualifications(jd_text)
        print("Compliance Analyst JD:")
        print(f"  Certs required: {result['certs_required']}")
        print(f"  Certs missing: {result['certs_missing']}")
        print(f"  Degree gap: {result['degree_gap']}")
        print(f"  Penalty score: {result['penalty_score']}")
        print(f"  Verdict: {result['verdict']}")
