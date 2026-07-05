"""Eval metric computation and reporting."""

from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import BaseModel

from eval.ground_truth import EvalGroundTruth, EvalSeededConflict
from pnid_recon.schemas.conflicts import Conflict, ConflictReport, ConflictType
from pnid_recon.schemas.extraction import ExtractionResult
from pnid_recon.tagparse.parse import parse_tag


@dataclass(frozen=True)
class BinaryCounts:
    """Raw true/false positive/negative counts."""

    tp: int
    fp: int
    fn: int


class BinaryMetrics(BaseModel):
    """Precision/recall derived from binary counts."""

    tp: int
    fp: int
    fn: int
    precision: float | None
    recall: float | None


class ConflictTypeMetrics(BaseModel):
    """Per-ConflictType reconciliation metrics."""

    tp: int
    fp: int
    fn: int
    precision: float | None
    recall: float | None


class ConfidenceCalibrationMetrics(BaseModel):
    """How well needs_review flags align with extraction errors."""

    flagged_incorrect: int
    flagged_correct: int
    unflagged_incorrect: int
    unflagged_correct: int
    review_precision: float | None
    review_recall: float | None


class ScenarioMetrics(BaseModel):
    """Metrics for one scenario."""

    scenario_id: str
    tier: str
    extraction: BinaryMetrics
    tag_parse: BinaryMetrics
    confidence_calibration: ConfidenceCalibrationMetrics
    conflicts: dict[str, ConflictTypeMetrics]
    false_positive_conflicts: int


class MetricsTable(BaseModel):
    """Aggregate eval output across all scenarios."""

    scenarios: list[ScenarioMetrics]
    aggregate: ScenarioMetrics
    generated_at: str


def compute_scenario_metrics(
    *,
    ground_truth: EvalGroundTruth,
    extraction: ExtractionResult,
    report: ConflictReport,
) -> ScenarioMetrics:
    """Compute all eval metrics for one scenario."""
    gt_tags = {instrument.tag for instrument in ground_truth.instruments}
    predicted_tags = {instrument.tag for instrument in extraction.instruments}

    extraction_counts = _binary_counts(
        predicted=predicted_tags,
        expected=gt_tags,
    )
    tag_parse_counts = _tag_parse_counts(extraction, gt_tags)
    calibration = _confidence_calibration(extraction, gt_tags)
    conflict_metrics, false_positives = _conflict_metrics(
        report.conflicts,
        ground_truth.seeded_conflicts,
    )

    return ScenarioMetrics(
        scenario_id=ground_truth.scenario_id,
        tier=ground_truth.tier,
        extraction=_metrics_from_counts(extraction_counts),
        tag_parse=_metrics_from_counts(tag_parse_counts),
        confidence_calibration=calibration,
        conflicts=conflict_metrics,
        false_positive_conflicts=false_positives,
    )


