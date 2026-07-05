"""Scenario generator: P&ID render, index CSV, datasheets, and ground truth."""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

from data_gen.inject_conflicts import (
    T0_INJECTOR_ORDER,
    T1_INJECTOR_ORDER,
    inject_conflicts,
)
from data_gen.instruments import sample_instruments
from data_gen.models import GroundTruth, SeedMetadata, TruthInstrument
from data_gen.render import render_pid
from pnid_recon.schemas.sources import Datasheet, IndexRow

DEFAULT_SEED = 42
DEFAULT_SCENARIO_ID = "scenario_001"
DEFAULT_TIER = "T0"


def generate_scenario(
    output_dir: Path,
    *,
    seed: int = DEFAULT_SEED,
    tier: str = DEFAULT_TIER,
    scenario_id: str = DEFAULT_SCENARIO_ID,
) -> GroundTruth:
    """Generate a full synthetic scenario directory from a deterministic seed."""
    if tier not in {"T0", "T1"}:
        msg = f"Unsupported tier {tier!r}; supported tiers: T0, T1"
        raise ValueError(msg)

    rng = random.Random(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    instruments = sample_instruments(rng, tier)
    instruments = render_pid(
        instruments,
        output_dir / "pid.svg",
        output_dir / "pid.png",
        tier=tier,
    )

    index_rows = [_instrument_to_index_row(inst) for inst in instruments]
    datasheets = [_instrument_to_datasheet(inst) for inst in instruments]

    perturbed_index, perturbed_datasheets, conflicts = inject_conflicts(
        rng,
        instruments,
        index_rows,
        datasheets,
        tier=tier,
    )

    write_index_csv(perturbed_index, output_dir / "instrument_index.csv")
    write_datasheets(perturbed_datasheets, output_dir / "datasheets")

    ground_truth = GroundTruth(
        scenario_id=scenario_id,
        tier=tier,
        seed=seed,
        instruments=instruments,
        seeded_conflicts=conflicts,
    )
    write_ground_truth(ground_truth, output_dir / "ground_truth.json")

    injector_order = T0_INJECTOR_ORDER if tier == "T0" else T1_INJECTOR_ORDER
    seed_metadata = SeedMetadata(
        seed=seed,
        tier=tier,
        instrument_count=len(instruments),
        injector_ids=list(injector_order),
    )
    write_seed_metadata(seed_metadata, output_dir / "seed.json")

    return ground_truth


def _instrument_to_index_row(instrument: TruthInstrument) -> IndexRow:
    properties: dict[str, str] = {"range": instrument.range}
    if instrument.show_pressure_on_drawing:
        properties["design_pressure"] = instrument.design_pressure
    return IndexRow(
        tag=instrument.tag,
        instrument_type=instrument.instrument_type,
        service=instrument.service,
        pid_ref="DWG-001",
        properties=properties,
    )


def _instrument_to_datasheet(instrument: TruthInstrument) -> Datasheet:
    return Datasheet(
        tag=instrument.tag,
        manufacturer=instrument.manufacturer,
        model=instrument.model,
        properties={
            "design_pressure": instrument.design_pressure,
            "range": instrument.range,
        },
    )


def write_index_csv(rows: list[IndexRow], path: Path) -> None:
    """Write instrument index rows to CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "tag",
        "instrument_type",
        "service",
        "pid_ref",
        "design_pressure",
        "range",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "tag": row.tag,
                    "instrument_type": row.instrument_type or "",
                    "service": row.service or "",
                    "pid_ref": row.pid_ref or "",
                    "design_pressure": row.properties.get("design_pressure", ""),
                    "range": row.properties.get("range", ""),
                }
            )


def write_datasheets(datasheets: list[Datasheet], directory: Path) -> None:
    """Write one JSON datasheet per instrument."""
    directory.mkdir(parents=True, exist_ok=True)
    for existing in directory.glob("*.json"):
        existing.unlink()
    for sheet in datasheets:
        path = directory / f"{sheet.tag}.json"
        path.write_text(
            json.dumps(sheet.model_dump(), indent=2) + "\n",
            encoding="utf-8",
        )


def write_ground_truth(ground_truth: GroundTruth, path: Path) -> None:
    """Serialize ground truth for eval comparison."""
    path.write_text(
        json.dumps(ground_truth.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )


def write_seed_metadata(metadata: SeedMetadata, path: Path) -> None:
    """Serialize generation seed and parameters."""
    path.write_text(
        json.dumps(metadata.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a synthetic P&ID scenario.")
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help="RNG seed for deterministic generation.",
    )
    parser.add_argument(
        "--tier",
        default=DEFAULT_TIER,
        help="Scenario difficulty tier (T0 or T1).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("scenarios") / DEFAULT_SCENARIO_ID,
        help="Output directory for the scenario.",
    )
    parser.add_argument(
        "--scenario-id",
        default=DEFAULT_SCENARIO_ID,
        help="Scenario identifier stored in ground truth.",
    )
    return parser.parse_args()


def main() -> None:
    """CLI entry point for scenario generation."""
    args = _parse_args()
    ground_truth = generate_scenario(
        args.output,
        seed=args.seed,
        tier=args.tier,
        scenario_id=args.scenario_id,
    )
    print(
        f"Generated {args.output} with {len(ground_truth.instruments)} instruments "
        f"and {len(ground_truth.seeded_conflicts)} seeded conflicts."
    )


if __name__ == "__main__":
    main()
