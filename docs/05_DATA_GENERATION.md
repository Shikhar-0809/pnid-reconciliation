# Data Generation

> **This is the real blocker, not the ML.** You cannot buy or easily download matched
> P&ID + index + datasheet sets with known conflicts. You generate them. Nail this first —
> everything downstream depends on it. Build the generator BEFORE the extraction pipeline.

## 1. Why synthetic

- Real P&IDs are proprietary and scarce; matched multi-document sets essentially don't exist publicly.
- We NEED ground truth (true instrument list + true seeded conflicts) to report honest metrics.
- Synthetic generation gives full control: we author the drawing AND the deliberate disagreements,
  so we always know the correct answer.

**Credibility note:** because the VLM must *read the rendered image* to extract, the extraction step
is still a genuine vision task — the model doesn't get the answer key. Reconciliation then runs on
what the model actually saw. That's what makes results defensible (see the brutal-review reasoning
in the project history / interview talking points).

## 2. What each scenario contains

```
scenarios/scenario_001/
  pid.png                 # rendered P&ID image (the thing the VLM reads)
  pid.svg                 # source SVG (for debugging / regeneration)
  instrument_index.csv    # the index spreadsheet
  datasheets/             # one JSON per instrument (or per type)
  ground_truth.json       # true instruments + true seeded conflicts
  seed.json               # RNG seed + generation params (reproducibility)
```

## 3. Generation pipeline

1. **Sample a plant fragment.** Pick N instruments (start N≤10) with valid ISA 5.1 tags
   (mix of PT/TT/FT/LT + a controller/valve). Assign properties (design pressure, range).
2. **Render the P&ID (SVG → PNG).** Use `svgwrite`: draw instrument bubbles with tags inside,
   a few equipment rectangles, connecting lines. Keep it clean and legible for MVP — this is a
   *readability* test of the VLM, not a stress test. Vary layout/spacing across scenarios.
3. **Emit the index CSV** from the same source-of-truth instrument list.
4. **Emit datasheets** (JSON) from the same source of truth.
5. **Inject conflicts deliberately** (the key step) — perturb copies AFTER the clean set exists,
   recording each perturbation in `ground_truth.json`. Conflict injectors:
   - drop an instrument from the index → MISSING_IN_INDEX
   - add a phantom row to the index → MISSING_IN_PID
   - remove a datasheet → MISSING_DATASHEET
   - change a datasheet's design_pressure → VALUE_MISMATCH (HIGH)
   - change a type in the index → TYPE_MISMATCH
   - duplicate a tag → DUPLICATE_TAG
6. **Write ground_truth.json** listing true instruments and every injected conflict with its type,
   tag, and expected severity.

## 4. Difficulty ladder (don't start hard)

| Tier | Instruments | Rendering | Purpose |
|---|---|---|---|
| T0 | 3–5 | Large, clean, high-contrast tags | Prove the pipeline runs at all |
| T1 | 8–12 | Normal spacing, a few equipment shapes | MVP target |
| T2 | 15–25 | Denser, some rotation/noise | Stretch, post-MVP |
| T3 | multi-sheet | continuation arrows | OUT OF SCOPE (later project) |

**Build and validate on T0 first.** If extraction can't read 4 clean bubbles, denser data won't help.

## 5. Determinism

- Every scenario is generated from a seed. Same seed → identical scenario. Store the seed.
- This makes eval reproducible and lets you regenerate the whole set on demand.

## 6. Optional realism boost (post-MVP, only if needed)

- Add slight image noise/blur to test confidence gating (low-confidence reads SHOULD get flagged).
- Hand-trace 2–3 real public example P&IDs (from textbooks/vendor samples) as a tiny "real-world"
  holdout to sanity-check that the model didn't just learn your synthetic style. Keep it small.

## 7. Anti-drift for data

- Do NOT let the generator balloon into a full P&ID CAD tool. It renders *enough* to be readable
  and to carry conflicts. Legibility > visual fidelity.
- The generator is the source of truth for ground truth. If a schema changes (DATA_MODEL.md),
  the generator and ground_truth format change together — never independently.