def aggregate_metrics(scenarios: list[ScenarioMetrics]) -> ScenarioMetrics:
    """Micro-average metrics across scenarios."""
    if not scenarios:
        return ScenarioMetrics(
            scenario_id="aggregate",
            tier="all",
            extraction=_metrics_from_counts(BinaryCounts(0, 0, 0)),
            tag_parse=_metrics_from_counts(BinaryCounts(0, 0, 0)),
            confidence_calibration=ConfidenceCalibrationMetrics(
                flagged_incorrect=0,
                flagged_correct=0,
                unflagged_incorrect=0,
                unflagged_correct=0,
                review_precision=None,
                review_recall=None,
            ),
            conflicts={},
            false_positive_conflicts=0,
        )

    extraction_counts = BinaryCounts(
        tp=sum(item.extraction.tp for item in scenarios),
        fp=sum(item.extraction.fp for item in scenarios),
        fn=sum(item.extraction.fn for item in scenarios),
    )
    tag_parse_counts = BinaryCounts(
        tp=sum(item.tag_parse.tp for item in scenarios),
        fp=sum(item.tag_parse.fp for item in scenarios),
        fn=sum(item.tag_parse.fn for item in scenarios),
    )

    calibration = ConfidenceCalibrationMetrics(
        flagged_incorrect=sum(
            item.confidence_calibration.flagged_incorrect for item in scenarios
        ),
        flagged_correct=sum(
            item.confidence_calibration.flagged_correct for item in scenarios
        ),
        unflagged_incorrect=sum(
            item.confidence_calibration.unflagged_incorrect for item in scenarios
        ),
        unflagged_correct=sum(
            item.confidence_calibration.unflagged_correct for item in scenarios
        ),
        review_precision=None,
        review_recall=None,
    )
    calibration.review_precision = _safe_ratio(
        calibration.flagged_incorrect,
        calibration.flagged_incorrect + calibration.flagged_correct,
    )
    calibration.review_recall = _safe_ratio(
        calibration.flagged_incorrect,
        calibration.flagged_incorrect + calibration.unflagged_incorrect,
    )

    conflict_types = {conflict_type.value for conflict_type in ConflictType}
    conflicts: dict[str, ConflictTypeMetrics] = {}
    for conflict_type in sorted(conflict_types):
        empty = _empty_type_metrics()
        counts = BinaryCounts(
            tp=sum(
                item.conflicts.get(conflict_type, empty).tp for item in scenarios
            ),
            fp=sum(
                item.conflicts.get(conflict_type, empty).fp for item in scenarios
            ),
            fn=sum(
                item.conflicts.get(conflict_type, empty).fn for item in scenarios
            ),
        )
        conflicts[conflict_type] = ConflictTypeMetrics(
            tp=counts.tp,
            fp=counts.fp,
            fn=counts.fn,
            precision=_safe_ratio(counts.tp, counts.tp + counts.fp),
            recall=_safe_ratio(counts.tp, counts.tp + counts.fn),
        )

    fp_conflicts = sum(item.false_positive_conflicts for item in scenarios)
    return ScenarioMetrics(
        scenario_id="aggregate",
        tier="all",
        extraction=_metrics_from_counts(extraction_counts),
        tag_parse=_metrics_from_counts(tag_parse_counts),
        confidence_calibration=calibration,
        conflicts=conflicts,
        false_positive_conflicts=fp_conflicts,
    )


def metrics_to_json(table: MetricsTable) -> str:
    """Serialize metrics table to JSON without rounding."""
    return json.dumps(table.model_dump(mode="json"), indent=2) + "\n"


