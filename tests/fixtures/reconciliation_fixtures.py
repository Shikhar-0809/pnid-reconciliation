"""Integration fixtures for reconciliation tests (canned ExtractionResult + sources)."""

from __future__ import annotations

from pathlib import Path

from eval.ground_truth import load_ground_truth
from pnid_recon.ingest.documents import load_datasheets, load_index_csv
from pnid_recon.schemas.extraction import ExtractedInstrument, ExtractionResult
from pnid_recon.schemas.sources import Datasheet, IndexRow

SCENARIO_DIR = Path("scenarios/scenario_001")


def build_full_conflict_fixture() -> tuple[
    ExtractionResult,
    list[IndexRow],
    list[Datasheet],
    set[str],
]:
    """Fixture aligned with scenario_001 index, datasheets, and ground truth."""
    ground_truth = load_ground_truth(SCENARIO_DIR / "ground_truth.json")
    instruments = [
        _ground_truth_to_extracted(instrument)
        for instrument in ground_truth.instruments
    ]
    extraction = ExtractionResult(
        source_image=str(SCENARIO_DIR / "pid.png"),
        model_name="mock-vlm",
        instruments=instruments,
    )
    index_rows = load_index_csv(SCENARIO_DIR / "instrument_index.csv")
    datasheets = load_datasheets(SCENARIO_DIR / "datasheets")
    expected_types = {
        conflict.conflict_type.value for conflict in ground_truth.seeded_conflicts
    }
    return extraction, index_rows, datasheets, expected_types


def _ground_truth_to_extracted(instrument) -> ExtractedInstrument:
    properties: dict[str, str] = {"range": instrument.range}
    if instrument.show_pressure_on_drawing:
        properties["design_pressure"] = instrument.design_pressure
    return ExtractedInstrument(
        tag=instrument.tag,
        instrument_type=instrument.instrument_type,
        properties=properties,
        confidence=0.92,
    )
