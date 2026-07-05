"""Tests for synthetic scenario generation."""

from __future__ import annotations

from pathlib import Path

from data_gen.generate import generate_scenario


def test_generate_t1_scenario_has_eight_to_twelve_instruments(tmp_path: Path) -> None:
    output_dir = tmp_path / "scenario_t1"
    ground_truth = generate_scenario(
        output_dir,
        seed=100,
        tier="T1",
        scenario_id="scenario_t1_test",
    )

    assert ground_truth.tier == "T1"
    assert 8 <= len(ground_truth.instruments) <= 12
    assert len(ground_truth.seeded_conflicts) == 6
    assert (output_dir / "pid.png").is_file()
    assert (output_dir / "ground_truth.json").is_file()
    assert (output_dir / "instrument_index.csv").is_file()
    assert any(output_dir.glob("datasheets/*.json"))
