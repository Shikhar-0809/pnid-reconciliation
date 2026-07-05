# Build Sequence

> Phased plan. Each phase has a **gate** — do not proceed until it passes. This ordering exists
> because the data and the schemas must be solid before the flaky/expensive VLM work starts.

## Phase 0 — Skeleton & contracts
- Repo, `pyproject.toml`, config, `.env.example`, `.gitignore`.
- Implement **all `schemas/`** (extraction, sources, conflicts). These come first — they're the contract.
- `llm/client.py` stub with the two method signatures (no real call yet).
- **Gate:** schemas import cleanly; `ruff`/`mypy` pass on an empty skeleton.

## Phase 1 — Data generation (the blocker — do this before extraction)
- `data_gen/`: generate T0 scenarios (3–5 instruments, clean render), index CSV, datasheets.
- `inject_conflicts.py` + `ground_truth.json`.
- **Gate:** one T0 scenario exists with a rendered `pid.png` a human can read, matching index +
  datasheets, and a correct `ground_truth.json`. Regeneration from seed is deterministic.

## Phase 2 — Tag parsing (pure, testable, no network)
- `lark` ISA 5.1 grammar + `parse.py`.
- Full unit-test table incl. malformed tags → `parse_ok=False`.
- **Gate:** tag-parse unit tests green.

## Phase 3 — Reconciliation engine (mock the VLM entirely)
- `match.py` (deterministic first), `normalize.py`, `rules.py` registry, `engine.py`.
- Integration test: canned `ExtractionResult` + known sources → expected `ConflictReport`.
- **Gate:** every ConflictType is detected on fixtures; every conflict has provenance; integration
  tests green — all WITHOUT a real VLM call.

## Phase 4 — Extraction (first real VLM contact)
- `llm/client.py` real impl on **Gemini free tier**; `extract.py` with `instructor` → `ExtractionResult`.
- `confidence.py` thresholding → `needs_review`. Caching by image hash.
- **Gate:** on a T0 scenario, extraction returns valid schema-conforming JSON for a clean image;
  low-confidence reads on a noisy variant get flagged.

## Phase 5 — Wire the full pipeline + API
- `api/app.py`: `/extract`, `/reconcile`, `/process`, `/runs/{id}`. `storage/db.py` (SQLite).
- `reporting/report.py`: JSON + Markdown report.
- **Gate:** `POST /process` on a T0 scenario returns a conflict report end-to-end.

## Phase 6 — Eval harness + honest metrics
- `eval/run_eval.py` over the scenario set → per-ConflictType precision/recall + extraction metrics
  + confidence calibration. Emit the metrics table.
- **Gate:** metrics table generated from a real run, numbers reported as-is.

## Phase 7 — Scale to T1 + writeup
- Push scenarios to T1 (8–12 instruments). Fix what breaks. Re-run eval.
- README with the pitch, architecture diagram, and the **real** metrics table.
- **Gate:** T1 pipeline works; README done; repo clean (no secrets, no committed images/weights).

## Post-MVP (only via ANTI_DRIFT drift process)
- Light Qwen2.5-VL LoRA fine-tune (swap provider in `llm/client.py`).
- Revision-delta detection. Denser T2 scenarios. Minimal review UI.

## Ordering rationale (why this and not something else)
- Schemas before anything → stable contract prevents drift.
- Data before extraction → you can't test extraction without readable images + ground truth.
- Reconciliation before extraction → it's the higher-value, deterministic half; build it against a
  mock so the flaky/rate-limited VLM isn't on your critical path early.
- VLM last among core → it's the most failure-prone and quota-limited; everything else is solid by then.
