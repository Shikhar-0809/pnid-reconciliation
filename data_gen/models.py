"""Internal Pydantic models for scenario generation and ground truth."""

from pydantic import BaseModel, Field

from pnid_recon.schemas.conflicts import ConflictType, Severity
from pnid_recon.schemas.extraction import BoundingBox


class TruthInstrument(BaseModel):
    """Source-of-truth instrument rendered on the P&ID."""

    tag: str
    instrument_type: str
    service: str
    manufacturer: str
    model: str
    design_pressure: str
    range: str
    bbox: BoundingBox | None = None
    show_pressure_on_drawing: bool = False


class SeededConflict(BaseModel):
    """One deliberately injected conflict recorded for eval."""

    conflict_type: ConflictType
    severity: Severity
    tag: str
    field: str | None = None
    sources: list[str]
    values: dict[str, str] = Field(default_factory=dict)
    message: str
    injector_id: str


class GroundTruth(BaseModel):
    """Eval reference: true P&ID instruments and seeded conflicts."""

    scenario_id: str
    tier: str
    seed: int
    instruments: list[TruthInstrument]
    seeded_conflicts: list[SeededConflict]


class SeedMetadata(BaseModel):
    """Reproducibility metadata stored alongside each scenario."""

    seed: int
    tier: str
    instrument_count: int
    injector_ids: list[str]
