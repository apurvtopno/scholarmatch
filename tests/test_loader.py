import json
from datetime import date

import pytest

from scholarmatch import Scheme, Status, StudentProfile, check_eligibility
from scholarmatch.loader import SchemeLoadError, load_schemes
from scholarmatch.validate import warnings_for

TODAY = date(2026, 11, 24)


def scheme_dict(id="a", **extra):
    d = dict(
        id=id,
        name="N",
        provider="P",
        official_url="https://example.org",
        source_text="t",
    )
    d.update(extra)
    return d


def write(folder, name, obj):
    (folder / name).write_text(json.dumps(obj), encoding="utf-8")


def test_loads_folder_of_single_scheme_files(tmp_path):
    write(tmp_path, "a.json", scheme_dict("a"))
    write(tmp_path, "b.json", scheme_dict("b"))
    assert [s.id for s in load_schemes(tmp_path)] == ["a", "b"]


def test_filename_must_match_id(tmp_path):
    write(tmp_path, "wrong.json", scheme_dict("a"))
    with pytest.raises(SchemeLoadError, match="does not match id 'a'"):
        load_schemes(tmp_path)


def test_duplicate_ids_across_files(tmp_path):
    write(tmp_path, "a.json", scheme_dict("a"))
    write(tmp_path, "a2.json", [scheme_dict("a")])
    with pytest.raises(SchemeLoadError, match="duplicate id 'a'"):
        load_schemes(tmp_path)


def test_all_errors_reported_together(tmp_path):
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    write(tmp_path, "missing.json", {"id": "missing", "name": "x"})
    with pytest.raises(SchemeLoadError) as e:
        load_schemes(tmp_path)
    msg = str(e.value)
    assert "4 problem(s)" in msg  # 1 bad JSON + 3 missing fields
    assert "broken.json: invalid JSON" in msg
    assert "missing.json: field 'provider'" in msg


def test_empty_folder_rejected(tmp_path):
    with pytest.raises(SchemeLoadError, match="No .json files"):
        load_schemes(tmp_path)


# ---------- unchecked_criteria ----------

def test_unchecked_criteria_surface_when_eligible():
    s = Scheme(**scheme_dict(max_family_income=450000,
                             unchecked_criteria=["Above 80th percentile in Class XII board"]))
    r = check_eligibility(StudentProfile(annual_family_income=300000), s, TODAY)
    assert r.status == Status.ELIGIBLE
    assert r.unchecked_criteria == ["Above 80th percentile in Class XII board"]


def test_unchecked_criteria_surface_when_needs_info():
    s = Scheme(**scheme_dict(max_family_income=450000, unchecked_criteria=["x"]))
    r = check_eligibility(StudentProfile(), s, TODAY)
    assert r.status == Status.NEEDS_MORE_INFO
    assert r.unchecked_criteria == ["x"]


def test_unchecked_criteria_hidden_when_not_eligible():
    s = Scheme(**scheme_dict(max_family_income=450000, unchecked_criteria=["x"]))
    r = check_eligibility(StudentProfile(annual_family_income=900000), s, TODAY)
    assert r.status == Status.NOT_ELIGIBLE
    assert r.unchecked_criteria == []


# ---------- validate warnings ----------

def test_clean_scheme_has_no_warnings():
    s = Scheme(**scheme_dict(
        source_text="x" * 100,
        last_verified="2026-11-20",
        deadline="2027-02-01",
        documents=["Marksheet"],
        benefit="Rs 10,000",
        max_family_income=100000,
    ))
    assert warnings_for(s, TODAY) == []


def test_placeholder_source_text_is_flagged():
    s = Scheme(**scheme_dict(source_text="PASTE THE EXACT PASSAGE HERE"))
    assert any("placeholder" in w for w in warnings_for(s, TODAY))


def test_warnings_flag_suspicious_data():
    s = Scheme(**scheme_dict(official_url="www.nolink", deadline="2026-01-01"))
    w = " | ".join(warnings_for(s, TODAY))
    assert "not a valid http(s) link" in w
    assert "source_text is very short" in w
    assert "last_verified is missing" in w
    assert "has passed" in w
    assert "no eligibility criteria" in w
    assert "no documents" in w
    assert "no benefit" in w


# ---------- special circumstances ----------

def circ_scheme():
    return Scheme(**scheme_dict(required_circumstances_any=["orphan", "parent_died_covid"]))


def test_circumstance_match_is_eligible():
    r = check_eligibility(StudentProfile(circumstances=["orphan"]), circ_scheme(), TODAY)
    assert r.status == Status.ELIGIBLE


def test_circumstance_none_apply_is_not_eligible():
    r = check_eligibility(StudentProfile(circumstances=[]), circ_scheme(), TODAY)
    assert r.status == Status.NOT_ELIGIBLE


def test_circumstance_other_only_is_not_eligible():
    p = StudentProfile(circumstances=["parent_critical_illness"])
    assert check_eligibility(p, circ_scheme(), TODAY).status == Status.NOT_ELIGIBLE


def test_circumstance_unknown_needs_info():
    r = check_eligibility(StudentProfile(), circ_scheme(), TODAY)
    assert r.status == Status.NEEDS_MORE_INFO
    assert r.missing_fields == ["circumstances"]


def test_unknown_circumstance_key_rejected_at_load(tmp_path):
    write(tmp_path, "a.json", scheme_dict("a", required_circumstances_any=["orphen"]))
    with pytest.raises(SchemeLoadError, match="unknown circumstance"):
        load_schemes(tmp_path)