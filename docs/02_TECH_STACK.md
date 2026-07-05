# Tech Stack

> Locked. Adding or swapping a dependency requires the drift process in `ANTI_DRIFT.md`.
> Everything here is free. No paid service is required for MVP.

## Core

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.11 | Ecosystem, matches the JD |
| API | FastAPI + Uvicorn | Async, the JD names FastAPI explicitly |
| Data contracts | Pydantic v2 | Validation + the schema layer everything shares |
| Structured LLM output | `instructor` | Forces VLM/LLM output into Pydantic schemas |
| DB | SQLite (WAL mode) | Zero-setup, sufficient for portfolio scale |
| Config | `pydantic-settings` + `.env` | Typed config, secrets out of code |
| Testing | `pytest` + `pytest-cov` | Standard; see TESTING.md |
| Lint/format | `ruff` + `ruff format` | One tool, fast |
| Types | `mypy` (advisory) | Catch contract violations early |

## VLM / LLM (pick ONE provider to start; seam keeps it swappable)

| Option | Cost | Setup effort | Notes |
|---|---|---|---|
| **Gemini (Google AI Studio)** | Free tier | Lowest — API key only | **Recommended start.** No GPU. Rate-limited. |
| Groq (Llama vision) | Free tier | Low | Fast; multi-key rotation if throttled |
| Qwen2.5-VL 3B/7B on Kaggle/Colab | Free GPU | Higher | Local; enables later LoRA fine-tune |

**Decision:** MVP on **Gemini free tier**. `llm/client.py` isolates the provider so a switch to
local Qwen2.5-VL later is a one-file change (see ARCHITECTURE.md §3).

## Data generation / handling

| Concern | Choice | Why |
|---|---|---|
| Synthetic P&ID rendering | `svgwrite` → SVG → `cairosvg` to PNG | Full control; deterministic ground truth |
| Tabular docs | `pandas` | Index CSVs, datasheet frames |
| Image handling | `Pillow` | Preprocess, tile if needed |
| Tag grammar | `lark` | Real parser for ISA 5.1, not regex soup |

## Explicitly NOT in the stack (for MVP)

- ❌ Vector DB / RAG framework — not needed; this is extraction + rules, not retrieval.
- ❌ Custom-trained object detector (YOLO/DETR) — pretrained VLM only.
- ❌ Neo4j / graph DB — topology is out of scope.
- ❌ Celery/queue — synchronous is fine at this scale (revisit only if API times out).
- ❌ Docker in MVP — add at packaging stage, not before the pipeline works.

## Environment

- Dependency management: `uv` (or `pip` + `requirements.txt` if simpler).
- Python 3.11 pinned via `.python-version`.
- Secrets in `.env` (git-ignored). See CODING_PRACTICES.md §secrets.
- Works on Windows/PowerShell (dev machine) and Kaggle/Colab (if using local VLM).
