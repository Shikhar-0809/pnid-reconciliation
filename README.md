# P&ID Extraction + Cross-Document Reconciliation

This repository is a working demonstration built for a P&ID digitization engineering context — to show hands-on capability with the problems that role actually involves: reading instrument data from engineering drawings with a vision-language model, shaping it into validated structured output, and reconciling that output against an instrument index and datasheets.

Industrial plants are described by hundreds of P&IDs plus supporting documents — an instrument index and per-device datasheets. The same instrument appears in all three, and they routinely disagree: a sensor on the drawing is missing from the index, a design pressure on the datasheet contradicts the drawing, a tag deleted in a revision still lingers in the index. That cross-document drift is the operational pain point. This project implements the read-and-check loop end to end, with measured eval results rather than aspirational claims.

**Half A — Extraction.** A VLM reads a P&ID image and returns structured JSON (tag, type, properties) with per-field confidence and review flags.

**Half B — Reconciliation.** The extracted list is matched against an instrument index (CSV) and datasheets (JSON) to produce a severity-ranked conflict report.

Half B runs on data Half A extracted from a real image — not hand-typed JSON. The pipeline is wired that way deliberately: extraction quality and reconciliation credibility have to be evaluated together.

## Architecture

```
                        ┌──────────────────────────────────────────┐
  P&ID image  ─────────▶│  HALF A: EXTRACTION                       │
  (PNG/PDF)             │  1. preprocess (resize/normalize)         │
                        │  2. VLM extract → raw JSON                 │
                        │  3. validate (Pydantic) + confidence      │
                        │  4. ISA 5.1 tag parse                     │
                        └───────────────┬──────────────────────────┘
                                        │  ExtractedInstrument[]
                                        ▼
  instrument_index.csv ───────▶┌──────────────────────────────────┐
  datasheets/*.json ──────────▶│  HALF B: RECONCILIATION          │
                               │  1. normalize + index all sources │
                               │  2. entity match (deterministic)  │
                               │  3. LLM fuzzy-match (only unmatched)│
                               │  4. rule engine → conflicts        │
                               └───────────────┬──────────────────┘
                                               │  Conflict[]
                                               ▼
                                     ConflictReport (JSON + Markdown)
```

All endpoints are exposed via **FastAPI**. Run history is persisted in **SQLite**.

| Module | Responsibility |
|---|---|
| `ingest/` | Load and preprocess images and documents |
| `extraction/` | VLM call, schema validation, confidence gating |
| `tagparse/` | ISA 5.1 tag grammar parsing |
| `reconciliation/` | Matching, declarative rules, conflict emission |
| `llm/` | Provider-agnostic client (VLM + text) |
| `schemas/` | Pydantic models — the shared data contract |
| `api/` | FastAPI routes (delegate to modules) |
| `reporting/` | Render `ConflictReport` → JSON + Markdown |
| `eval/` | End-to-end metrics vs synthetic ground truth |

## Eval metrics (measured)

Generated from `python -m eval.run_eval` on T0 (`scenario_001`, 5 instruments) and T1 (`scenario_002`, 9 instruments). Numbers are exactly as emitted — no rounding up.

| Scenario | Tier | Extraction P | Extraction R | Tag Parse Acc | FP Conflicts |
| --- | --- | ---: | ---: | ---: | ---: |
| scenario_001 | T0 | 1.0 | 1.0 | 1.0 | 0 |
| scenario_002 | T1 | 1.0 | 1.0 | 1.0 | 0 |

**Aggregate extraction:** precision 1.0, recall 1.0 (tp=14, fp=0, fn=0)

**Aggregate tag parse:** accuracy 1.0 (tp=14, fp=0, fn=0)

**Reconciliation by ConflictType (aggregate):**

| ConflictType | TP | FP | FN | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| DUPLICATE_TAG | 2 | 0 | 0 | 1.0 | 1.0 |
| MISSING_DATASHEET | 2 | 0 | 0 | 1.0 | 1.0 |
| MISSING_IN_INDEX | 2 | 0 | 0 | 1.0 | 1.0 |
| MISSING_IN_PID | 2 | 0 | 0 | 1.0 | 1.0 |
| TYPE_MISMATCH | 2 | 0 | 0 | 1.0 | 1.0 |
| VALUE_MISMATCH | 2 | 0 | 0 | 1.0 | 1.0 |

Full tables: `eval/output/metrics.json` and `eval/output/metrics.md`.

Beyond the synthetic eval, the extraction half was exercised on a batch of real P&ID images — public-domain and textbook examples — via `POST /extract` in extraction-only mode (no instrument index or datasheets were available for matching). On clean CAD-exported P&IDs, the VLM typically returned on the order of 10–20 instruments per drawing. Images that are not P&IDs — motor nameplates, mechanical drawings, electrical schematics — generally returned zero instruments once the extraction prompt precondition was in place.

## Run instructions

### Prerequisites

- Python 3.11
- [uv](https://github.com/astral-sh/uv) or `pip` for dependency install

### Setup

```powershell
cd Pathnovo
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
# Edit .env and set GEMINI_API_KEY for live VLM extraction
```

### Generate synthetic scenarios

Scenario images (`pid.png`) are generated locally and git-ignored. Committed artifacts are seeds, SVG sources, CSV/JSON documents, and ground truth.

```powershell
# T0 — 3–5 instruments, large clean tags
python -m data_gen.generate --seed 42 --tier T0 --output scenarios/scenario_001

# T1 — 8–12 instruments, normal spacing (MVP target)
python -m data_gen.generate --seed 100 --tier T1 --output scenarios/scenario_002 --scenario-id scenario_002
```

### Run the API

```powershell
uvicorn pnid_recon.api.app:app --reload
```

Endpoints:

- `POST /extract` — VLM extraction from a P&ID image
- `POST /reconcile` — reconciliation from extraction + index + datasheets
- `POST /process` — full pipeline in one call
- `GET /runs/{id}` — retrieve a stored run

Example full pipeline:

```powershell
curl -X POST http://127.0.0.1:8000/process `
  -H "Content-Type: application/json" `
  -d "{\"image_path\":\"scenarios/scenario_002/pid.png\",\"index_path\":\"scenarios/scenario_002/instrument_index.csv\",\"datasheets_dir\":\"scenarios/scenario_002/datasheets\"}"
```

### Eval harness

```powershell
python -m eval.run_eval --scenarios-dir scenarios --output-dir eval/output
```

Requires rendered `pid.png` per scenario (generate first). Live VLM extraction needs `GEMINI_API_KEY`; results are cached under `.cache/extraction/` by image hash.

### Tests

```powershell
pytest
ruff check src tests data_gen eval
```

Unit and integration tests mock the VLM. Eval is run manually (costs API quota).

## Project docs

Full scaffold contracts live in `docs/`:

- `docs/00_PROJECT_OVERVIEW.md` — problem, scope, success criteria
- `docs/01_ARCHITECTURE.md` — module boundaries and invariants
- `docs/05_DATA_GENERATION.md` — synthetic scenario generator
- `docs/07_TESTING.md` — unit, integration, and eval layers
- `docs/08_ANTI_DRIFT.md` — locked decisions and scope guards

## Repository hygiene

- `.env` is git-ignored — never commit API keys
- `scenarios/**/pid.png` is git-ignored — regenerate from seeds
- `.cache/` and `*.db` are git-ignored
