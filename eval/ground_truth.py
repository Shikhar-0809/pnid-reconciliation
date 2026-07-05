"""Load scenario ground truth for eval comparison."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from pnid_recon.schemas.conflicts import ConflictType, Severity
from pnid_recon.schemas.extraction import BoundingBox


class EvalInstrument(BaseModel):
    """True instrument on the P&ID from ground_truth.json."""

    tag: str
    instrument_type: str
    service: str
    manufacturer: str
    model: str
    design_pressure: str
    range: str
    bbox: BoundingBox | None = None
    show_pressure_on_drawing: bool = False


class EvalSeededConflict(BaseModel):
    """Seeded conflict reference from ground_truth.json."""

    conflict_type: ConflictType
    severity: Severity
    tag: str
    field: str | None = None
    sources: list[str]
    values: dict[str, str] = Field(default_factory=dict)
    message: str
    injector_id: str


class EvalGroundTruth(BaseModel):
    """Eval reference for one synthetic scenario."""

    scenario_id: str
    tier: str
    seed: int
    instruments: list[EvalInstrument]
    seeded_conflicts: list[EvalSeededConflict]


def load_ground_truth(path: Path | str) -> EvalGroundTruth:
    """Load and validate ground_truth.json."""
    return EvalGroundTruth.model_validate_json(Path(path).read_text(encoding="utf-8"))
