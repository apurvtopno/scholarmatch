from datetime import date

import pytest

from scholarmatch import Scheme, Status, StudentProfile, check_eligibility, match_schemes
from scholarmatch.loader import load_schemes

TODAY = date(2026, 11, 17)


def make_scheme(**overrides) -> Scheme:
    base = dict(
        id="s1",
        name="Test Scheme",
        provider="Test Provider",
        official_url="https://example.org",
        source_text="Test source passage.",
    )
    base.update(overrides)
    return Scheme(**base)


# ---------- Category ----------

def test_category_match_is_eligible():
    s = make_scheme(eligible_categories=["SC", "ST"])
    r = check_eligibility(StudentProfile(category="SC"), s, TODAY)
    assert r.status == Status.ELIGIBLE


def test_category_mismatch_is_not_eligible():
    s = make_scheme(eligible_categories=["SC", "ST"])
    r = check_eligibility(StudentProfile(category="General"), s, TODAY)
    assert r.status == Status.NOT_ELIGIBLE
    assert "General" in r.reasons[0]


def test_category_is_case_insensitive():
    s = make_scheme(eligible_categories=["OBC"])
    r = check_eligibility(StudentProfile(category=" obc "), s, TODAY)
    assert r.status == Status.ELIGIBLE


def test_category_unknown_needs_info():
    s = make_scheme(eligible_categories=["SC"])
    r = check_eligibility(StudentProfile(), s, TODAY)
    assert r.status == Status.NEEDS_MORE_INFO
    assert r.missing_fields == ["category"]


# ---------- Income ----------

def test_income_below_limit_eligible():
    s = make_scheme(max_family_income=250000)
    r = check_eligibility(StudentProfile(annual_family_income=200000), s, TODAY)
    assert r.status == Status.ELIGIBLE


def test_income_exactly_at_limit_eligible():
    s = make_scheme(max_family_income=250000)
    r = check_eligibility(StudentProfile(annual_family_income=250000), s, TODAY)
    assert r.status == Status.ELIGIBLE


def test_income_above_limit_not_eligible():
    s = make_scheme(max_family_income=250000)
    r = check_eligibility(StudentProfile(annual_family_income=250001), s, TODAY)
    assert r.status == Status.NOT_ELIGIBLE


def test_income_unknown_needs_info():
    s = make_scheme(max_family_income=250000)
    r = check_eligibility(StudentProfile(), s, TODAY)
    assert r.status == Status.NEEDS_MORE_INFO
    assert "annual_family_income" in r.missing_fields


def test_zero_income_is_not_treated_as_missing():
    s = make_scheme(max_family_income=250000)
    r = check_eligibility(StudentProfile(annual_family_income=0), s, TODAY)
    assert r.status == Status.ELIGIBLE


# ---------- Marks ----------

def test_marks_meet_minimum():
    s = make_scheme(min_percentage=60)
    assert check_eligibility(
        StudentProfile(last_exam_percentage=60), s, TODAY
    ).status == Status.ELIGIBLE


def test_marks_below_minimum():
    s = make_scheme(min_percentage=60)
    assert check_eligibility(
        StudentProfile(last_exam_percentage=59.9), s, TODAY
    ).status == Status.NOT_ELIGIBLE


def test_zero_marks_is_not_treated_as_missing():
    s = make_scheme(min_percentage=60)
    r = check_eligibility(StudentProfile(last_exam_percentage=0), s, TODAY)
    assert r.status == Status.NOT_ELIGIBLE


# ---------- Level / course / state / gender ----------

def test_level_mismatch():
    s = make_scheme(levels=["UG"])
    assert check_eligibility(
        StudentProfile(level="PG"), s, TODAY
    ).status == Status.NOT_ELIGIBLE


def test_course_match():
    s = make_scheme(courses=["BTech", "BE"])
    assert check_eligibility(
        StudentProfile(course="btech"), s, TODAY
    ).status == Status.ELIGIBLE


def test_state_mismatch():
    s = make_scheme(states=["Jharkhand"])
    assert check_eligibility(
        StudentProfile(state="Bihar"), s, TODAY
    ).status == Status.NOT_ELIGIBLE


def test_state_match():
    s = make_scheme(states=["Jharkhand"])
    assert check_eligibility(
        StudentProfile(state="jharkhand"), s, TODAY
    ).status == Status.ELIGIBLE


