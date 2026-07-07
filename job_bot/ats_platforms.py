"""ATS platform detection and platform-specific scoring behaviour.

Different ATS platforms parse and rank resumes differently. This encodes the
practical differences (informed by the ats-screener project and the master
plan's hiring intelligence) as scoring weights + candidate-facing tips.

Each platform defines relative weights for the four subscores; they are
normalized at scoring time, so only their ratios matter.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .skills_ontology import COMPANY_ATS


@dataclass(frozen=True)
class Platform:
    name: str
    # relative weights
    w_keyword: float
    w_title: float
    w_quantification: float
    w_similarity: float
    exact_match: bool  # True = literal keyword matching matters a lot (older ATS)
    summary: str
    tips: list[str] = field(default_factory=list)


PLATFORMS: dict[str, Platform] = {
    "Workday": Platform(
        name="Workday",
        w_keyword=0.40, w_title=0.20, w_quantification=0.15, w_similarity=0.25,
        exact_match=False,
        summary="Structured-field parser; weights keyword match and title, decent semantic tolerance.",
        tips=[
            "Mirror the exact job title in your resume header or summary line.",
            "Fill keywords into the Experience section — Workday keys off structured roles.",
            "Avoid tables/columns; Workday's parser drops text inside them.",
        ],
    ),
    "Taleo": Platform(
        name="Taleo",
        w_keyword=0.55, w_title=0.20, w_quantification=0.10, w_similarity=0.15,
        exact_match=True,
        summary="Older, literal keyword matcher; exact phrasing matters, low semantic tolerance.",
        tips=[
            "Use the JD's exact wording — Taleo does little synonym matching.",
            "Spell out acronyms AND include the acronym (e.g. 'Sarbanes-Oxley (SOX)').",
            "Use a plain single-column .docx; Taleo mangles complex formatting.",
        ],
    ),
    "iCIMS": Platform(
        name="iCIMS",
        w_keyword=0.45, w_title=0.20, w_quantification=0.10, w_similarity=0.25,
        exact_match=True,
        summary="Keyword + boolean matching; recruiter-driven search, so coverage matters.",
        tips=[
            "Cover both required and preferred keywords — recruiters boolean-search iCIMS.",
            "Include a Skills section with exact technologies named in the JD.",
        ],
    ),
    "Greenhouse": Platform(
        name="Greenhouse",
        w_keyword=0.30, w_title=0.20, w_quantification=0.20, w_similarity=0.30,
        exact_match=False,
        summary="Modern parser, strong semantic handling; impact and relevance weigh heavily.",
        tips=[
            "Lead with quantified impact — Greenhouse-using teams read for results.",
            "Synonyms are fine; you don't need to match phrasing exactly.",
        ],
    ),
    "Lever": Platform(
        name="Lever",
        w_keyword=0.30, w_title=0.20, w_quantification=0.20, w_similarity=0.30,
        exact_match=False,
        summary="Modern, lenient parser; relevance and outcomes over keyword stuffing.",
        tips=[
            "Focus on a tight, relevant story over keyword density.",
            "Quantified bullets and a clear title alignment carry the most weight.",
        ],
    ),
    "SuccessFactors": Platform(
        name="SuccessFactors",
        w_keyword=0.50, w_title=0.20, w_quantification=0.10, w_similarity=0.20,
        exact_match=True,
        summary="SAP ATS; strict, keyword-heavy, conservative parsing.",
        tips=[
            "Match keywords literally and keep formatting extremely simple.",
            "Include an explicit Skills section; SuccessFactors indexes it directly.",
        ],
    ),
    "Generic": Platform(
        name="Generic",
        w_keyword=0.40, w_title=0.20, w_quantification=0.15, w_similarity=0.25,
        exact_match=False,
        summary="Unknown ATS; balanced default weighting.",
        tips=[
            "Keep formatting ATS-clean: one column, standard fonts, no graphics.",
            "Cover the JD's required keywords explicitly in Experience and Skills.",
        ],
    ),
}

# URL fragment -> platform
URL_SIGNATURES: dict[str, str] = {
    "myworkdayjobs.com": "Workday",
    "workday": "Workday",
    "taleo.net": "Taleo",
    "tbe.taleo.net": "Taleo",
    "icims.com": "iCIMS",
    "boards.greenhouse.io": "Greenhouse",
    "greenhouse.io": "Greenhouse",
    "jobs.lever.co": "Lever",
    "lever.co": "Lever",
    "successfactors": "SuccessFactors",
    "sapsf.com": "SuccessFactors",
}


def get_platform(name: str | None) -> Platform:
    return PLATFORMS.get(name or "Generic", PLATFORMS["Generic"])


def detect_platform(url: str | None, text: str, company: str | None) -> tuple[str, str]:
    """Return (platform_name, how_detected)."""
    haystacks = [h for h in (url, text) if h]
    for hay in haystacks:
        low = hay.lower()
        for sig, platform in URL_SIGNATURES.items():
            if sig in low:
                return platform, f"matched '{sig}' in {'URL' if hay is url else 'posting text'}"

    if company:
        clow = company.lower()
        for known, platform in COMPANY_ATS.items():
            if known in clow:
                return platform, f"known ATS for {company}"

    return "Generic", "no ATS signature found (using balanced default)"
