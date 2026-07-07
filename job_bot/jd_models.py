"""Pydantic models for Phase 2: job postings and ATS score reports."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Importance = Literal["required", "preferred"]


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class JobPosting(_Base):
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    source_url: Optional[str] = None

    role_type: Optional[str] = None
    seniority: Optional[str] = Field(default=None, description="intern | entry | mid | senior")
    market_tier: Optional[str] = None
    market_tier_num: Optional[int] = None
    remote: bool = False

    ats_platform: Optional[str] = None
    ats_detection: Optional[str] = Field(default=None, description="how the ATS was identified")

    gpa_cutoff: Optional[float] = None
    years_experience: Optional[int] = None

    # canonical skill -> importance
    required_keywords: list[str] = Field(default_factory=list)
    preferred_keywords: list[str] = Field(default_factory=list)
    all_keywords: list[str] = Field(default_factory=list)

    raw_text: str = ""


class KeywordHit(_Base):
    keyword: str
    importance: Importance = "required"
    present: bool = False
    where: Optional[str] = Field(default=None, description="where in the profile it was found")


class GapItem(_Base):
    keyword: str
    importance: Importance
    impact: float = Field(ge=0.0, le=1.0, description="how much closing this lifts the score")
    suggested_section: Optional[str] = None
    suggested_target: Optional[str] = Field(
        default=None, description="which experience/project to add it to"
    )
    action: str = ""


class SubScores(_Base):
    keyword_coverage: float = 0.0
    title_alignment: float = 0.0
    quantification: float = 0.0
    content_similarity: float = 0.0


class ATSScoreReport(_Base):
    overall_score: float = Field(ge=0.0, le=100.0, default=0.0)
    verdict: str = ""
    subscores: SubScores = Field(default_factory=SubScores)

    ats_platform: Optional[str] = None
    platform_weighting: Optional[str] = None
    platform_tips: list[str] = Field(default_factory=list)

    matched_keywords: list[KeywordHit] = Field(default_factory=list)
    missing_keywords: list[KeywordHit] = Field(default_factory=list)
    gap_analysis: list[GapItem] = Field(default_factory=list)

    quantification_note: str = ""
    job: Optional[JobPosting] = None
    generated_at: datetime = Field(default_factory=datetime.now)
