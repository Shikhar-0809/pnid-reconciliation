"""Conflict schemas — Half B reconciliation output contract."""

from enum import Enum

from pydantic import BaseModel, Field


class ConflictType(str, Enum):
    """Categories of cross-document disagreement."""

    MISSING_IN_INDEX = "MISSING_IN_INDEX"
    MISSING_IN_PID = "MISSING_IN_PID"
    MISSING_DATASHEET = "MISSING_DATASHEET"
    VALUE_MISMATCH = "VALUE_MISMATCH"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    DUPLICATE_TAG = "DUPLICATE_TAG"


class Severity(str, Enum):
    """Conflict severity for triage."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Conflict(BaseModel):
    """One detected conflict with full provenance."""

    conflict_type: ConflictType
    severity: Severity
    tag: str
    field: str | None = None
    sources: list[str]
    values: dict[str, str] = Field(default_factory=dict)
    message: str
    low_confidence_input: bool = False


class ConflictReport(BaseModel):
    """Aggregated reconciliation output."""

    conflicts: list[Conflict]
    summary: dict[str, int]
    generated_at: str
