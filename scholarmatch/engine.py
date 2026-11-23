"""Deterministic eligibility engine. No LLM involved.

Rules:
- If any criterion definitely fails          -> NOT_ELIGIBLE
- else if any needed field is unknown        -> NEEDS_MORE_INFO
- else                                       -> ELIGIBLE
Failing always wins over missing: if the student already fails one
criterion, there is no point asking more questions.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from .models import EligibilityResult, Scheme, Status, StudentProfile


def _norm(value: str) -> str:
    return value.strip().lower()


def _in_list(value: str, options: list[str]) -> bool:
    return _norm(value) in {_norm(o) for o in options}


def check_eligibility(
    profile: StudentProfile,
    scheme: Scheme,
    today: Optional[date] = None,
) -> EligibilityResult:
    today = today or date.today()
    fails: list[str] = []
    passes: list[str] = []
    missing: list[str] = []

    # Category
    if scheme.eligible_categories is not None:
        if profile.category is None:
            missing.append("category")
        elif _in_list(profile.category, scheme.eligible_categories):
            passes.append(f"Category {profile.category} is accepted.")
        else:
            fails.append(
                f"Open only to {', '.join(scheme.eligible_categories)}; "
                f"you are {profile.category}."
            )

    # Income
    if scheme.max_family_income is not None:
        if profile.annual_family_income is None:
            missing.append("annual_family_income")
        elif profile.annual_family_income <= scheme.max_family_income:
            passes.append(
                f"Family income {profile.annual_family_income} is within the "
                f"limit of {scheme.max_family_income}."
            )
        else:
            fails.append(
                f"Family income {profile.annual_family_income} exceeds the "
                f"limit of {scheme.max_family_income}."
            )

    # Minimum marks
    if scheme.min_percentage is not None:
        if profile.last_exam_percentage is None:
            missing.append("last_exam_percentage")
        elif profile.last_exam_percentage >= scheme.min_percentage:
            passes.append(
                f"Marks {profile.last_exam_percentage}% meet the minimum of "
                f"{scheme.min_percentage}%."
            )
        else:
            fails.append(
                f"Marks {profile.last_exam_percentage}% are below the minimum "
                f"of {scheme.min_percentage}%."
            )

    # Level (UG / PG ...)
    if scheme.levels is not None:
        if profile.level is None:
            missing.append("level")
        elif _in_list(profile.level, scheme.levels):
            passes.append(f"Level {profile.level} is covered.")
        else:
            fails.append(
                f"Covers {', '.join(scheme.levels)} only; you are in "
                f"{profile.level}."
            )

    # Course
    if scheme.courses is not None:
        if profile.course is None:
            missing.append("course")
        elif _in_list(profile.course, scheme.courses):
            passes.append(f"Course {profile.course} is covered.")
        else:
            fails.append(
                f"Covers {', '.join(scheme.courses)} only; your course is "
                f"{profile.course}."
            )

    # State of domicile
    if scheme.states is not None:
        if profile.state is None:
            missing.append("state")
        elif _in_list(profile.state, scheme.states):
            passes.append(f"State {profile.state} is covered.")
        else:
            fails.append(
                f"Only for residents of {', '.join(scheme.states)}; you are "
                f"from {profile.state}."
            )

    # Gender
    if scheme.gender is not None:
        if profile.gender is None:
            missing.append("gender")
        elif _norm(profile.gender) == _norm(scheme.gender):
            passes.append("Gender requirement met.")
        else:
            fails.append(f"Only for {scheme.gender} students.")

    # Disability
    if scheme.requires_disability:
        if profile.has_disability is None:
            missing.append("has_disability")
        elif profile.has_disability:
            passes.append("Disability requirement met.")
        else:
            fails.append("Only for students with a disability.")

    # Minority
    if scheme.requires_minority:
        if profile.is_minority is None:
            missing.append("is_minority")
        elif profile.is_minority:
            passes.append("Minority-community requirement met.")
        else:
            fails.append("Only for minority-community students.")

    # Special circumstances (student needs at least one)
    if scheme.required_circumstances_any is not None:
        if profile.circumstances is None:
            missing.append("circumstances")
        else:
            have = {_norm(c) for c in profile.circumstances}
            wanted = {_norm(c) for c in scheme.required_circumstances_any}
            if have & wanted:
                passes.append("A required family circumstance applies.")
            else:
                fails.append(
                    "Only for students in one of these situations: "
                    + ", ".join(scheme.required_circumstances_any)
                    + "."
                )

    deadline_passed = scheme.deadline is not None and scheme.deadline < today

    if fails:
        status, reasons, missing_out = Status.NOT_ELIGIBLE, fails, []
    elif missing:
        status = Status.NEEDS_MORE_INFO
        reasons = passes
        missing_out = missing
    else:
        status, reasons, missing_out = Status.ELIGIBLE, passes, []

    return EligibilityResult(
        scheme_id=scheme.id,
        status=status,
        reasons=reasons,
        missing_fields=missing_out,
        # Only relevant if the student is not already ruled out.
        unchecked_criteria=(
            list(scheme.unchecked_criteria)
            if status != Status.NOT_ELIGIBLE
            else []
        ),
        deadline_passed=deadline_passed,
    )


def match_schemes(
    profile: StudentProfile,
    schemes: list[Scheme],
    today: Optional[date] = None,
) -> dict[Status, list[EligibilityResult]]:
    """Run every scheme and group results by status."""
    grouped: dict[Status, list[EligibilityResult]] = {s: [] for s in Status}
    for scheme in schemes:
        result = check_eligibility(profile, scheme, today)
        grouped[result.status].append(result)
    return grouped