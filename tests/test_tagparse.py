"""Unit tests for ISA 5.1 tag parsing."""

from __future__ import annotations

import pytest

from pnid_recon.schemas.extraction import ParsedTag
from pnid_recon.tagparse.parse import parse_tag

VALID_TAG_CASES: list[tuple[str, str, str, str]] = [
    ("PT-101", "Pressure", "Transmitter", "101"),
    ("TT-102", "Temperature", "Transmitter", "102"),
    ("FT-103", "Flow", "Transmitter", "103"),
    ("LT-104", "Level", "Transmitter", "104"),
    ("AT-201", "Analysis", "Transmitter", "201"),
    ("FIC-200", "Flow", "Indicating Controller", "200"),
    ("PIC-106", "Pressure", "Indicating Controller", "106"),
    ("TIC-107", "Temperature", "Indicating Controller", "107"),
    ("LCV-106", "Level", "Control Valve", "106"),
    ("LSH-305", "Level", "Switch High", "305"),
    ("LSL-310", "Level", "Switch Low", "310"),
    ("LAL-401", "Level", "Alarm Low", "401"),
    ("LAH-402", "Level", "Alarm High", "402"),
    ("FV-110", "Flow", "Valve", "110"),
    ("FE-120", "Flow", "Element", "120"),
    ("PCV-130", "Pressure", "Control Valve", "130"),
    ("TE-220", "Temperature", "Element", "220"),
    ("LS-330", "Level", "Switch", "330"),
]

MALFORMED_TAG_CASES: list[str] = [
    "",
    "   ",
    "PT101",
    "PT 101",
    "PT-",
    "-101",
    "101",
    "PT--101",
    "PT-10A",
    "PT-10.5",
    "X-101",
    "P-101",
    "PT-101A",
    "PT-101 extra",
    "PT-\n101",
    "???",
    "PT--",
    "ABC",
    "PT-",
    "T-101",
    "ZX-101",
]


@pytest.mark.parametrize(
    ("tag", "measured_variable", "function", "loop_number"),
    VALID_TAG_CASES,
)
def test_parse_valid_tags(
    tag: str,
    measured_variable: str,
    function: str,
    loop_number: str,
) -> None:
    """Valid ISA 5.1 tags decompose into expected ParsedTag fields."""
    result = parse_tag(tag)
    assert result == ParsedTag(
        raw=tag,
        measured_variable=measured_variable,
        function=function,
        loop_number=loop_number,
        parse_ok=True,
    )


@pytest.mark.parametrize("tag", MALFORMED_TAG_CASES)
def test_parse_malformed_tags(tag: str) -> None:
    """Malformed or unknown tags must never be guessed — parse_ok=False."""
    result = parse_tag(tag)
    assert result.parse_ok is False
    assert result.measured_variable is None
    assert result.function is None
    assert result.loop_number is None
    assert result.raw == tag


def test_parse_preserves_original_raw_string() -> None:
    """Whitespace trimming applies to parsing only; raw stores the original input."""
    result = parse_tag("  pt-101  ")
    assert result.raw == "  pt-101  "
    assert result.parse_ok is True
    assert result.measured_variable == "Pressure"
    assert result.function == "Transmitter"
    assert result.loop_number == "101"


def test_parse_normalizes_case_for_matching() -> None:
    """Tag letters are matched case-insensitively after strip."""
    result = parse_tag("fic-200")
    assert result.parse_ok is True
    assert result.measured_variable == "Flow"
    assert result.function == "Indicating Controller"
    assert result.loop_number == "200"
