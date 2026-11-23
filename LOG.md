# Build Log

Write a few lines every day: what you did, what broke, what you learned.
This becomes your interview material.

## 2026-11-17
- Set up the project structure.
- Wrote the scheme schema and the eligibility engine (plain Python, no LLM).
- Wrote pytest cases for the engine, including missing-information cases.
- Decision: eligibility is decided by code, never by the LLM. The LLM will only
  extract profile fields from chat and phrase the answer.
