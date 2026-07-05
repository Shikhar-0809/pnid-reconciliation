"""Load instrument index CSV and datasheet JSON files into schemas."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from pnid_recon.schemas.sources import Datasheet, IndexRow


def load_index_csv(path: Path | str) -> list[IndexRow]:
    """Parse an instrument index CSV into IndexRow models."""
    csv_path = Path(path)
    rows: list[IndexRow] = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            properties: dict[str, str] = {}
            if raw.get("design_pressure"):
                properties["design_pressure"] = raw["design_pressure"]
            if raw.get("range"):
                properties["range"] = raw["range"]
            rows.append(
                IndexRow(
                    tag=raw["tag"],
                    instrument_type=raw.get("instrument_type") or None,
                    service=raw.get("service") or None,
                    pid_ref=raw.get("pid_ref") or None,
                    properties=properties,
                )
            )
    return rows


def load_datasheets(directory: Path | str) -> list[Datasheet]:
    """Load all JSON datasheets from a directory."""
    datasheet_dir = Path(directory)
    datasheets: list[Datasheet] = []
    for path in sorted(datasheet_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        datasheets.append(Datasheet.model_validate(payload))
    return datasheets
