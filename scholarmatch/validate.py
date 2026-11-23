"""Data-quality check for scheme files.

Usage:  python -m scholarmatch.validate data/schemes

Errors  = file cannot be loaded (bad JSON, missing field, id mismatch).
Warnings = loads fine but looks suspicious. Review each one by hand.
"""

from __future__ import annotations

import sys
from datetime import date

from .loader import SchemeLoadError, load_schemes
from .models import Scheme

CRITERIA = [
    "eligible_categories",
    "max_family_income",
    "min_percentage",
    "levels",
    "courses",
    "states",
    "gender",
]


def warnings_for(s: Scheme, today: date | None = None) -> list[str]:
    today = today or date.today()
    w: list[str] = []
    if not s.official_url.startswith(("http://", "https://")):
        w.append("official_url is not a valid http(s) link")
    if len(s.source_text.strip()) < 80:
        w.append("source_text is very short; paste the full official passage")
    if s.source_text.strip().upper().startswith(("PASTE", "TODO")):
        w.append("source_text is still a placeholder; paste the official wording")
    if s.last_verified is None:
        w.append("last_verified is missing")
    elif (today - s.last_verified).days > 180:
        w.append("last_verified is more than 180 days old")
    if s.deadline is None:
        w.append("no deadline set (fine if the portal announces it yearly)")
    elif s.deadline < today:
        w.append(f"deadline {s.deadline} has passed; check for a new cycle")
    has_criteria = (
        any(getattr(s, c) is not None for c in CRITERIA)
        or s.requires_disability
        or s.requires_minority
        or s.required_circumstances_any is not None
        or s.unchecked_criteria
    )
    if not has_criteria:
        w.append("no eligibility criteria at all; everyone would match")
    if not s.documents:
        w.append("no documents listed")
    if not s.benefit:
        w.append("no benefit amount listed")
    if "example" in s.id.lower() or "placeholder" in s.name.lower():
        w.append("looks like placeholder data")
    return w


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: python -m scholarmatch.validate <folder-or-file>")
        return 2
    try:
        schemes = load_schemes(argv[1])
    except SchemeLoadError as e:
        print(f"ERRORS\n  {e}")
        return 1
    except FileNotFoundError:
        print(f"Not found: {argv[1]}")
        return 2

    total_warnings = 0
    for s in schemes:
        ws = warnings_for(s)
        total_warnings += len(ws)
        mark = "ok  " if not ws else "warn"
        print(f"[{mark}] {s.id}")
        for line in ws:
            print(f"         - {line}")
    print(f"\n{len(schemes)} schemes loaded, {total_warnings} warning(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))