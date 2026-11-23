# ScholarMatch

An agent that tells Indian students which scholarships and government schemes
they are eligible for, with the reasoning, deadline, required documents and the
official source.

**Status:** in development (week 1 of 6).

## Design principle

The LLM never decides eligibility. Deterministic Python code does.
The LLM only (a) extracts student details from conversation and (b) phrases
the final answer. This keeps decisions testable and prevents hallucinated
eligibility.

## Layout

```
scholarmatch/
  models.py       Pydantic models: StudentProfile, Scheme, EligibilityResult
  engine.py       check_eligibility(profile, scheme) -> result
  loader.py       Load and validate scheme JSON files
data/
  schemes.example.json   Format example only (placeholder, not real data)
tests/
  test_engine.py
```

## Run the tests

```
pip install -r requirements.txt
pytest -q
```

## Roadmap

See LOG.md for daily progress. Planned: hybrid retrieval, agent loop,
50-case evaluation set, deployment, real-user feedback.