def test_gender_restricted_scheme():
    s = make_scheme(gender="female")
    assert check_eligibility(
        StudentProfile(gender="male"), s, TODAY
    ).status == Status.NOT_ELIGIBLE
    assert check_eligibility(
        StudentProfile(gender="Female"), s, TODAY
    ).status == Status.ELIGIBLE


# ---------- Disability / minority ----------

def test_disability_required():
    s = make_scheme(requires_disability=True)
    assert check_eligibility(
        StudentProfile(has_disability=False), s, TODAY
    ).status == Status.NOT_ELIGIBLE
    assert check_eligibility(
        StudentProfile(has_disability=True), s, TODAY
    ).status == Status.ELIGIBLE
    assert check_eligibility(
        StudentProfile(), s, TODAY
    ).status == Status.NEEDS_MORE_INFO


def test_minority_required():
    s = make_scheme(requires_minority=True)
    assert check_eligibility(
        StudentProfile(is_minority=False), s, TODAY
    ).status == Status.NOT_ELIGIBLE
    assert check_eligibility(
        StudentProfile(is_minority=True), s, TODAY
    ).status == Status.ELIGIBLE


# ---------- Combined logic ----------

def test_no_criteria_means_everyone_eligible():
    r = check_eligibility(StudentProfile(), make_scheme(), TODAY)
    assert r.status == Status.ELIGIBLE


def test_fail_wins_over_missing():
    """If one criterion already fails, do not ask for more info."""
    s = make_scheme(eligible_categories=["SC"], max_family_income=100000)
    r = check_eligibility(StudentProfile(category="General"), s, TODAY)
    assert r.status == Status.NOT_ELIGIBLE
    assert r.missing_fields == []


def test_multiple_missing_fields_all_reported():
    s = make_scheme(eligible_categories=["SC"], max_family_income=100000, min_percentage=50)
    r = check_eligibility(StudentProfile(), s, TODAY)
    assert r.status == Status.NEEDS_MORE_INFO
    assert set(r.missing_fields) == {
        "category",
        "annual_family_income",
        "last_exam_percentage",
    }


def test_all_criteria_pass():
    s = make_scheme(
        eligible_categories=["OBC"],
        max_family_income=400000,
        min_percentage=55,
        levels=["UG"],
        states=["Jharkhand"],
    )
    p = StudentProfile(
        category="OBC",
        annual_family_income=380000,
        last_exam_percentage=72,
        level="UG",
        state="Jharkhand",
    )
    r = check_eligibility(p, s, TODAY)
    assert r.status == Status.ELIGIBLE
    assert len(r.reasons) == 5


# ---------- Deadlines ----------

def test_deadline_passed_flag():
    s = make_scheme(deadline=date(2026, 10, 1))
    r = check_eligibility(StudentProfile(), s, TODAY)
    assert r.deadline_passed is True


def test_deadline_today_is_not_passed():
    s = make_scheme(deadline=TODAY)
    assert check_eligibility(StudentProfile(), s, TODAY).deadline_passed is False


def test_no_deadline_not_passed():
    assert check_eligibility(StudentProfile(), make_scheme(), TODAY).deadline_passed is False


# ---------- match_schemes + loader ----------

def test_match_schemes_groups_by_status():
    schemes = [
        make_scheme(id="a", eligible_categories=["OBC"]),
        make_scheme(id="b", eligible_categories=["SC"]),
        make_scheme(id="c", max_family_income=100000),
    ]
    grouped = match_schemes(StudentProfile(category="OBC"), schemes, TODAY)
    assert [r.scheme_id for r in grouped[Status.ELIGIBLE]] == ["a"]
    assert [r.scheme_id for r in grouped[Status.NOT_ELIGIBLE]] == ["b"]
    assert [r.scheme_id for r in grouped[Status.NEEDS_MORE_INFO]] == ["c"]


def test_duplicate_ids_rejected(tmp_path):
    f = tmp_path / "dup.json"
    one = (
        '{"id":"x","name":"n","provider":"p","official_url":"u","source_text":"t"}'
    )
    f.write_text(f"[{one},{one}]")
    with pytest.raises(ValueError, match="duplicate id"):
        load_schemes(f)


def test_missing_required_field_rejected(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text('[{"id":"x","name":"n"}]')
    with pytest.raises(Exception):
        load_schemes(f)
