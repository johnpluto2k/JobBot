"""Pydantic models for Phase 7: interview prep + mock interviews."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class Story(_Base):
    """A STAR+ story extracted from real experience."""
    title: str
    source: Optional[str] = None
    competencies: list[str] = Field(default_factory=list)
    situation: str = ""
    task: str = ""
    action: str = ""
    result: str = ""
    reflection: str = ""        # +Reflection (what you learned)
    connection: str = ""        # +Connection (link to the role)
    quantified: bool = False


class Question(_Base):
    text: str
    qtype: str                  # behavioral | fit | technical | case | hirevue | curveball | questions
    firm_types: list[str] = Field(default_factory=list)
    hint: Optional[str] = None
    competency: Optional[str] = None


class AnswerScore(_Base):
    score: float = Field(ge=0.0, le=100.0, default=0.0)
    band: str = ""
    has_situation: bool = False
    has_task: bool = False
    has_action: bool = False
    has_result: bool = False
    quantified: bool = False
    ownership: float = 0.0       # I-vs-we ratio
    word_count: int = 0
    filler_count: int = 0
    strengths: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
