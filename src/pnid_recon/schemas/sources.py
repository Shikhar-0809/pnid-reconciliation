"""Source-document schemas — reconciliation inputs from index and datasheets."""

from pydantic import BaseModel, Field


class IndexRow(BaseModel):
    """One row from the instrument index CSV."""

    tag: str
    instrument_type: str | None = None
    service: str | None = None
    pid_ref: str | None = None
    properties: dict[str, str] = Field(default_factory=dict)


class Datasheet(BaseModel):
    """Per-instrument datasheet specification."""

    tag: str
    manufacturer: str | None = None
    model: str | None = None
    properties: dict[str, str] = Field(default_factory=dict)
