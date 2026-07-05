"""Extraction schemas — Half A VLM output contract."""

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    """Normalized bounding box in 0..1 coordinates."""

    x: float
    y: float
    width: float
    height: float


class ParsedTag(BaseModel):
    """ISA 5.1 tag decomposition."""

    raw: str
    measured_variable: str | None = None
    function: str | None = None
    loop_number: str | None = None
    parse_ok: bool


class ExtractedInstrument(BaseModel):
    """Single instrument extracted from a P&ID image."""

    tag: str
    parsed_tag: ParsedTag | None = None
    instrument_type: str | None = None
    properties: dict[str, str] = Field(default_factory=dict)
    bbox: BoundingBox | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    needs_review: bool = False


class ExtractionResult(BaseModel):
    """Structured output from VLM extraction on one P&ID image."""

    source_image: str
    instruments: list[ExtractedInstrument]
    model_name: str
    warnings: list[str] = Field(default_factory=list)
