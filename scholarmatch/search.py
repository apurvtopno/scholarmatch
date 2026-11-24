"""Keyword search over schemes (BM25), no external dependencies.

Search only decides WHICH schemes are worth looking at. It never decides
eligibility; that stays in engine.py.

Usage:
    python -m scholarmatch.search data/schemes "free coaching for UPSC"
"""

from __future__ import annotations

import math
import re
import sys
from collections import Counter
from dataclasses import dataclass

from .models import Scheme

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "for", "to", "in", "on", "at", "by",
    "is", "are", "be", "i", "me", "my", "we", "you", "your", "with", "from",
    "want", "need", "looking", "any", "which", "what", "can", "get", "find",
    "scheme", "schemes", "scholarship", "scholarships", "student", "students",
    "who", "that", "this", "it", "as", "will", "must", "not", "per",
}

# Words students use -> words the scheme documents use.
SYNONYMS = {
    "disabled": ["disability", "divyang", "pwd", "specially", "abled"],
    "disability": ["divyang", "pwd", "benchmark", "specially", "abled"],
    "divyang": ["disability", "specially", "abled"],
    "handicapped": ["disability", "specially", "abled"],
    "blind": ["disability", "visual", "specially", "abled"],
    "deaf": ["disability", "hearing", "specially", "abled"],
    "wheelchair": ["disability", "locomotor", "specially", "abled"],
    "girl": ["girls", "women", "female"],
    "girls": ["girl", "women", "female"],
    "woman": ["women", "girl", "female"],
    "women": ["girl", "female"],
    "female": ["girl", "women"],
    "tribal": ["st", "scheduled", "tribe"],
    "dalit": ["sc", "scheduled", "caste"],
    "ias": ["upsc", "civil"],
    "ips": ["upsc", "civil"],
    "upsc": ["civil", "services"],
    "btech": ["engineering", "technical", "degree"],
    "be": ["engineering"],
    "engineering": ["technical", "btech"],
    "mtech": ["engineering", "postgraduate"],
    "mba": ["management", "postgraduate"],
    "phd": ["doctoral", "fellowship", "research"],
    "research": ["phd", "fellowship"],
    "abroad": ["overseas", "foreign"],
    "foreign": ["overseas", "abroad"],
    "ug": ["undergraduate", "graduate", "degree"],
    "pg": ["postgraduate", "masters"],
    "masters": ["postgraduate", "pg"],
    "degree": ["undergraduate", "ug"],
    "diploma": ["polytechnic"],
    "polytechnic": ["diploma"],
    "northeast": ["north", "eastern", "region"],
    "ne": ["north", "eastern", "region"],
    "orphan": ["orphans", "parents", "died"],
    "martyr": ["shaheed", "armed", "forces"],
    "army": ["armed", "forces", "shaheed"],
    "coaching": ["entrance", "exam", "examination", "preparation"],
    "neet": ["medical", "entrance"],
    "jee": ["engineering", "entrance"],
    "gate": ["engineering", "entrance"],
    "covid": ["parents", "died"],
}

_TOKEN = re.compile(r"[a-z0-9]+")


def _stem(tok: str) -> str:
    """Very light stemming so 'girls' matches 'girl', 'courses' matches 'course'."""
    if len(tok) > 4 and tok.endswith("ies"):
        return tok[:-3] + "y"
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
        return tok[:-1]
    return tok


def tokenize(text: str) -> list[str]:
    toks = _TOKEN.findall(text.lower())
    return [_stem(t) for t in toks if t not in STOPWORDS and len(t) > 1]


def expand_query(query: str) -> list[str]:
    """Tokenize the query and add synonyms (each synonym counts less)."""
    base = _TOKEN.findall(query.lower())
    out: list[str] = []
    for t in base:
        if t in STOPWORDS:
            continue
        out.append(_stem(t))
    extra: list[str] = []
    for t in base:
        for syn in SYNONYMS.get(t, []):
            extra.append(_stem(syn))
    # Synonyms are appended once each; originals keep their own weight.
    return out + [e for e in dict.fromkeys(extra) if e not in out]


def _scheme_document(s: Scheme) -> list[str]:
    """Build the searchable token list for a scheme. The name is repeated
    so title matches outrank passing mentions deep in the text."""
    parts: list[str] = []
    parts += [s.name] * 4
    parts += [s.provider] * 1
    if s.benefit:
        parts.append(s.benefit)
    parts += list(s.unchecked_criteria)
    parts += list(s.documents)
    # Structured criteria become searchable words too.
    if s.eligible_categories:
        parts += list(s.eligible_categories) * 2
    if s.levels:
        parts += list(s.levels) * 2
    if s.states:
        parts += list(s.states)
    if s.gender:
        parts += [s.gender] * 3
    if s.requires_disability:
        parts += ["disability divyang benchmark"] * 3
    if s.requires_minority:
        parts += ["minority"] * 3
    if s.required_circumstances_any:
        parts += [c.replace("_", " ") for c in s.required_circumstances_any] * 2
    # Ignore placeholder text that would add noise.
    src = s.source_text.strip()
    if not src.upper().startswith(("PASTE", "TODO")):
        parts.append(src)
    tokens: list[str] = []
    for p in parts:
        tokens += tokenize(p)
    return tokens


@dataclass
class SearchHit:
    scheme_id: str
    score: float


class SchemeSearch:
    """BM25 index over a list of schemes."""

    def __init__(self, schemes: list[Scheme], k1: float = 1.5, b: float = 0.75):
        self.schemes = schemes
        self.k1, self.b = k1, b
        self._docs = [Counter(_scheme_document(s)) for s in schemes]
        self._lens = [sum(d.values()) for d in self._docs]
        self._avg = (sum(self._lens) / len(self._lens)) if self._lens else 0.0
        df: Counter[str] = Counter()
        for d in self._docs:
            df.update(d.keys())
        n = len(self._docs)
        self._idf = {
            t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()
        }

    def search(self, query: str, top_k: int = 5) -> list[SearchHit]:
        terms = expand_query(query)
        if not terms:
            return []
        original = {_stem(t) for t in _TOKEN.findall(query.lower())}
        hits: list[SearchHit] = []
        for s, doc, dl in zip(self.schemes, self._docs, self._lens):
            score = 0.0
            for t in terms:
                f = doc.get(t, 0)
                if not f:
                    continue
                idf = self._idf.get(t, 0.0)
                denom = f + self.k1 * (1 - self.b + self.b * dl / (self._avg or 1))
                weight = 1.0 if t in original else 0.4  # synonyms count less
                score += weight * idf * f * (self.k1 + 1) / denom
            if score > 0:
                hits.append(SearchHit(s.id, round(score, 4)))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print('Usage: python -m scholarmatch.search <schemes-folder> "your query"')
        return 2
    from .loader import load_schemes

    schemes = load_schemes(argv[1])
    names = {s.id: s.name for s in schemes}
    for h in SchemeSearch(schemes).search(" ".join(argv[2:]), top_k=5):
        print(f"{h.score:7.2f}  {h.scheme_id}  |  {names[h.scheme_id]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
