from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Status(str, Enum):
    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"
    NEEDS_MORE_INFO = "needs_more_info"


# Controlled vocabulary for special family circumstances. The chat agent must
# map what a student says onto these keys; schemes may only use these keys.
CIRCUMSTANCES = {
    "orphan",
    "parent_died_covid",
    "ward_of_armed_forces_martyr",
    "ward_of_cpf_martyr",
    "parent_critical_illness",
    "parent_died_or_severely_disabled_in_accident",
}


class StudentProfile(BaseModel):
    """What we know about the student. Every field is optional because the
    agent collects them over a conversation. None means 'not yet known'."""

    state: Optional[str] = None  # state of domicile, e.g. "Jharkhand"
    category: Optional[str] = None  # General / OBC / SC / ST / EWS
    gender: Optional[str] = None  # female / male / other
    annual_family_income: Optional[int] = None  # rupees per year
    level: Optional[str] = None  # School / Diploma / UG / PG
    course: Optional[str] = None  # e.g. "BTech"
    last_exam_percentage: Optional[float] = None  # 0-100
    has_disability: Optional[bool] = None
    is_minority: Optional[bool] = None
    # None = not asked yet; [] = asked, none apply; else keys from CIRCUMSTANCES
    circumstances: Optional[list[str]] = None


class Scheme(BaseModel):
    """One scholarship or scheme. A criterion left as None means
    'no restriction' for that criterion."""

    id: str
    name: str
    provider: str
    official_url: str

    # Eligibility criteria (None = no restriction)
    eligible_categories: Optional[list[str]] = None
    max_family_income: Optional[int] = None
    min_percentage: Optional[float] = None
    levels: Optional[list[str]] = None
    courses: Optional[list[str]] = None
    states: Optional[list[str]] = None
    gender: Optional[str] = None
    requires_disability: bool = False
    requires_minority: bool = False
    # Student must have AT LEAST ONE of these circumstances (None = no rule)
    required_circumstances_any: Optional[list[str]] = None

    @field_validator("required_circumstances_any")
    @classmethod
    def _check_circumstances(cls, v):
        if v is not None:
            unknown = set(v) - CIRCUMSTANCES
            if unknown:
                raise ValueError(
                    f"unknown circumstance(s) {sorted(unknown)}; "
                    f"allowed: {sorted(CIRCUMSTANCES)}"
                )
        return v

    # Rules the engine cannot verify from chat answers (e.g. "above 80th
    # percentile in your board", "not receiving another scholarship").
    # Shown to the student as "you must also confirm these".
    unchecked_criteria: list[str] = Field(default_factory=list)

    # Information shown to the student
    benefit: Optional[str] = None
    deadline: Optional[date] = None
    documents: list[str] = Field(default_factory=list)

    # Provenance (required for citations)
    source_text: str
    last_verified: Optional[date] = None


class EligibilityResult(BaseModel):
    scheme_id: str
    status: Status
    reasons: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    unchecked_criteria: list[str] = Field(default_factory=list)
    deadline_passed: bool = False
