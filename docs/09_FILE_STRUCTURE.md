# File Structure

> The repo layout. Mirrors the module boundaries in ARCHITECTURE.md §2. Cursor creates files in
> these locations; new top-level modules are a drift event.

```
pnid-reconciliation/
├── README.md                     # generated last: pitch + honest metrics table
├── .env.example                  # placeholder keys (real .env is git-ignored)
├── .gitignore                    # .env, __pycache__, scenarios/*.png, *.db
├── pyproject.toml                # deps (uv/pip), ruff, mypy config
├── .python-version               # 3.11
│
├── docs/                         # THIS scaffolding suite lives here
│   ├── 00_PROJECT_OVERVIEW.md
│   ├── 01_ARCHITECTURE.md
│   ├── ...                       # all the .md files
│   └── 10_PROMPTS.md
│
├── src/pnid_recon/
│   ├── __init__.py
│   ├── config.py                 # pydantic-settings: threshold, model, timeouts, paths
│   │
│   ├── schemas/                  # THE shared contract (DATA_MODEL.md)
│   │   ├── __init__.py
│   │   ├── extraction.py         # ExtractedInstrument, ExtractionResult, ParsedTag, BoundingBox
│   │   ├── sources.py            # IndexRow, Datasheet
│   │   └── conflicts.py          # Conflict, ConflictReport, ConflictType, Severity
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   └── client.py             # provider-agnostic: extract_from_image(), text_complete()
│   │
│   ├── ingest/
│   │   ├── __init__.py
│   │   ├── images.py             # load/preprocess P&ID images
│   │   └── documents.py          # load index CSV + datasheet JSONs into schemas
│   │
│   ├── extraction/
│   │   ├── __init__.py
│   │   ├── extract.py            # VLM call via llm/client + instructor → ExtractionResult
│   │   └── confidence.py         # apply threshold → needs_review
│   │
│   ├── tagparse/
│   │   ├── __init__.py
│   │   ├── grammar.py            # lark grammar for ISA 5.1
│   │   └── parse.py              # tag string → ParsedTag
│   │
│   ├── reconciliation/
│   │   ├── __init__.py
│   │   ├── match.py              # deterministic + LLM fuzzy matching
│   │   ├── rules.py              # declarative RULES registry
│   │   ├── engine.py             # run rules → Conflict[]
│   │   └── normalize.py          # value/unit normalization
│   │
│   ├── reporting/
│   │   ├── __init__.py
│   │   └── report.py             # ConflictReport → JSON + Markdown
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   └── db.py                 # SQLite: runs, instruments, conflicts
│   │
│   └── api/
│       ├── __init__.py
│       └── app.py                # FastAPI routes → delegate to modules
│
├── data_gen/                     # DATA_GENERATION.md — build FIRST
│   ├── generate.py               # scenario generator (SVG→PNG, index, datasheets)
│   ├── inject_conflicts.py       # deliberate perturbations + ground truth
│   └── render.py                 # svgwrite → cairosvg
│
├── scenarios/                    # generated output (git-ignored except seeds)
│   └── scenario_001/ ...
│
├── eval/
│   ├── run_eval.py               # pipeline vs ground_truth → metrics table
│   └── metrics.py                # precision/recall per ConflictType, calibration
│
└── tests/
    ├── fixtures/                 # hand-authored canned data
    ├── test_tagparse.py
    ├── test_rules.py
    ├── test_match.py
    ├── test_normalize.py
    └── test_integration.py       # extraction→reconciliation with mocked VLM
```

## API surface (MVP)

- `POST /extract` — image → `ExtractionResult`
- `POST /reconcile` — extraction + index + datasheets → `ConflictReport`
- `POST /process` — image + index + datasheets → full pipeline → `ConflictReport`
- `GET /runs/{id}` — fetch a stored run + its conflicts

Keep it this small. New endpoints are a scope decision, not a reflex.
