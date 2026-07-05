"""Unit tests for value and tag normalization."""

from __future__ import annotations

import pytest

from pnid_recon.reconciliation.normalize import (
    normalize_tag,
    parse_numeric_with_unit,
    values_conflict,
    values_equal,
)


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ("50 bar", "50 BAR", True),
        ("50 bar", "50bar", True),
        ("50 bar", "40 bar", False),
        ("50 bar", "50 psi", False),
    ],
)
def test_values_equal_numeric_with_unit(left: str, right: str, expected: bool) -> None:
    assert values_equal(left, right, "numeric_with_unit") is expected


def test_normalize_tag_equivalence_for_matchers() -> None:
    assert normalize_tag("PT-101") == normalize_tag("PT 101")


def test_values_conflict_requires_both_values() -> None:
    assert values_conflict("", "40 bar", "numeric_with_unit") is False
    assert values_conflict("50 bar", "40 bar", "numeric_with_unit") is True


def test_normalize_tag_handles_spaced_tags() -> None:
    assert normalize_tag("pt 101") == "PT-101"
    assert normalize_tag("PT-101") == "PT-101"


def test_parse_numeric_with_unit() -> None:
    parsed = parse_numeric_with_unit("50 bar")
    assert parsed is not None
    assert parsed.numeric == 50.0
    assert parsed.unit == "bar"
