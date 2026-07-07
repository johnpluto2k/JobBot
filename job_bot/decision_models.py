"""Pydantic models for Phase 3: the network-vs-cold-apply decision."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Verdict = Literal["cold_apply", "apply_and_network", "network_first"]


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class ConnectionMatch(_Base):
    name: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    relationship: str = "alum"
    warmth: float = Field(ge=0.0, le=1.0, default=0.3)
    notes: Optional[str] = None


class Factors(_Base):
    competition: float = Field(ge=0.0, le=1.0, default=0.0)
    resume_strength: float = Field(ge=0.0, le=1.0, default=0.0)
    connection_strength: float = Field(ge=0.0, le=1.0, default=0.0)
    recruiter_available: bool = False
    days_since_posting: Optional[int] = None
    competition_notes: list[str] = Field(default_factory=list)


class DecisionReport(_Base):
    verdict: Verdict
    verdict_label: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    rationale: str = ""
    factors: Factors = Field(default_factory=Factors)

    top_contacts: list[ConnectionMatch] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)

    company: Optional[str] = None
    title: Optional[str] = None
    ats_score: Optional[float] = None
    generated_at: datetime = Field(default_factory=datetime.now)


VERDICT_LABELS: dict[str, str] = {
    "cold_apply": "🟢 Cold apply — strong enough resume, manageable competition.",
    "apply_and_network": "🟡 Apply + network in parallel — submit now, reach out simultaneously.",
    "network_first": "🔴 Network first — high competition and real connections exist; "
                     "secure a referral before applying.",
}
