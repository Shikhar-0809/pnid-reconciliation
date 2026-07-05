# Data Model

> The Pydantic schemas here ARE the inter-module contract (ARCHITECTURE.md §2). Modules pass
> these objects, never loose dicts. Changing a schema is a drift event — see ANTI_DRIFT.md.

## 1. Extraction schemas (Half A output)

```python
# schemas/extraction.py
from pydantic import BaseModel, Field
from typing import Literal, Optional

class BoundingBox(BaseModel):
    x: float; y: float; width: float; height: float  # normalized 0..1

class ParsedTag(BaseModel):
    raw: str                          # "PT-101"
    measured_variable: Optional[str]  # "Pressure" (None if unknown)
    function: Optional[str]           # "Transmitter"
    loop_number: Optional[str]        # "101"
    parse_ok: bool                    # False → flagged, never guessed

class ExtractedInstrument(BaseModel):
    tag: str
    parsed_tag: Optional[ParsedTag] = None
    instrument_type: Optional[str] = None      # VLM's read of the type
    properties: dict[str, str] = Field(default_factory=dict)  # e.g. {"design_pressure": "50 bar"}
    bbox: Optional[BoundingBox] = None
    confidence: float = Field(ge=0.0, le=1.0)
    needs_review: bool = False                 # confidence < threshold

class ExtractionResult(BaseModel):
    source_image: str
    instruments: list[ExtractedInstrument]
    model_name: str
    warnings: list[str] = Field(default_factory=list)
```

`instructor` forces the VLM to return `ExtractionResult`. `needs_review` is set post-hoc from
config threshold (TECH_STACK / CODING_PRACTICES).

## 2. Source-document schemas (reconciliation inputs)

```python
# schemas/sources.py
class IndexRow(BaseModel):
    tag: str
    instrument_type: Optional[str] = None
    service: Optional[str] = None
    pid_ref: Optional[str] = None
    properties: dict[str, str] = Field(default_factory=dict)

class Datasheet(BaseModel):
    tag: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    properties: dict[str, str] = Field(default_factory=dict)  # design_pressure, range, etc.
```

## 3. Conflict schemas (Half B output)

```python
# schemas/conflicts.py
from enum import Enum

class ConflictType(str, Enum):
    MISSING_IN_INDEX = "MISSING_IN_INDEX"
    MISSING_IN_PID = "MISSING_IN_PID"
    MISSING_DATASHEET = "MISSING_DATASHEET"
    VALUE_MISMATCH = "VALUE_MISMATCH"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    DUPLICATE_TAG = "DUPLICATE_TAG"

class Severity(str, Enum):
    HIGH = "HIGH"; MEDIUM = "MEDIUM"; LOW = "LOW"

class Conflict(BaseModel):
    conflict_type: ConflictType
    severity: Severity
    tag: str
    field: Optional[str] = None              # for VALUE_MISMATCH
    sources: list[str]                       # provenance: ["pid", "datasheet"]
    values: dict[str, str] = Field(default_factory=dict)  # {"pid": "50 bar", "datasheet": "40 bar"}
    message: str
    low_confidence_input: bool = False       # true if any source item was needs_review

class ConflictReport(BaseModel):
    conflicts: list[Conflict]
    summary: dict[str, int]                  # counts by type/severity
    generated_at: str
```

## 4. Conflict rule registry (rules are DATA, not code)

Rules live in a declarative list the engine iterates. New rule = new entry.

```python
# reconciliation/rules.py — illustrative shape
RULES = [
    {
        "id": "pressure_mismatch",
        "conflict_type": ConflictType.VALUE_MISMATCH,
        "field": "design_pressure",
        "compare": "numeric_with_unit",   # normalize "50 bar" vs "40 bar"
        "severity": Severity.HIGH,
    },
    {
        "id": "missing_datasheet",
        "conflict_type": ConflictType.MISSING_DATASHEET,
        "severity": Severity.MEDIUM,
    },
    # ...
]
```

The engine: match entities across sources → for each matched set, run every applicable rule →
emit `Conflict` objects. Unmatched items produce MISSING_* conflicts.

## 5. Persistence (SQLite)

Minimal tables — mirror the schemas, don't over-normalize:

- `runs(id, source_image, model_name, created_at)`
- `instruments(run_id, tag, json)`  — store the `ExtractedInstrument` as JSON
- `conflicts(run_id, tag, type, severity, json)`

Rationale: portfolio scale; querying by run/tag/severity is all we need. No ORM required —
`sqlite3` + JSON columns is fine.

## 6. Ground-truth schema (for eval — see TESTING.md)

Synthetic data ships with a `ground_truth.json` per scenario: the true instrument list AND the
list of deliberately seeded conflicts, so eval can compute honest precision/recall.
