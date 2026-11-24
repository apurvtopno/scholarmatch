from pathlib import Path

import pytest

from scholarmatch import Scheme
from scholarmatch.loader import load_schemes
from scholarmatch.search import SchemeSearch, expand_query, tokenize

DATA = Path(__file__).resolve().parent.parent / "data" / "schemes"


def sch(id_, name, **kw):
    base = dict(
        id=id_, name=name, provider="P",
        official_url="https://example.org", source_text="x",
    )
    base.update(kw)
    return Scheme(**base)


# ---------- tokenizer ----------

def test_tokenize_lowercases_and_drops_stopwords():
    assert tokenize("I want a Scholarship for the Girls") == ["girl"]


def test_light_stemming_matches_plurals():
    assert tokenize("courses") == tokenize("course")
    assert tokenize("girls") == tokenize("girl")


def test_expand_query_adds_synonyms_once():
    terms = expand_query("blind")
    assert "blind" in terms and "disability" in terms
    assert len(terms) == len(set(terms))


def test_expand_query_empty_for_only_stopwords():
    assert expand_query("I want a scholarship") == []


# ---------- ranking on synthetic schemes ----------

def test_title_match_ranks_first():
    schemes = [
        sch("a", "Free Coaching Scheme"),
        sch("b", "Pragati for Girls", benefit="mentions coaching once"),
    ]
    hits = SchemeSearch(schemes).search("coaching")
    assert hits[0].scheme_id == "a"


def test_no_match_returns_empty_list():
    schemes = [sch("a", "Free Coaching Scheme")]
    assert SchemeSearch(schemes).search("zzzqqq") == []


def test_empty_query_returns_empty_list():
    assert SchemeSearch([sch("a", "x scheme")]).search("") == []


def test_empty_index_does_not_crash():
    assert SchemeSearch([]).search("anything") == []


def test_top_k_limits_results():
    schemes = [sch(str(i), f"Coaching scheme {i}") for i in range(10)]
    assert len(SchemeSearch(schemes).search("coaching", top_k=3)) == 3


def test_synonym_finds_scheme_that_uses_other_word():
    schemes = [
        sch("dis", "Support for Students with Disability"),
        sch("other", "Merit Prize"),
    ]
    hits = SchemeSearch(schemes).search("I am disabled")
    assert hits and hits[0].scheme_id == "dis"


def test_structured_fields_are_searchable():
    schemes = [
        sch("orph", "Swanath", required_circumstances_any=["orphan"]),
        sch("other", "Merit Prize"),
    ]
    hits = SchemeSearch(schemes).search("orphan")
    assert hits[0].scheme_id == "orph"


def test_placeholder_source_text_is_not_indexed():
    schemes = [
        sch("a", "Alpha", source_text="PASTE THE EXACT PASSAGE HERE"),
        sch("b", "Beta"),
    ]
    assert SchemeSearch(schemes).search("paste passage") == []


# ---------- real data: expected scheme must appear in the top 3 ----------

REAL_CASES = [
    ("free coaching for UPSC", "free-coaching-sc-obc-pmcares-2024"),
    ("free coaching for UPSC", "depwd-free-coaching"),
    ("scholarship for girls engineering", "aicte-pragati-degree"),
    ("I am blind and want a scholarship", "aicte-saksham-degree"),
    ("deaf student diploma", "aicte-saksham-diploma"),
    ("north east student", "ugc-ishan-uday"),
    ("my parents died", "aicte-swanath"),
    ("PhD fellowship", "depwd-national-fellowship"),
    ("study abroad masters", "depwd-national-overseas"),
    ("ST student", "national-scholarship-higher-education-st-2021"),
]


@pytest.fixture(scope="module")
def real_index():
    if not DATA.exists():
        pytest.skip("data/schemes not found")
    return SchemeSearch(load_schemes(DATA))


@pytest.mark.parametrize("query,expected", REAL_CASES)
def test_real_data_expected_scheme_in_top3(real_index, query, expected):
    top3 = [h.scheme_id for h in real_index.search(query, top_k=3)]
    assert expected in top3, f"{query!r} gave {top3}"
