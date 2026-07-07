"""Pydantic v2 master profile schema.

This is the structured "source of truth" the rest of the system references
(reverse ATS scoring, tailoring engine, networking, interview prep). Every
field is optional-friendly so partial extraction from messy documents never
crashes the pipeline.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SkillCategory = Literal["technical", "financial", "analytical", "soft", "language", "other"]


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class PersonalInfo(_Base):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = Field(default=None, description="City, State only")
    linkedin: Optional[str] = None
    github: Optional[str] = None
    website: Optional[str] = None


class Education(_Base):
    school: Optional[str] = None
    degree: Optional[str] = Field(default=None, description="e.g. B.S. Accounting")
    major: Optional[str] = None
    secondary_major: Optional[str] = None
    gpa: Optional[float] = None
    graduation_date: Optional[str] = Field(default=None, description="e.g. 'May 2027'")
    relevant_coursework: list[str] = Field(default_factory=list)
    honors: list[str] = Field(default_factory=list)


class Bullet(_Base):
    """A single accomplishment bullet, ideally in Google XYZ format:
    'Accomplished [X] as measured by [Y] by doing [Z]'."""

    text: str
    keyword_tags: list[str] = Field(
        default_factory=list, description="Skills/keywords this bullet evidences"
    )
    quantified: bool = Field(
        default=False, description="True if the bullet contains a metric/number"
    )
    strength_score: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Relative impact, used by the selection engine"
    )


class Experience(_Base):
    role: Optional[str] = None
    organization: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = Field(default=None, description="'Present' for current roles")
    is_current: bool = False
    bullets: list[Bullet] = Field(default_factory=list)
    keyword_tags: list[str] = Field(default_factory=list)


class Leadership(_Base):
    role: Optional[str] = None
    organization: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    bullets: list[Bullet] = Field(default_factory=list)
    competencies: list[str] = Field(
        default_factory=list, description="e.g. Leadership, Teamwork, Networking"
    )


class Project(_Base):
    name: Optional[str] = None
    description: Optional[str] = None
    technologies: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)
    bullets: list[Bullet] = Field(default_factory=list)
    url: Optional[str] = None
    competencies: list[str] = Field(default_factory=list)


class SkillGroup(_Base):
    category: SkillCategory = "other"
    skills: list[str] = Field(default_factory=list)


class Targets(_Base):
    """Career direction — seeded from the master plan, refined over time."""

    target_roles: list[str] = Field(default_factory=list)
    target_firms: list[str] = Field(default_factory=list)
    target_markets: list[str] = Field(default_factory=list)
    personas: list[str] = Field(
        default_factory=list,
        description="Which 'version of you' to present, e.g. audit / analytics / fintech",
    )


class SourceDoc(_Base):
    path: str
    filename: str
    doc_type: Optional[str] = Field(
        default=None, description="resume | cover_letter | transcript | project | other"
    )
    char_count: int = 0
    parser: Optional[str] = None


class MasterProfile(_Base):
    """Top-level structured profile — the system's source of truth."""

    personal: PersonalInfo = Field(default_factory=PersonalInfo)
    education: list[Education] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    leadership: list[Leadership] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    skills: list[SkillGroup] = Field(default_factory=list)
    targets: Targets = Field(default_factory=Targets)
    certifications: list[str] = Field(default_factory=list)
    summary: Optional[str] = None

    source_documents: list[SourceDoc] = Field(default_factory=list)
    extraction_method: Optional[str] = Field(
        default=None, description="'llm' or 'heuristic'"
    )
    generated_at: datetime = Field(default_factory=datetime.now)
    schema_version: str = "1.0"
