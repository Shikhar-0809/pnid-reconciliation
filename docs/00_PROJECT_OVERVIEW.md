# Project Overview — P&ID Extraction + Cross-Document Reconciliation

> **One-line pitch:** A service that reads an engineering P&ID drawing with a vision-language
> model, extracts every instrument tag into structured data, then cross-checks that data
> against the instrument index and datasheets to automatically flag conflicts.

---

## 1. The problem (why this exists)

Industrial plants (refineries, chemical plants) are described by hundreds of **P&IDs**
(Piping & Instrumentation Diagrams) plus supporting documents — an **instrument index**
(a spreadsheet listing every instrument) and **datasheets** (per-device spec sheets).

The same instrument appears in all three. Because they are authored by different people at
different times, they routinely **disagree**: a sensor on the drawing is missing from the index,
a design pressure on the datasheet contradicts the drawing, a tag deleted in a drawing revision
still lingers in the index. Today humans catch these by manual review — slow, costly, error-prone.

This project automates the read + cross-check.

## 2. The solution (two halves)

**Half A — Extraction.** VLM reads a P&ID image → structured JSON list of instruments
(tag, type, properties) with a per-field **confidence score** and source location.

**Half B — Reconciliation.** Extracted list + instrument index + datasheets → a
**severity-ranked conflict report** (missing items, value mismatches, orphaned entries).

Half B runs on data Half A extracted from a real image — not hand-typed JSON. That fusion is
the whole point: it proves computer-vision capability AND makes the reconciliation results
credible (the inputs weren't authored by us).

## 3. Scope

### MVP (build this first, prove it end-to-end)
- Single P&ID image input (clean, low-complexity: ≤ ~15 instruments).
- VLM extraction → validated structured JSON with confidence + review flags.
- ISA 5.1 tag parsing (decompose tag into measured-variable / function / loop number).
- Reconciliation against ONE instrument index (CSV) + a small set of datasheets.
- Conflict report (JSON + human-readable) with severity levels.
- FastAPI endpoints wrapping the pipeline.
- Synthetic dataset with deliberately seeded conflicts + ground truth.

### Later (only after MVP works — see ANTI_DRIFT.md before adding)
- Multi-sheet drawings, higher instrument density.
- Light LoRA fine-tune of Qwen2.5-VL for symbol robustness.
- Revision-delta detection (diff two drawing revisions).
- Web UI for reviewing flagged conflicts.

## 4. Non-goals (explicitly out of scope)

- **NOT** rebuilding Pathnovo's proprietary CV moat (custom detectors on 200k drawings).
- **NOT** full topology/connectivity graph extraction (that's a separate, harder project).
- **NOT** training a VLM from scratch — we use pretrained models + prompting (+ optional LoRA later).
- **NOT** enterprise-schema export (CFIHOS/ISO 15926) in MVP — stub the interface only.
- **NOT** a production SLA. This is a portfolio-grade proof, with honest metrics.

## 5. Success criteria

- Pipeline runs end-to-end: image in → conflict report out, via one API call.
- On the synthetic set, the system **detects the seeded conflicts** and **reports honest
  precision/recall** (no fabricated accuracy claims — see TESTING.md).
- Low-confidence extractions are correctly flagged for review rather than silently trusted.
- Every claim in the writeup is backed by a reproducible eval run.

## 6. Who reads this suite

This is a Claude Projects + Cursor scaffold. Every doc is a contract. Before any build session,
the assistant re-reads `ANTI_DRIFT.md` and the files named in the active prompt (see PROMPTS.md).
