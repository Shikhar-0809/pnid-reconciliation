# Cursor Prompt Sequence

> One prompt per build phase (BUILD_SEQUENCE.md). **Every prompt attaches the specific `@.md`
> files it needs** — attach exactly those in Cursor so the model has the contract in context and
> can't drift. `@08_ANTI_DRIFT.md` is attached to EVERY prompt on purpose. Run prompts in order;
> do not skip a phase's gate.

**How to use:** in Cursor, attach the listed `@files`, paste the prompt, let it work, then verify
the phase gate in BUILD_SEQUENCE.md before moving on.

---

## Standing preamble (mentally prepend to every prompt)

```
Follow @08_ANTI_DRIFT.md. Before coding: re-read the attached .md files, confirm the task is in
scope (ANTI_DRIFT §2), and if it requires changing a locked decision (ANTI_DRIFT §1) STOP and run
the drift process instead. Exchange only schemas/ objects across module boundaries. Do not add
features, dependencies, or refactors I didn't ask for. After coding, self-check against
ANTI_DRIFT §3 drift signs.
```

---

### Prompt 0 — Skeleton & schemas
**Attach:** `@00_PROJECT_OVERVIEW.md` `@01_ARCHITECTURE.md` `@02_TECH_STACK.md` `@04_DATA_MODEL.md` `@06_CODING_PRACTICES.md` `@09_FILE_STRUCTURE.md` `@08_ANTI_DRIFT.md`

```
Set up the repo skeleton exactly per @09_FILE_STRUCTURE.md: pyproject.toml (deps from
@02_TECH_STACK.md only), config.py using pydantic-settings, .env.example, .gitignore, .python-version.
Then implement ALL Pydantic models in src/pnid_recon/schemas/ exactly as specified in
@04_DATA_MODEL.md (extraction.py, sources.py, conflicts.py). Create llm/client.py with stub
signatures extract_from_image() and text_complete() — no implementation yet.
Follow @06_CODING_PRACTICES.md. Do not implement any business logic this phase.
Gate: schemas import cleanly, ruff + mypy pass.
```

---

### Prompt 1 — Data generator
**Attach:** `@05_DATA_GENERATION.md` `@04_DATA_MODEL.md` `@03_DOMAIN_GLOSSARY.md` `@06_CODING_PRACTICES.md` `@09_FILE_STRUCTURE.md` `@08_ANTI_DRIFT.md`

```
Implement data_gen/ per @05_DATA_GENERATION.md for Tier T0 only (3–5 instruments, clean render).
Use svgwrite→cairosvg for pid.png, emit instrument_index.csv and datasheets/*.json from one
source-of-truth instrument list, then inject_conflicts.py perturbs copies and writes ground_truth.json
recording every seeded conflict. Tags must be valid ISA 5.1 per @03_DOMAIN_GLOSSARY.md. Everything
seed-deterministic. Do NOT build a general CAD tool — legibility over fidelity (ANTI_DRIFT §2 data note).
Gate: one readable T0 scenario with matching docs + correct ground_truth.json, regenerable from seed.
```

---

### Prompt 2 — ISA 5.1 tag parser
**Attach:** `@03_DOMAIN_GLOSSARY.md` `@04_DATA_MODEL.md` `@07_TESTING.md` `@06_CODING_PRACTICES.md` `@08_ANTI_DRIFT.md`

```
Implement src/pnid_recon/tagparse/ : a lark grammar (grammar.py) for ISA 5.1 tags and parse.py
turning a tag string into a ParsedTag (@04_DATA_MODEL.md), using the letter tables in
@03_DOMAIN_GLOSSARY.md. Unknown/malformed tags must return parse_ok=False — never guess.
Write the full unit-test table per @07_TESTING.md §2, including malformed cases. Pure functions,
no network. Gate: tag-parse unit tests green.
```

---

### Prompt 3 — Reconciliation engine (VLM mocked)
**Attach:** `@01_ARCHITECTURE.md` `@04_DATA_MODEL.md` `@03_DOMAIN_GLOSSARY.md` `@07_TESTING.md` `@06_CODING_PRACTICES.md` `@08_ANTI_DRIFT.md`

```
Implement src/pnid_recon/reconciliation/ : normalize.py (value/unit normalization), match.py
(deterministic exact/normalized match FIRST, then a text-LLM fuzzy-match via llm/client.text_complete
on ONLY the leftover unmatched — ARCHITECTURE §3), rules.py (declarative RULES registry per
@04_DATA_MODEL.md §4), engine.py (run rules on matched sets → Conflict[]). Every Conflict carries
provenance (sources + values). Cover every ConflictType from @03_DOMAIN_GLOSSARY.md. Do NOT call the
VLM here. Write integration tests per @07_TESTING.md §3 using a canned ExtractionResult (mock the VLM).
Gate: all ConflictTypes detected on fixtures, every conflict has provenance, integration tests green.
```

