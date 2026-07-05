"""Unit tests for eval metric computation."""

from __future__ import annotations

from pathlib import Path

from eval.ground_truth import load_ground_truth
from eval.metrics import (
    aggregate_metrics,
    compute_scenario_metrics,
    metrics_to_json,
    metrics_to_markdown,
)

from pnid_recon.reconciliation.engine import reconcile
from pnid_recon.schemas.conflicts import ConflictType
from pnid_recon.schemas.extraction import ExtractedInstrument, ExtractionResult
from tests.fixtures.reconciliation_fixtures import build_full_conflict_fixture

SCENARIO_DIR = Path("scenarios/scenario_001")


def test_compute_scenario_metrics_perfect_reconciliation() -> None:
    extraction, index_rows, datasheets, _ = build_full_conflict_fixture()
    ground_truth = load_ground_truth(SCENARIO_DIR / "ground_truth.json")
    report = reconcile(extraction, index_rows, datasheets)

    metrics = compute_scenario_metrics(
        ground_truth=ground_truth,
        extraction=extraction,
        report=report,
    )

    assert metrics.extraction.tp == 5
    assert metrics.extraction.fp == 0
    assert metrics.extraction.fn == 0
    assert metrics.extraction.precision == 1.0
    assert metrics.extraction.recall == 1.0
    assert metrics.false_positive_conflicts == 0

    for conflict_type in ConflictType:
        type_metrics = metrics.conflicts[conflict_type.value]
        assert type_metrics.tp == 1
        assert type_metrics.fp == 0
        assert type_metrics.fn == 0
        assert type_metrics.precision == 1.0
        assert type_metrics.recall == 1.0


def test_tag_parse_counts_correct_decompositions() -> None:
    extraction, index_rows, datasheets, _ = build_full_conflict_fixture()
    ground_truth = load_ground_truth(SCENARIO_DIR / "ground_truth.json")
    report = reconcile(extraction, index_rows, datasheets)

    metrics = compute_scenario_metrics(
        ground_truth=ground_truth,
        extraction=extraction,
        report=report,
    )

    assert metrics.tag_parse.tp == 5
    assert metrics.tag_parse.fp == 0
    assert metrics.tag_parse.fn == 0


def test_aggregate_metrics_micro_averages() -> None:
    extraction, index_rows, datasheets, _ = build_full_conflict_fixture()
    ground_truth = load_ground_truth(SCENARIO_DIR / "ground_truth.json")
    report = reconcile(extraction, index_rows, datasheets)
    scenario = compute_scenario_metrics(
        ground_truth=ground_truth,
        extraction=extraction,
        report=report,
    )

    aggregate = aggregate_metrics([scenario, scenario])

    assert aggregate.extraction.tp == 10
    assert aggregate.extraction.fp == 0
    assert aggregate.extraction.fn == 0
    assert aggregate.false_positive_conflicts == 0


def test_metrics_table_serializes_without_rounding() -> None:
    extraction, index_rows, datasheets, _ = build_full_conflict_fixture()
    ground_truth = load_ground_truth(SCENARIO_DIR / "ground_truth.json")
    report = reconcile(extraction, index_rows, datasheets)
    scenario = compute_scenario_metrics(
        ground_truth=ground_truth,
        extraction=extraction,
        report=report,
    )
    from eval.metrics import MetricsTable

    table = MetricsTable(
        scenarios=[scenario],
        aggregate=aggregate_metrics([scenario]),
        generated_at="2026-01-01T00:00:00+00:00",
    )

    payload = metrics_to_json(table)
    assert '"precision": 1.0' in payload
    markdown = metrics_to_markdown(table)
    assert "Eval Metrics" in markdown
    assert "VALUE_MISMATCH" in markdown


def test_extraction_misses_lower_recall() -> None:
    extraction, index_rows, datasheets, _ = build_full_conflict_fixture()
    ground_truth = load_ground_truth(SCENARIO_DIR / "ground_truth.json")
    partial = ExtractionResult(
        source_image=extraction.source_image,
        model_name=extraction.model_name,
        instruments=extraction.instruments[:3],
    )
    report = reconcile(partial, index_rows, datasheets)

    metrics = compute_scenario_metrics(
        ground_truth=ground_truth,
        extraction=partial,
        report=report,
    )

    assert metrics.extraction.tp == 3
    assert metrics.extraction.fn == 2
    assert metrics.extraction.recall == 0.6


def test_wrong_parsed_tag_counts_as_tag_parse_failure() -> None:
    extraction, index_rows, datasheets, _ = build_full_conflict_fixture()
    ground_truth = load_ground_truth(SCENARIO_DIR / "ground_truth.json")
    from pnid_recon.schemas.extraction import ParsedTag

    bad_parse = extraction.model_copy(deep=True)
    bad_parse.instruments[0] = ExtractedInstrument(
        tag="PT-101",
        parsed_tag=ParsedTag(
            raw="PT-101",
            measured_variable="X",
            function="Y",
            loop_number="101",
            parse_ok=True,
        ),
        instrument_type="Pressure Transmitter",
        properties={"design_pressure": "50 bar"},
        confidence=0.95,
    )
    report = reconcile(bad_parse, index_rows, datasheets)

    metrics = compute_scenario_metrics(
        ground_truth=ground_truth,
        extraction=bad_parse,
        report=report,
    )

    assert metrics.tag_parse.tp == 4
    assert metrics.tag_parse.fp == 1
