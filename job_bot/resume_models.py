"""Pydantic models for Phase 4: tailored resume output."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class TailoredRole(_Base):
    role: Optional[str] = None
    organization: Optional[str] = None
    location: Optional[str] = None
    dates: Optional[str] = None
    bullets: list[str] = Field(default_factory=list)


class TailoredEducation(_Base):
    school: Optional[str] = None
    degree: Optional[str] = None
    secondary: Optional[str] = None
    gpa: Optional[float] = None
    graduation_date: Optional[str] = None
    coursework: list[str] = Field(default_factory=list)


class TailoredResume(_Base):
    name: Optional[str] = None
    contact_line: str = ""
    summary: Optional[str] = None

    education: list[TailoredEducation] = Field(default_factory=list)
    experience: list[TailoredRole] = Field(default_factory=list)
    leadership: list[TailoredRole] = Field(default_factory=list)
    projects: list[TailoredRole] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)

    # context
    target_title: Optional[str] = None
    target_company: Optional[str] = None