---

### Prompt 4 — Extraction (real VLM)
**Attach:** `@01_ARCHITECTURE.md` `@02_TECH_STACK.md` `@04_DATA_MODEL.md` `@06_CODING_PRACTICES.md` `@07_TESTING.md` `@08_ANTI_DRIFT.md`

```
Implement the real llm/client.py for the Gemini free tier (provider-agnostic per ARCHITECTURE §3;
keep the seam so Groq/local Qwen2.5-VL can swap in via config). Implement extraction/extract.py:
call the VLM through instructor to return ExtractionResult (@04_DATA_MODEL.md); temp=0; timeout +
retry/backoff for 429s; cache by image hash (@06_CODING_PRACTICES.md §3). Implement
confidence.py applying the config threshold → needs_review. Do not hand-parse free text.
Gate: on a T0 scenario, extraction returns schema-valid JSON; a noisy variant triggers needs_review.
```

---

### Prompt 5 — Pipeline + FastAPI + storage
**Attach:** `@01_ARCHITECTURE.md` `@09_FILE_STRUCTURE.md` `@04_DATA_MODEL.md` `@06_CODING_PRACTICES.md` `@08_ANTI_DRIFT.md`

```
Wire the full pipeline. Implement storage/db.py (SQLite: runs, instruments, conflicts as JSON
columns — @04_DATA_MODEL.md §5), reporting/report.py (ConflictReport → JSON + Markdown), and
api/app.py with exactly the four endpoints in @09_FILE_STRUCTURE.md (/extract, /reconcile,
/process, /runs/{id}). Routes contain NO business logic — they delegate to modules (CODING_PRACTICES §1).
Do not add endpoints beyond the four. Gate: POST /process on a T0 scenario returns a full report.
```

---

### Prompt 6 — Eval harness + honest metrics
**Attach:** `@07_TESTING.md` `@05_DATA_GENERATION.md` `@04_DATA_MODEL.md` `@06_CODING_PRACTICES.md` `@08_ANTI_DRIFT.md`

```
Implement eval/ : run_eval.py runs the full pipeline over scenarios and compares to ground_truth.json;
metrics.py computes per-ConflictType precision/recall, extraction recall/precision, tag-parse accuracy,
and confidence calibration (@07_TESTING.md §4). Emit a metrics table (JSON + Markdown). Report numbers
exactly as measured — no rounding up, no cherry-picking one scenario (ANTI_DRIFT §3). Gate: metrics
table generated from a real run.
```

---

### Prompt 7 — Scale to T1 + README
**Attach:** `@00_PROJECT_OVERVIEW.md` `@05_DATA_GENERATION.md` `@07_TESTING.md` `@01_ARCHITECTURE.md` `@08_ANTI_DRIFT.md`

```
Generate T1 scenarios (8–12 instruments, @05_DATA_GENERATION.md ladder), run the pipeline, fix
failures, re-run eval. Write README.md: the pitch from @00_PROJECT_OVERVIEW.md, an architecture
diagram from @01_ARCHITECTURE.md, the honest metrics table, and run instructions. Ensure repo is
clean: no .env, no committed scenario images or model weights (CODING_PRACTICES §9). Gate: T1
pipeline works, README done.
```

---

## Drift-recovery prompt (use any time the build wanders)

**Attach:** `@08_ANTI_DRIFT.md` `@01_ARCHITECTURE.md` `@09_FILE_STRUCTURE.md` + the drifting file(s)

```
Audit the attached code against @08_ANTI_DRIFT.md §1 (locked decisions) and §3 (drift signs) and
@01_ARCHITECTURE.md module boundaries. List every violation: loose dicts across boundaries, model
calls bypassing llm/client.py, deps not in TECH_STACK, conflicts missing provenance, out-of-scope
features, unrequested refactors. Propose the minimal fix to bring it back to contract. Do not add
anything new — only realign to the docs.
```

---

## Feature-request prompt (when you genuinely need to change scope)

**Attach:** `@08_ANTI_DRIFT.md` `@00_PROJECT_OVERVIEW.md` + affected docs

```
I want to change/add: <describe>. Run the ANTI_DRIFT §4 drift process: (1) state the trigger,
(2) name the locked decision(s) affected, (3) propose the change + blast radius (files/schemas/docs),
(4) update the relevant .md FIRST and show me the diff. Do NOT write code until the docs are updated
and I approve.
```
