"""Run the full eval pipeline over synthetic scenarios."""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime
from pathlib import Path

from eval.ground_truth import load_ground_truth
from eval.metrics import (
    MetricsTable,
    ScenarioMetrics,
    aggregate_metrics,
    compute_scenario_metrics,
    metrics_to_json,
    metrics_to_markdown,
)
from pnid_recon.config import settings
from pnid_recon.extraction.extract import extract_pid
from pnid_recon.ingest.documents import load_datasheets, load_index_csv
from pnid_recon.reconciliation.engine import reconcile

logger = logging.getLogger(__name__)


def discover_scenarios(scenarios_dir: Path) -> list[Path]:
    """Return scenario directories containing ground_truth.json."""
    return sorted(
        path.parent
        for path in scenarios_dir.glob("*/ground_truth.json")
        if path.is_file()
    )


def evaluate_scenario(scenario_dir: Path) -> ScenarioMetrics:
    """Run extraction + reconciliation for one scenario and compute metrics."""
    ground_truth_path = scenario_dir / "ground_truth.json"
    image_path = scenario_dir / "pid.png"
    index_path = scenario_dir / "instrument_index.csv"
    datasheets_dir = scenario_dir / "datasheets"

    ground_truth = load_ground_truth(ground_truth_path)
    if not image_path.is_file():
        msg = (
            f"Missing P&ID image for {scenario_dir.name}: {image_path}. "
            "Regenerate with: python -m data_gen.generate --seed 42 "
            f"--output {scenario_dir}"
        )
        raise FileNotFoundError(msg)

    extraction = extract_pid(image_path)
    index_rows = load_index_csv(index_path)
    datasheets = load_datasheets(datasheets_dir)
    report = reconcile(extraction, index_rows, datasheets)

    return compute_scenario_metrics(
        ground_truth=ground_truth,
        extraction=extraction,
        report=report,
    )


def run_eval(
    *,
    scenarios_dir: Path,
    output_dir: Path,
) -> MetricsTable:
    """Evaluate all scenarios and write JSON + Markdown metrics tables."""
    scenario_dirs = discover_scenarios(scenarios_dir)
    if not scenario_dirs:
        msg = f"No scenarios found under {scenarios_dir}"
        raise FileNotFoundError(msg)

    scenario_metrics = [evaluate_scenario(path) for path in scenario_dirs]
    table = MetricsTable(
        scenarios=scenario_metrics,
        aggregate=aggregate_metrics(scenario_metrics),
        generated_at=datetime.now(tz=UTC).isoformat(),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "metrics.json"
    markdown_path = output_dir / "metrics.md"
    json_path.write_text(metrics_to_json(table), encoding="utf-8")
    markdown_path.write_text(metrics_to_markdown(table), encoding="utf-8")

    logger.info("Wrote metrics to %s and %s", json_path, markdown_path)
    return table


def main() -> None:
    """CLI entrypoint for eval runs."""
    parser = argparse.ArgumentParser(
        description="Run full pipeline eval against synthetic scenario ground truth.",
    )
    parser.add_argument(
        "--scenarios-dir",
        type=Path,
        default=settings.scenarios_dir,
        help="Directory containing scenario_* folders",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("eval/output"),
        help="Directory for metrics.json and metrics.md",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    table = run_eval(scenarios_dir=args.scenarios_dir, output_dir=args.output_dir)

    aggregate = table.aggregate
    print(
        f"Eval complete: {len(table.scenarios)} scenario(s), "
        f"extraction recall={aggregate.extraction.recall}, "
        f"aggregate false_positive_conflicts={aggregate.false_positive_conflicts}",
    )


if __name__ == "__main__":
    main()
