"""Value and tag normalization for deterministic reconciliation."""

from __future__ import annotations

import re
from dataclasses import dataclass

TAG_PATTERN = re.compile(r"^([A-Z]+)-(\d+)$")
NUMERIC_UNIT_PATTERN = re.compile(
    r"^\s*(-?\d+(?:\.\d+)?)\s*([A-Za-z%/°]+(?:\s+[A-Za-z]+)?)?\s*$",
)


@dataclass(frozen=True)
class ParsedValue:
    """Numeric value with optional unit extracted from an engineering string."""

    numeric: float
    unit: str
    raw: str


def normalize_tag(tag: str) -> str:
    """Normalize a tag for exact/normalized matching (e.g. PT 101 → PT-101)."""
    compact = "".join(tag.upper().split())
    if "-" in compact:
        return compact

    match = re.match(r"^([A-Z]+)(\d+)$", compact)
    if match is not None:
        return f"{match.group(1)}-{match.group(2)}"
    return compact


def parse_numeric_with_unit(value: str) -> ParsedValue | None:
    """Parse strings like '50 bar' or '50BAR' into numeric + unit components."""
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        return None

    match = NUMERIC_UNIT_PATTERN.match(cleaned)
    if match is None:
        return None

    numeric = float(match.group(1))
    unit = (match.group(2) or "").strip().lower()
    return ParsedValue(numeric=numeric, unit=unit, raw=cleaned)


def normalize_text(value: str) -> str:
    """Case-insensitive text normalization for exact-insensitive comparisons."""
    return " ".join(value.strip().lower().split())


def values_equal(left: str, right: str, compare: str) -> bool:
    """Return True when two field values are equivalent under the compare mode."""
    if compare == "numeric_with_unit":
        return _numeric_values_equal(left, right)
    if compare == "exact_insensitive":
        return normalize_text(left) == normalize_text(right)
    return left.strip() == right.strip()


def values_conflict(left: str, right: str, compare: str) -> bool:
    """Return True when both values are present and they disagree."""
    if not left.strip() or not right.strip():
        return False
    return not values_equal(left, right, compare)


def _numeric_values_equal(left: str, right: str) -> bool:
    left_parsed = parse_numeric_with_unit(left)
    right_parsed = parse_numeric_with_unit(right)
    if left_parsed is None or right_parsed is None:
        return normalize_text(left) == normalize_text(right)

    if left_parsed.unit != right_parsed.unit:
        return False
    return left_parsed.numeric == right_parsed.numeric
