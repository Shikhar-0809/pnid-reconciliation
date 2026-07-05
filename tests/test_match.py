"""Unit tests for deterministic entity matching."""

from __future__ import annotations

from pnid_recon.reconciliation.match import match_entities
from pnid_recon.schemas.extraction import ExtractedInstrument, ExtractionResult
from pnid_recon.schemas.sources import Datasheet, IndexRow


def test_deterministic_exact_and_normalized_match() -> None:
    extraction = ExtractionResult(
        source_image="pid.png",
        model_name="mock",
        instruments=[
            ExtractedInstrument(
                tag="PT 101", instrument_type="Pressure Transmitter", confidence=0.9
            ),
        ],
    )
    index_rows = [
        IndexRow(tag="PT-101", instrument_type="Pressure Transmitter"),
    ]
    datasheets = [
        Datasheet(tag="PT-101", properties={"design_pressure": "50 bar"}),
    ]

    result = match_entities(extraction, index_rows, datasheets)
    assert len(result.matched) == 1
    assert result.matched[0].canonical_tag == "PT-101"
    assert result.unmatched_pid == []
    assert result.unmatched_index == []


def test_fuzzy_match_only_runs_on_leftovers() -> None:
    extraction = ExtractionResult(
        source_image="pid.png",
        model_name="mock",
        instruments=[
            ExtractedInstrument(tag="PT-101", confidence=0.9),
            ExtractedInstrument(tag="FT-103", confidence=0.9),
        ],
    )
    index_rows = [
        IndexRow(tag="PT-101"),
        IndexRow(tag="FT-103X"),
    ]

    def fake_text_complete(prompt: str) -> str:
        assert "FT-103" in prompt
        assert "FT-103X" in prompt
        return '[{"pid_tag": "FT-103", "index_tag": "FT-103X"}]'

    result = match_entities(
        extraction,
        index_rows,
        [],
        text_complete_fn=fake_text_complete,
    )
    assert len(result.matched) == 2
    assert result.unmatched_pid == []
    assert result.unmatched_index == []


def test_duplicate_index_rows_do_not_surface_as_missing_in_pid() -> None:
    extraction = ExtractionResult(
        source_image="pid.png",
        model_name="mock",
        instruments=[
            ExtractedInstrument(tag="FT-103", confidence=0.9),
        ],
    )
    index_rows = [
        IndexRow(tag="FT-103"),
        IndexRow(tag="FT-103", service="duplicate row"),
    ]

    result = match_entities(extraction, index_rows, [])

    assert len(result.matched) == 1
    assert result.unmatched_index == []
    assert "FT-103" in result.duplicate_index_tags
