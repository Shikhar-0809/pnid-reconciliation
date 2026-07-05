# Architecture

> Locked design. Do not restructure without going through the drift process in `ANTI_DRIFT.md`.

## 1. High-level flow

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

All of it exposed via **FastAPI**. Persistence in **SQLite**.

## 2. Module boundaries (the contract)

| Module | Responsibility | Must NOT do |
|---|---|---|
| `ingest/` | Load + preprocess images and documents | Call the VLM, apply business rules |
| `extraction/` | VLM call, schema validation, confidence | Reconciliation, cross-document logic |
| `tagparse/` | ISA 5.1 tag grammar parsing | Network calls, VLM calls |
| `reconciliation/` | Matching + rule engine + conflict build | Call the VLM directly for extraction |
| `llm/` | Thin provider-agnostic client (VLM + text) | Contain business logic |
| `schemas/` | Pydantic models — the shared data contract | Any logic beyond validation |
| `api/` | FastAPI routes, request/response shaping | Business logic (delegates to modules) |
| `reporting/` | Render ConflictReport → JSON + Markdown | Detect conflicts |

**Rule:** modules talk only through the Pydantic models in `schemas/`. If two modules need a new
shared shape, it goes in `schemas/` — never passed as loose dicts.

## 3. Key decisions (and why)

- **Provider-agnostic LLM client.** `llm/client.py` exposes `extract_from_image()` and
  `text_complete()`. Swapping Gemini ↔ Groq ↔ local Qwen2.5-VL changes ONE file. Start on
  Gemini free tier; keep the seam so a later local/fine-tuned model drops in.
- **Structured output via `instructor` + Pydantic.** The VLM is forced to return the
  `ExtractionResult` schema. No free-text parsing. This is the reliability backbone.
- **Deterministic-first matching.** Cheap exact/normalized matching runs before any LLM call.
  The LLM fuzzy-matcher only sees the *leftover unmatched* items → cheap, fast, auditable.
- **Rules are data, not code.** Conflict rules live in a declarative registry (see DATA_MODEL.md)
  so new rule = new entry, not a code rewrite. Keeps the engine stable as rules grow.
- **Confidence gating at the boundary.** Extraction attaches confidence; a threshold in config
  decides `needs_review`. Reconciliation treats `needs_review` items as lower-trust.

## 4. Data flow invariants

1. Nothing downstream of `extraction/` ever re-reads the image.
2. Every conflict references the **source document(s)** and the **field(s)** that disagree.
3. Every extracted instrument carries provenance: which image, which region, what confidence.
4. The pipeline is **idempotent** on the same inputs (same input → same report, LLM temp=0).

## 5. Tech stack summary

See `02_TECH_STACK.md` for exact libraries/versions. Headline: Python 3.11, FastAPI, Pydantic v2,
`instructor`, a free VLM (Gemini/Groq/Qwen2.5-VL), SQLite, pytest.
