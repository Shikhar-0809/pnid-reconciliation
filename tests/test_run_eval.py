"""Integration tests for the eval harness."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from eval.ground_truth import EvalInstrument, load_ground_truth
from eval.run_eval import discover_scenarios, run_eval

from pnid_recon.extraction.confidence import apply_confidence_threshold
from pnid_recon.schemas.extraction import ExtractedInstrument, ExtractionResult

SCENARIO_DIR = Path("scenarios/scenario_001")


def _mock_extract(image_path: Path) -> ExtractionResult:
    scenario_dir = Path(image_path).parent
    ground_truth = load_ground_truth(scenario_dir / "ground_truth.json")
    instruments = [
        ExtractedInstrument(
            tag=instrument.tag,
            instrument_type=instrument.instrument_type,
            properties=_instrument_properties(instrument),
            confidence=0.92,
        )
        for instrument in ground_truth.instruments
    ]
    extraction = ExtractionResult(
        source_image=str(image_path),
        model_name="mock-vlm",
        instruments=instruments,
    )
    return apply_confidence_threshold(extraction)


def _instrument_properties(instrument: EvalInstrument) -> dict[str, str]:
    properties = {"range": instrument.range}
    if instrument.show_pressure_on_drawing:
        properties["design_pressure"] = instrument.design_pressure
    return properties


def test_discover_scenarios_finds_scenario_001() -> None:
    scenarios = discover_scenarios(Path("scenarios"))
    assert SCENARIO_DIR in scenarios


def test_run_eval_writes_json_and_markdown(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    with patch("eval.run_eval.extract_pid", side_effect=_mock_extract):
        table = run_eval(scenarios_dir=Path("scenarios"), output_dir=output_dir)

    assert (output_dir / "metrics.json").is_file()
    assert (output_dir / "metrics.md").is_file()
    assert table.scenarios[0].scenario_id == "scenario_001"
    assert table.aggregate.extraction.recall == 1.0
    assert table.aggregate.false_positive_conflicts == 0

    json_text = (output_dir / "metrics.json").read_text(encoding="utf-8")
    assert "scenario_001" in json_text
    assert "scenario_002" in json_text
    markdown_text = (output_dir / "metrics.md").read_text(encoding="utf-8")
    assert "DUPLICATE_TAG" in markdown_text
