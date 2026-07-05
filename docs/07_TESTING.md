# Testing

> The eval harness is a first-class deliverable, not an afterthought — honest metrics are the
> credibility of the whole project. Reuse the discipline from prior eval-harness work.

## 1. Test layers

| Layer | What | Speed | Uses real VLM? |
|---|---|---|---|
| Unit | Pure logic: tag parser, rule engine, matchers, normalizers | fast | No |
| Integration | Module seams: extraction→reconciliation with a **mocked** VLM | fast | No (mock) |
| Eval | End-to-end on synthetic scenarios with **real** VLM, vs ground truth | slow | Yes |

Unit + integration run on every change (cheap, deterministic). Eval runs on demand (costs quota).

## 2. Unit tests (the bulk)

- **ISA 5.1 tag parser** — table of tags → expected decomposition, including malformed tags that
  must return `parse_ok=False` (never guessed). This is the highest-value unit test.
- **Rule engine** — hand-built matched instrument sets → expected `Conflict` list. Cover every
  ConflictType and every severity.
- **Matchers** — exact match, normalized match (`PT-101` vs `PT 101`), and cases that should NOT
  match.
- **Value normalizers** — `"50 bar"` vs `"50 BAR"` vs `"50bar"` equal; `"50 bar"` vs `"40 bar"`
  conflict; unit mismatches flagged.

## 3. Integration tests (mock the VLM)

- Feed a canned `ExtractionResult` (as if the VLM returned it) + a known index/datasheets →
  assert the exact expected `ConflictReport`. No network. This validates Half B independently of
  the flaky/rate-limited VLM.
- Assert every conflict carries provenance (sources + values). A conflict without provenance is a
  test failure.

## 4. Eval harness (the credibility layer)

For each synthetic scenario, run the FULL pipeline and compare to `ground_truth.json`:

**Extraction metrics**
- Instrument recall/precision (did we find the right tags?).
- Tag-parse accuracy (did ISA 5.1 decomposition match?).
- Confidence calibration: are `needs_review` items actually the wrong/hard ones? (Flagging the
  hard cases is a feature — measure it.)

**Reconciliation metrics**
- Conflict precision/recall vs seeded conflicts, **per ConflictType**.
- False positives (conflicts reported that weren't seeded) — these matter as much as misses.

**Reporting**
- Emit a metrics table (JSON + Markdown). This table goes in the README. **Report real numbers.**
  If recall is 0.72, it's 0.72 — no rounding up, no cherry-picking the best scenario. Honest metrics
  are the entire point and the strongest interview signal.

## 5. Fixtures & data

- Small hand-authored fixtures for unit/integration (checked into `tests/fixtures/`).
- Synthetic scenarios (DATA_GENERATION.md) for eval — regenerated from seeds, not committed as images.
- A tiny "hard" scenario (noisy image) to prove confidence gating flags low-confidence reads.

## 6. What NOT to test

- Don't unit-test the VLM's raw accuracy in unit tests (non-deterministic, rate-limited) — that's
  the eval layer's job with real metrics.
- Don't assert exact confidence floats; assert threshold behavior (`>= t` → trusted, `< t` → review).

## 7. CI (lightweight)

- On push: `ruff`, `mypy` (advisory), unit + integration tests. **Not** eval (needs API keys/quota).
- Eval is a manual `make eval` / script run, results pasted into the writeup.

## 8. Definition of done (per feature)

A feature is done when: it has unit tests, integration tests pass with a mocked VLM, it doesn't
violate an ARCHITECTURE invariant, and (if it touches extraction/reconciliation) the eval numbers
didn't regress.
