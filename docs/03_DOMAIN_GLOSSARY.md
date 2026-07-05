# Domain Glossary

> Read this before writing any extraction or reconciliation logic. The domain drives the schema,
> the rules, and what a "conflict" even means. This is the cheap edge over generic candidates.

## Core documents

- **P&ID (Piping & Instrumentation Diagram)** — the master schematic of a plant. Shows equipment
  (tanks, pumps, vessels), piping, valves, and instruments as standardized symbols, plus how they
  connect. Dense engineering drawings, usually large PDFs.
- **Instrument Index** — a spreadsheet listing every instrument in the plant: tag, type, service,
  location (which P&ID it appears on), sometimes range/rating. The "master list."
- **Datasheet** — a detailed spec document for a single instrument: manufacturer, model, ranges,
  design pressure/temperature, materials, calibration. One per device (or device type).
- **Cause & Effect (C&E) Matrix** — maps trigger conditions to safety actions. (Out of scope for MVP,
  but it's a common reconciliation target — mentioned for interview credibility.)

## Instruments and tags

- **Instrument** — a device that measures or controls a process variable (pressure, flow, level,
  temperature). On a P&ID it's usually a **bubble** (circle) with a tag inside.
- **Instrument Tag** — the unique identifier, e.g. `PT-101`. Follows the **ISA 5.1** standard.
- **Loop** — a set of instruments working together (e.g. a transmitter + controller + valve),
  sharing a **loop number**.

### ISA 5.1 tag structure (the grammar we parse)

A tag like `PT-101` decomposes as:

```
  P        T        -   101
  │        │            │
  │        │            └─ loop number (identifies the control loop)
  │        └────────────── succeeding letter(s): the FUNCTION (Transmitter)
  └─────────────────────── first letter: the MEASURED VARIABLE (Pressure)
```

**First letter (measured variable), common values:**

| Letter | Meaning |
|---|---|
| P | Pressure |
| T | Temperature |
| F | Flow |
| L | Level |
| A | Analysis |

**Succeeding letters (function), common values:**

| Letter | Meaning |
|---|---|
| T | Transmitter |
| I | Indicator |
| C | Controller |
| V | Valve |
| E | Element (sensor) |
| S | Switch |
| AL / AH | Alarm Low / Alarm High |

So `FIC-200` = Flow Indicating Controller, loop 200. `LSH-305` = Level Switch High, loop 305.

> Note: real projects extend ISA 5.1 with company conventions. MVP handles the standard core;
> unknown letters are parsed as `unknown` and flagged, never guessed.

## Reconciliation vocabulary

- **Reconciliation** — cross-checking the same entity across multiple documents to find disagreements.
- **Conflict** — a specific disagreement. Our conflict types (see DATA_MODEL.md):
  - **MISSING_IN_INDEX** — tag on P&ID, absent from instrument index.
  - **MISSING_IN_PID** — tag in index, not found on the drawing (orphaned).
  - **MISSING_DATASHEET** — instrument has no datasheet.
  - **VALUE_MISMATCH** — same field, different values across sources (e.g. design pressure).
  - **TYPE_MISMATCH** — tag decodes to one type on the drawing, another in the index.
  - **DUPLICATE_TAG** — the same tag used for two different instruments.
- **Severity** — HIGH (safety/spec-critical, e.g. pressure mismatch), MEDIUM (missing datasheet),
  LOW (cosmetic/naming). Drives report ordering.
- **Provenance** — for every conflict, which documents and fields disagreed. Never report a
  conflict without it.

## Standards referenced (conceptual only for MVP)

- **ISA 5.1** — instrumentation symbols and identification (our tag grammar).
- **CFIHOS / ISO 15926** — data-handover schemas plants use for enterprise systems. MVP stubs the
  export interface only; do not implement.
