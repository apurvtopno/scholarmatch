from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from .models import Scheme


class SchemeLoadError(ValueError):
    """Raised with ALL problems found, so you can fix them in one pass."""


def _load_file(path: Path) -> list[Scheme]:
    """A scheme file holds one scheme object (or a list of them)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = raw if isinstance(raw, list) else [raw]
    return [Scheme.model_validate(item) for item in items]


def load_schemes(path: str | Path) -> list[Scheme]:
    """Load schemes from a single JSON file or from a folder of JSON files.

    For a folder, every *.json file is loaded, and the file name must match
    the scheme id (csss-pm-usp.json -> "id": "csss-pm-usp"). All problems
    across all files are collected and reported together.
    """
    path = Path(path)
    files = sorted(path.glob("*.json")) if path.is_dir() else [path]
    if not files:
        raise SchemeLoadError(f"No .json files found in {path}")

    schemes: list[Scheme] = []
    errors: list[str] = []
    origin: dict[str, str] = {}

    for f in files:
        try:
            loaded = _load_file(f)
        except json.JSONDecodeError as e:
            errors.append(f"{f.name}: invalid JSON ({e.msg}, line {e.lineno})")
            continue
        except ValidationError as e:
            for err in e.errors():
                loc = ".".join(str(p) for p in err["loc"]) or "(root)"
                errors.append(f"{f.name}: field '{loc}': {err['msg']}")
            continue

        for s in loaded:
            if path.is_dir() and len(loaded) == 1 and f.stem != s.id:
                errors.append(
                    f"{f.name}: file name does not match id '{s.id}' "
                    f"(expected {s.id}.json)"
                )
            if s.id in origin:
                errors.append(
                    f"{f.name}: duplicate id '{s.id}' (also in {origin[s.id]})"
                )
            origin[s.id] = f.name
            schemes.append(s)

    if errors:
        raise SchemeLoadError(
            f"{len(errors)} problem(s) found:\n  - " + "\n  - ".join(errors)
        )
    return schemes
