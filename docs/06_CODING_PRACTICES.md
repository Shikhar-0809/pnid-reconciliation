# Coding Practices

> Conventions Cursor must follow in every file. Consistency here is what keeps a multi-session
> AI-assisted build from drifting into spaghetti.

## 1. General

- Python 3.11, type hints on every function signature. `mypy` advisory, `ruff` enforced.
- Small, single-responsibility functions. If a function does extraction AND reconciliation, split it.
- No logic in `__init__.py`. No business logic in `api/` routes — routes call module functions.
- Prefer pure functions; isolate side effects (I/O, network) at module edges.

## 2. The schema contract

- Modules exchange **Pydantic models from `schemas/`**, never raw dicts across boundaries.
- If you need a new shared shape, add it to `schemas/` — don't invent an ad-hoc dict.
- Validate at boundaries: anything entering from VLM/CSV/JSON is parsed into a schema immediately.

## 3. LLM / VLM call discipline

- **All** model calls go through `llm/client.py`. No module calls Gemini/Groq SDK directly.
- Extraction uses `instructor` to return `ExtractionResult`. Never parse free text by hand.
- Temperature = 0 for extraction and fuzzy-matching (determinism, see ARCHITECTURE invariant 4).
- Every call has a timeout and a retry-with-backoff (free tiers rate-limit — expect 429s).
- Log the prompt, model name, and token/latency for every call (cheap observability).
- Cache extraction results by image hash so re-runs don't burn quota. Cache is invalidated when
  the prompt template or model changes.

## 4. Error handling

- Fail loudly at boundaries, degrade gracefully in the pipeline: if one datasheet is malformed,
  record a warning and continue — don't crash the whole run.
- Distinguish **expected** issues (missing datasheet → a conflict, not an error) from **bugs**
  (schema validation failure → raise).
- Never swallow exceptions silently. Every `except` either handles or re-raises with context.

## 5. Config & secrets

- All tunables in typed config (`pydantic-settings`): confidence threshold, model name, timeouts,
  provider, paths. No magic numbers in code.
- Secrets (`GEMINI_API_KEY`, `GROQ_API_KEY`) in `.env`, git-ignored. `.env.example` committed
  with placeholder keys.
- **Never** hardcode a key or commit one. (Relevant lesson: a leaked key in git history is a real
  incident — rotate immediately if it ever happens, and scrub history.)

## 6. Determinism & reproducibility

- Set seeds for any randomness (data gen especially).
- Same inputs + temp=0 → same outputs. Tests rely on this.
- Pin dependency versions.

## 7. Naming

- `snake_case` functions/vars, `PascalCase` classes, `UPPER_SNAKE` constants.
- Names say what, not how: `find_value_mismatches()` not `check2()`.
- Conflict/schema field names match DATA_MODEL.md and DOMAIN_GLOSSARY.md exactly.

## 8. Comments & docstrings

- Docstring every public function: one line on purpose, note non-obvious domain logic.
- Comment the *why* for domain rules (e.g. "pressure mismatch is HIGH because it's safety-critical").
- No commented-out dead code committed.

## 9. Commits

- Small, scoped commits with imperative messages ("add ISA 5.1 tag parser").
- One logical change per commit. Don't mix a refactor with a feature.
- Never commit `.env`, model weights, or generated scenario images (git-ignore them; keep the
  generator + seeds instead).

## 10. Windows / cross-env note

- Dev machine is Windows/PowerShell; local VLM path may run on Kaggle/Colab Linux. Use `pathlib`,
  never hardcoded `\` or `/`. Keep the VLM provider swappable so environment differences are isolated
  to `llm/client.py`.
