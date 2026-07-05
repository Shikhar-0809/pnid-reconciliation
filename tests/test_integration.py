"""Integration tests for reconciliation with a mocked VLM extraction result."""

from __future__ import annotations

from pathlib import Path

from eval.ground_truth import load_ground_truth
from pnid_recon.reconciliation.engine import reconcile
from pnid_recon.schemas.conflicts import ConflictType
from tests.fixtures.reconciliation_fixtures import build_full_conflict_fixture

SCENARIO_DIR = Path("scenarios/scenario_001")


def test_reconciliation_detects_every_conflict_type() -> None:
    extraction, index_rows, datasheets, expected_types = build_full_conflict_fixture()

    report = reconcile(extraction, index_rows, datasheets)

    found_types = {conflict.conflict_type.value for conflict in report.conflicts}
    assert expected_types.issubset(found_types)


def test_every_conflict_has_provenance() -> None:
    extraction, index_rows, datasheets, _ = build_full_conflict_fixture()

    report = reconcile(extraction, index_rows, datasheets)

    assert report.conflicts, "Expected at least one conflict in fixture"
    for conflict in report.conflicts:
        assert conflict.sources, f"{conflict.conflict_type} missing sources"
        assert conflict.values, f"{conflict.conflict_type} missing values"
        assert conflict.message


def test_reconciliation_fixture_matches_seeded_scenario_conflicts() -> None:
    extraction, index_rows, datasheets, _ = build_full_conflict_fixture()
    ground_truth = load_ground_truth(SCENARIO_DIR / "ground_truth.json")

    report = reconcile(extraction, index_rows, datasheets)
    conflicts_by_key = {
        (conflict.conflict_type, conflict.tag): conflict
        for conflict in report.conflicts
    }

    for seeded in ground_truth.seeded_conflicts:
        key = (seeded.conflict_type, seeded.tag)
        assert key in conflicts_by_key, f"Missing seeded conflict {key}"
        found = conflicts_by_key[key]
        assert found.sources == seeded.sources
        assert found.values == seeded.values

    value_mismatch = conflicts_by_key[
        (ConflictType.VALUE_MISMATCH, "PT-101")
    ]
    assert value_mismatch.values["pid"] == "50 bar"
    assert value_mismatch.values["datasheet"] == "40 bar"