def metrics_to_markdown(table: MetricsTable) -> str:
    """Render metrics table as Markdown."""
    header = (
        "| Scenario | Tier | Extraction P | Extraction R | "
        "Tag Parse Acc | FP Conflicts |"
    )
    lines = [
        "# Eval Metrics",
        "",
        f"Generated at: {table.generated_at}",
        "",
        "## Scenario Summary",
        "",
        header,
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]

    for scenario in table.scenarios:
        ext_p = _fmt(scenario.extraction.precision)
        ext_r = _fmt(scenario.extraction.recall)
        tag_acc = _fmt(scenario.tag_parse.precision)
        fp_count = scenario.false_positive_conflicts
        lines.append(
            f"| {scenario.scenario_id} | {scenario.tier} | "
            f"{ext_p} | {ext_r} | {tag_acc} | {fp_count} |"
        )

    aggregate = table.aggregate
    ext = aggregate.extraction
    tag = aggregate.tag_parse
    cal = aggregate.confidence_calibration
    lines.extend(
        [
            "",
            "## Aggregate Metrics",
            "",
            "### Extraction",
            "",
            f"- Precision: {_fmt(ext.precision)} "
            f"(tp={ext.tp}, fp={ext.fp}, fn={ext.fn})",
            f"- Recall: {_fmt(ext.recall)}",
            "",
            "### Tag Parse",
            "",
            f"- Accuracy: {_fmt(tag.precision)} "
            f"(tp={tag.tp}, fp={tag.fp}, "
            f"fn={tag.fn})",
            "",
            "### Confidence Calibration",
            "",
            f"- Review precision: {_fmt(cal.review_precision)}",
            f"- Review recall: {_fmt(cal.review_recall)}",
            f"- Flagged incorrect: {cal.flagged_incorrect}",
            f"- Flagged correct: {cal.flagged_correct}",
            f"- Unflagged incorrect: {cal.unflagged_incorrect}",
            f"- Unflagged correct: {cal.unflagged_correct}",
            "",
            "### Reconciliation By ConflictType",
            "",
            "| ConflictType | TP | FP | FN | Precision | Recall |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )

    for conflict_type, metrics in sorted(aggregate.conflicts.items()):
        lines.append(
            f"| {conflict_type} | {metrics.tp} | {metrics.fp} | {metrics.fn} | "
            f"{_fmt(metrics.precision)} | {_fmt(metrics.recall)} |"
        )

    lines.append("")
    return "\n".join(lines)


def _binary_counts(*, predicted: set[str], expected: set[str]) -> BinaryCounts:
    tp = len(predicted & expected)
    fp = len(predicted - expected)
    fn = len(expected - predicted)
    return BinaryCounts(tp=tp, fp=fp, fn=fn)


def _metrics_from_counts(counts: BinaryCounts) -> BinaryMetrics:
    return BinaryMetrics(
        tp=counts.tp,
        fp=counts.fp,
        fn=counts.fn,
        precision=_safe_ratio(counts.tp, counts.tp + counts.fp),
        recall=_safe_ratio(counts.tp, counts.tp + counts.fn),
    )


def _tag_parse_counts(
    extraction: ExtractionResult,
    gt_tags: set[str],
) -> BinaryCounts:
    tp = 0
    fp = 0
    predicted_tags = {instrument.tag for instrument in extraction.instruments}

    for instrument in extraction.instruments:
        if instrument.tag not in gt_tags:
            continue
        expected = parse_tag(instrument.tag)
        actual = instrument.parsed_tag or parse_tag(instrument.tag)
        parse_ok = (
            expected.parse_ok
            and actual.parse_ok
            and _parsed_tags_equal(expected, actual)
        )
        if parse_ok:
            tp += 1
        else:
            fp += 1

    fn = len(gt_tags - predicted_tags)
    return BinaryCounts(tp=tp, fp=fp, fn=fn)


def _parsed_tags_equal(left, right) -> bool:
    return (
        left.measured_variable == right.measured_variable
        and left.function == right.function
        and left.loop_number == right.loop_number
    )


def _confidence_calibration(
    extraction: ExtractionResult,
    gt_tags: set[str],
) -> ConfidenceCalibrationMetrics:
    flagged_incorrect = 0
    flagged_correct = 0
    unflagged_incorrect = 0
    unflagged_correct = 0

    for instrument in extraction.instruments:
        incorrect = instrument.tag not in gt_tags
        if instrument.needs_review:
            if incorrect:
                flagged_incorrect += 1
            else:
                flagged_correct += 1
        elif incorrect:
            unflagged_incorrect += 1
        else:
            unflagged_correct += 1

    return ConfidenceCalibrationMetrics(
        flagged_incorrect=flagged_incorrect,
        flagged_correct=flagged_correct,
        unflagged_incorrect=unflagged_incorrect,
        unflagged_correct=unflagged_correct,
        review_precision=_safe_ratio(
            flagged_incorrect,
            flagged_incorrect + flagged_correct,
        ),
        review_recall=_safe_ratio(
            flagged_incorrect,
            flagged_incorrect + unflagged_incorrect,
        ),
    )


def _conflict_metrics(
    predicted: list[Conflict],
    seeded: list[EvalSeededConflict],
) -> tuple[dict[str, ConflictTypeMetrics], int]:
    predicted_keys = {_conflict_key(conflict) for conflict in predicted}
    seeded_keys = {_seeded_conflict_key(conflict) for conflict in seeded}

    false_positives = len(predicted_keys - seeded_keys)
    metrics: dict[str, ConflictTypeMetrics] = {}

    for conflict_type in ConflictType:
        type_predicted = {
            key for key in predicted_keys if key[0] == conflict_type.value
        }
        type_seeded = {key for key in seeded_keys if key[0] == conflict_type.value}
        counts = _binary_counts(predicted=type_predicted, expected=type_seeded)
        metrics[conflict_type.value] = ConflictTypeMetrics(
            tp=counts.tp,
            fp=counts.fp,
            fn=counts.fn,
            precision=_safe_ratio(counts.tp, counts.tp + counts.fp),
            recall=_safe_ratio(counts.tp, counts.tp + counts.fn),
        )

    return metrics, false_positives


def _conflict_key(conflict: Conflict) -> tuple[str, str, str | None]:
    return (conflict.conflict_type.value, conflict.tag, conflict.field)


def _seeded_conflict_key(conflict: EvalSeededConflict) -> tuple[str, str, str | None]:
    return (conflict.conflict_type.value, conflict.tag, conflict.field)


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _fmt(value: float | None) -> str:
    if value is None:
        return "n/a"
    return str(value)


def _empty_type_metrics() -> ConflictTypeMetrics:
    return ConflictTypeMetrics(tp=0, fp=0, fn=0, precision=None, recall=None)
