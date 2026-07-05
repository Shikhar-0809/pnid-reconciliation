"""Entity matching across P&ID extraction, index, and datasheets."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field

from pnid_recon.reconciliation.normalize import normalize_tag
from pnid_recon.schemas.extraction import ExtractedInstrument, ExtractionResult
from pnid_recon.schemas.sources import Datasheet, IndexRow


@dataclass
class MatchedSet:
    """One instrument matched across available source documents."""

    canonical_tag: str
    pid: ExtractedInstrument | None = None
    index: IndexRow | None = None
    datasheet: Datasheet | None = None

    @property
    def low_confidence_input(self) -> bool:
        """True when the P&ID extraction for this tag needs review."""
        return bool(self.pid is not None and self.pid.needs_review)


@dataclass
class MatchResult:
    """Output of deterministic and fuzzy entity matching."""

    matched: list[MatchedSet] = field(default_factory=list)
    rule_targets: list[MatchedSet] = field(default_factory=list)
    unmatched_pid: list[ExtractedInstrument] = field(default_factory=list)
    unmatched_index: list[IndexRow] = field(default_factory=list)
    duplicate_index_tags: dict[str, list[IndexRow]] = field(default_factory=dict)


TextCompleteFn = Callable[[str], str]


def match_entities(
    extraction: ExtractionResult,
    index_rows: list[IndexRow],
    datasheets: list[Datasheet],
    *,
    text_complete_fn: TextCompleteFn | None = None,
) -> MatchResult:
    """Match entities deterministically, then fuzzy-match leftovers via LLM."""
    datasheet_by_tag = {normalize_tag(sheet.tag): sheet for sheet in datasheets}
    index_by_tag: dict[str, list[IndexRow]] = {}
    for row in index_rows:
        key = normalize_tag(row.tag)
        index_by_tag.setdefault(key, []).append(row)

    duplicate_index_tags = {
        tag: rows for tag, rows in index_by_tag.items() if len(rows) > 1
    }

    unmatched_pid = list(extraction.instruments)
    unmatched_index = list(index_rows)
    matched: list[MatchedSet] = []

    _apply_deterministic_matches(
        unmatched_pid, unmatched_index, matched, datasheet_by_tag
    )
    _apply_fuzzy_matches(
        unmatched_pid,
        unmatched_index,
        matched,
        datasheet_by_tag,
        text_complete_fn=text_complete_fn,
    )

    rule_targets = _build_rule_targets(matched, unmatched_pid, datasheet_by_tag)

    pid_keys = {normalize_tag(instrument.tag) for instrument in extraction.instruments}
    unmatched_index = [
        row for row in unmatched_index if normalize_tag(row.tag) not in pid_keys
    ]

    return MatchResult(
        matched=matched,
        rule_targets=rule_targets,
        unmatched_pid=unmatched_pid,
        unmatched_index=unmatched_index,
        duplicate_index_tags=duplicate_index_tags,
    )


def _apply_deterministic_matches(
    unmatched_pid: list[ExtractedInstrument],
    unmatched_index: list[IndexRow],
    matched: list[MatchedSet],
    datasheet_by_tag: dict[str, Datasheet],
) -> None:
    """Exact and normalized tag matches before any LLM call."""
    remaining_pid: list[ExtractedInstrument] = []
    for instrument in unmatched_pid:
        pid_key = normalize_tag(instrument.tag)
        index_row = _pop_index_row(unmatched_index, pid_key)
        if (
            index_row is None
            and normalize_tag(instrument.tag) != instrument.tag.upper()
        ):
            index_row = _pop_index_row(unmatched_index, instrument.tag.upper())

        if index_row is None:
            remaining_pid.append(instrument)
            continue

        matched.append(
            _build_matched_set(
                canonical_tag=pid_key,
                pid=instrument,
                index=index_row,
                datasheet=datasheet_by_tag.get(pid_key),
            )
        )

    unmatched_pid[:] = remaining_pid


def _apply_fuzzy_matches(
    unmatched_pid: list[ExtractedInstrument],
    unmatched_index: list[IndexRow],
    matched: list[MatchedSet],
    datasheet_by_tag: dict[str, Datasheet],
    *,
    text_complete_fn: TextCompleteFn | None,
) -> None:
    """LLM fuzzy-match only for tags still unmatched after deterministic pass."""
    if not unmatched_pid or not unmatched_index or text_complete_fn is None:
        return

    prompt = _build_fuzzy_prompt(unmatched_pid, unmatched_index)
    try:
        response = text_complete_fn(prompt)
    except NotImplementedError:
        return

    pairs = _parse_fuzzy_pairs(response)
    if not pairs:
        return

    consumed_pid: set[str] = set()
    consumed_index: set[str] = set()

    for pid_tag, index_tag in pairs:
        pid_key = normalize_tag(pid_tag)
        index_key = normalize_tag(index_tag)
        if pid_key in consumed_pid or index_key in consumed_index:
            continue

        instrument = _pop_instrument(unmatched_pid, pid_key)
        index_row = _pop_index_row(unmatched_index, index_key)
        if instrument is None or index_row is None:
            continue

        consumed_pid.add(pid_key)
        consumed_index.add(index_key)
        matched.append(
            _build_matched_set(
                canonical_tag=pid_key,
                pid=instrument,
                index=index_row,
                datasheet=datasheet_by_tag.get(index_key),
            )
        )


def _build_fuzzy_prompt(
    unmatched_pid: list[ExtractedInstrument],
    unmatched_index: list[IndexRow],
) -> str:
    pid_tags = [instrument.tag for instrument in unmatched_pid]
    index_tags = [row.tag for row in unmatched_index]
    return (
        "Match instrument tags between a P&ID extraction and an instrument index.\n"
        "Return ONLY a JSON array of objects with keys pid_tag and index_tag for tags "
        "that refer to the same physical instrument.\n"
        "Do not invent tags. Omit pairs you are unsure about.\n\n"
        f"Unmatched P&ID tags: {json.dumps(pid_tags)}\n"
        f"Unmatched index tags: {json.dumps(index_tags)}\n"
    )


def _parse_fuzzy_pairs(response: str) -> list[tuple[str, str]]:
    """Parse LLM JSON response into tag pairs."""
    stripped = response.strip()
    start = stripped.find("[")
    end = stripped.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []

    try:
        payload = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return []

    if not isinstance(payload, list):
        return []

    pairs: list[tuple[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        pid_tag = item.get("pid_tag")
        index_tag = item.get("index_tag")
        if isinstance(pid_tag, str) and isinstance(index_tag, str):
            pairs.append((pid_tag, index_tag))
    return pairs


def _build_matched_set(
    *,
    canonical_tag: str,
    pid: ExtractedInstrument | None,
    index: IndexRow | None,
    datasheet: Datasheet | None,
) -> MatchedSet:
    return MatchedSet(
        canonical_tag=canonical_tag,
        pid=pid,
        index=index,
        datasheet=datasheet,
    )


def _pop_index_row(rows: list[IndexRow], tag_key: str) -> IndexRow | None:
    for index, row in enumerate(rows):
        if normalize_tag(row.tag) == tag_key:
            return rows.pop(index)
    return None


def _pop_instrument(
    instruments: list[ExtractedInstrument],
    tag_key: str,
) -> ExtractedInstrument | None:
    for index, instrument in enumerate(instruments):
        if normalize_tag(instrument.tag) == tag_key:
            return instruments.pop(index)
    return None


def _build_rule_targets(
    matched: list[MatchedSet],
    unmatched_pid: list[ExtractedInstrument],
    datasheet_by_tag: dict[str, Datasheet],
) -> list[MatchedSet]:
    """Build rule targets including pid+datasheet pairs missing from the index."""
    targets = list(matched)
    covered = {item.canonical_tag for item in matched}
    for instrument in unmatched_pid:
        key = normalize_tag(instrument.tag)
        if key in covered:
            continue
        datasheet = datasheet_by_tag.get(key)
        if datasheet is None:
            continue
        targets.append(
            MatchedSet(
                canonical_tag=key,
                pid=instrument,
                index=None,
                datasheet=datasheet,
            )
        )
    return targets
