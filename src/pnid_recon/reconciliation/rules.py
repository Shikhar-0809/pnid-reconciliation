"""Declarative conflict rule registry — rules are data, not scattered conditionals."""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

from pnid_recon.schemas.conflicts import ConflictType, Severity

CompareMode = Literal["numeric_with_unit", "exact_insensitive"]


class RuleSpec(TypedDict):
    """One declarative reconciliation rule consumed by the engine."""

    id: str
    conflict_type: ConflictType
    severity: Severity
    field: NotRequired[str]
    compare: NotRequired[CompareMode]


RULES: list[RuleSpec] = [
    {
        "id": "missing_datasheet",
        "conflict_type": ConflictType.MISSING_DATASHEET,
        "severity": Severity.MEDIUM,
    },
    {
        "id": "pressure_mismatch",
        "conflict_type": ConflictType.VALUE_MISMATCH,
        "field": "design_pressure",
        "compare": "numeric_with_unit",
        "severity": Severity.HIGH,
    },
    {
        "id": "type_mismatch",
        "conflict_type": ConflictType.TYPE_MISMATCH,
        "field": "instrument_type",
        "compare": "exact_insensitive",
        "severity": Severity.MEDIUM,
    },
]
