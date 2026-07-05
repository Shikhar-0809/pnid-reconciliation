"""Reconciliation engine — matching, rules, and conflict emission."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from pnid_recon.reconciliation.match import MatchedSet, MatchResult, match_entities
from pnid_recon.reconciliation.normalize import values_conflict
from pnid_recon.reconciliation.rules import RULES, RuleSpec
from pnid_recon.schemas.conflicts import (
    Conflict,
    ConflictReport,
    ConflictType,
    Severity,
)
from pnid_recon.schemas.extraction import ExtractionResult
from pnid_recon.schemas.sources import Datasheet, IndexRow

TextCompleteFn = Callable[[str], str]


def reconcile(
    extraction: ExtractionResult,
    index_rows: list[IndexRow],
    datasheets: list[Datasheet],
    *,
    text_complete_fn: TextCompleteFn | None = None,
) -> ConflictReport:
    """Run reconciliation and return a provenance-complete conflict report."""
    match_result = match_entities(
        extraction,
        index_rows,
        datasheets,
        text_complete_fn=text_complete_fn,
    )

    conflicts: list[Conflict] = []
    conflicts.extend(_duplicate_tag_conflicts(match_result))
    conflicts.extend(_missing_in_index_conflicts(match_result))
    conflicts.extend(_missing_in_pid_conflicts(match_result))
    conflicts.extend(_rule_conflicts(match_result.rule_targets))

    return ConflictReport(
        conflicts=conflicts,
        summary=_build_summary(conflicts),
        generated_at=datetime.now(tz=UTC).isoformat(),
    )


def _duplicate_tag_conflicts(match_result: MatchResult) -> list[Conflict]:
    conflicts: list[Conflict] = []
    for _tag, rows in sorted(match_result.duplicate_index_tags.items()):
        tag_label = rows[0].tag
        conflicts.append(
            Conflict(
                conflict_type=ConflictType.DUPLICATE_TAG,
                severity=Severity.LOW,
                tag=tag_label,
                sources=["index"],
                values={"index": tag_label},
                message=(
                    f"Tag {tag_label} appears more than once in the instrument index."
                ),
            )
        )
    return conflicts


def _missing_in_index_conflicts(match_result: MatchResult) -> list[Conflict]:
    conflicts: list[Conflict] = []
    for instrument in match_result.unmatched_pid:
        conflicts.append(
            Conflict(
                conflict_type=ConflictType.MISSING_IN_INDEX,
                severity=Severity.MEDIUM,
                tag=instrument.tag,
                sources=["pid", "index"],
                values={"pid": instrument.tag},
                message=(
                    f"Instrument {instrument.tag} is on the P&ID "
                    "but missing from the index."
                ),
                low_confidence_input=instrument.needs_review,
            )
        )
    return conflicts


def _missing_in_pid_conflicts(match_result: MatchResult) -> list[Conflict]:
    conflicts: list[Conflict] = []
    for row in match_result.unmatched_index:
        conflicts.append(
            Conflict(
                conflict_type=ConflictType.MISSING_IN_PID,
                severity=Severity.MEDIUM,
                tag=row.tag,
                sources=["index", "pid"],
                values={"index": row.tag},
                message=f"Instrument {row.tag} is in the index but not on the P&ID.",
            )
        )
    return conflicts


def _rule_conflicts(rule_targets: list[MatchedSet]) -> list[Conflict]:
    conflicts: list[Conflict] = []
    for matched in rule_targets:
        for rule in RULES:
            conflict = _apply_rule(matched, rule)
            if conflict is not None:
                conflicts.append(conflict)
    return conflicts


def _apply_rule(matched: MatchedSet, rule: RuleSpec) -> Conflict | None:
    conflict_type = rule["conflict_type"]

    if conflict_type == ConflictType.MISSING_DATASHEET:
        return _missing_datasheet_conflict(matched, rule)
    if conflict_type == ConflictType.VALUE_MISMATCH:
        return _value_mismatch_conflict(matched, rule)
    if conflict_type == ConflictType.TYPE_MISMATCH:
        return _type_mismatch_conflict(matched, rule)
    return None


def _missing_datasheet_conflict(matched: MatchedSet, rule: RuleSpec) -> Conflict | None:
    if matched.pid is None or matched.index is None or matched.datasheet is not None:
        return None

    tag = matched.pid.tag if matched.pid is not None else matched.index.tag
    return Conflict(
        conflict_type=rule["conflict_type"],
        severity=rule["severity"],
        tag=tag,
        sources=["index", "datasheet"],
        values={"index": tag},
        message=f"No datasheet found for instrument {tag}.",
        low_confidence_input=matched.low_confidence_input,
    )


def _value_mismatch_conflict(matched: MatchedSet, rule: RuleSpec) -> Conflict | None:
    field = rule.get("field")
    compare = rule.get("compare")
    if (
        field is None
        or compare is None
        or matched.pid is None
        or matched.datasheet is None
    ):
        return None

    pid_value = _field_value(matched.pid.properties, field)
    datasheet_value = _field_value(matched.datasheet.properties, field)
    if not values_conflict(pid_value, datasheet_value, compare):
        return None

    return Conflict(
        conflict_type=rule["conflict_type"],
        severity=rule["severity"],
        tag=matched.pid.tag,
        field=field,
        sources=["pid", "datasheet"],
        values={"pid": pid_value, "datasheet": datasheet_value},
        message=(
            f"{field.replace('_', ' ').title()} for {matched.pid.tag} differs between "
            f"P&ID ({pid_value}) and datasheet ({datasheet_value})."
        ),
        low_confidence_input=matched.low_confidence_input,
    )


def _type_mismatch_conflict(matched: MatchedSet, rule: RuleSpec) -> Conflict | None:
    compare = rule.get("compare", "exact_insensitive")
    if matched.pid is None or matched.index is None:
        return None

    pid_type = matched.pid.instrument_type or ""
    index_type = matched.index.instrument_type or ""
    if not values_conflict(pid_type, index_type, compare):
        return None

    return Conflict(
        conflict_type=rule["conflict_type"],
        severity=rule["severity"],
        tag=matched.pid.tag,
        field="instrument_type",
        sources=["pid", "index"],
        values={"pid": pid_type, "index": index_type},
        message=(
            f"Instrument type for {matched.pid.tag} differs between P&ID "
            f"({pid_type}) and index ({index_type})."
        ),
        low_confidence_input=matched.low_confidence_input,
    )


def _field_value(properties: dict[str, str], field: str) -> str:
    return properties.get(field, "")


def _build_summary(conflicts: list[Conflict]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for conflict in conflicts:
        type_key = conflict.conflict_type.value
        summary[type_key] = summary.get(type_key, 0) + 1
        severity_key = f"severity:{conflict.severity.value}"
        summary[severity_key] = summary.get(severity_key, 0) + 1
    return summary
