# Anti-Drift Contract

> **Read this at the start of every build session.** Its job is to stop the classic AI-assisted
> failure mode: the model silently "improving" the design, adding features, swapping libraries, or
> re-architecting between sessions until nothing matches the plan. Drift is allowed — but only
> deliberately, through the process below. Never silently.

## 1. Locked decisions (do NOT change without the drift process)

1. **Two-half architecture**: Extraction (VLM) → Reconciliation (rules + LLM fuzzy match). Fixed.
2. **Pydantic `schemas/` is the only inter-module contract.** No loose dicts across boundaries.
3. **Provider-agnostic LLM client** (`llm/client.py`) — all model calls route through it.
4. **`instructor` + Pydantic** for structured extraction. No hand-rolled free-text parsing.
5. **Rules are declarative data** in a registry, not scattered `if` statements.
6. **Deterministic-first matching**, LLM only on leftover unmatched items.
7. **Stack is frozen** to TECH_STACK.md. No new dependency without justification.
8. **Free-tier only** for MVP. No paid service introduced silently.
9. **SQLite + JSON columns.** No ORM, no Postgres, no vector DB in MVP.
10. **temp=0** for extraction and fuzzy matching (determinism invariant).

## 2. Scope guards (do NOT build these in MVP)

- ❌ Topology / connectivity graph extraction (separate project).
- ❌ Custom-trained object detector (pretrained VLM only).
- ❌ Multi-sheet drawings, continuation arrows.
- ❌ CFIHOS/ISO 15926 export (stub the interface only).
- ❌ Web UI (API + reports first).
- ❌ Auth, multi-tenancy, queues, Docker (until explicitly scheduled in BUILD_SEQUENCE.md).
- ❌ LoRA fine-tuning (post-MVP, only after the pretrained path is proven and metric'd).

If a prompt or the model suggests any of the above during MVP, STOP and flag it as a scope breach.

## 3. Signs of drift (catch these in review)

- A dict being passed between modules where a schema should be.
- A model call not going through `llm/client.py`.
- A new library appearing in imports that isn't in TECH_STACK.md.
- A conflict emitted without provenance (sources/values).
- "While I was here I also refactored X" — unrequested changes.
- Reconciliation logic leaking into the extraction module, or vice versa.
- Confidence/review logic being removed or bypassed.
- Metrics being hardcoded, rounded up, or a single best scenario reported as "the result."

## 4. The drift process (how to change a locked decision)

Drift is sometimes correct. When it's genuinely needed:

1. **State the trigger** — what forced the reconsideration (a real limitation, not a preference).
2. **Name the locked decision** being challenged (from §1/§2).
3. **Propose the change** + its blast radius (which files/schemas/docs change).
4. **Update the relevant .md FIRST**, then the code. Docs are the source of truth.
5. Only then implement. The change is now the new locked decision.

No silent changes. If it's not worth updating a doc for, it's not worth doing.

## 5. Per-session ritual (paste at the top of each Cursor session)

```
Before writing code this session:
1. Re-read ANTI_DRIFT.md (this file), ARCHITECTURE.md, and the .md files named in the current prompt.
2. Confirm the task is in scope (not blocked by §2 scope guards).
3. If the task requires changing a §1 locked decision, STOP and run the §4 drift process.
4. Exchange only schemas/ objects across module boundaries.
5. After coding: check the §3 drift signs before declaring done.
```

## 6. Definition of "unless needed"

The project may drift **only** when a locked decision provably blocks the success criteria in
PROJECT_OVERVIEW.md — never for elegance, novelty, or "best practice" impulses. Convenience is not
a trigger. A real blocker is.
