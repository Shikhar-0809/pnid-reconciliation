"""Parse ISA 5.1 instrument tag strings into ParsedTag schemas."""

from __future__ import annotations

from functools import lru_cache

from lark import Lark, Transformer
from lark.exceptions import LarkError

from pnid_recon.schemas.extraction import ParsedTag
from pnid_recon.tagparse.grammar import ISA_TAG_GRAMMAR

MEASURED_VARIABLE_LABELS: dict[str, str] = {
    "P": "Pressure",
    "T": "Temperature",
    "F": "Flow",
    "L": "Level",
    "A": "Analysis",
}

FUNCTION_TOKEN_LABELS: dict[str, str] = {
    "T": "Transmitter",
    "I": "Indicator",
    "C": "Controller",
    "V": "Valve",
    "E": "Element",
    "S": "Switch",
    "H": "High",
    "L": "Low",
    "AL": "Alarm Low",
    "AH": "Alarm High",
}

FUNCTION_COMBINATIONS: dict[tuple[str, ...], str] = {
    ("T",): "Transmitter",
    ("I",): "Indicator",
    ("C",): "Controller",
    ("V",): "Valve",
    ("E",): "Element",
    ("S",): "Switch",
    ("AL",): "Alarm Low",
    ("AH",): "Alarm High",
    ("S", "H"): "Switch High",
    ("S", "L"): "Switch Low",
    ("I", "C"): "Indicating Controller",
    ("C", "V"): "Control Valve",
}


@lru_cache(maxsize=1)
def _parser() -> Lark:
    """Return a cached Lark parser for ISA 5.1 tags."""
    return Lark(ISA_TAG_GRAMMAR, parser="lalr", maybe_placeholders=False)


class _TagTransformer(Transformer):  # type: ignore[type-arg]
    """Transform a Lark parse tree into letter code and loop number strings."""

    def letters(self, children: list[object]) -> str:
        return str(children[0])

    def loop_number(self, children: list[object]) -> str:
        return str(children[0])

    def tag(self, children: list[str]) -> tuple[str, str]:
        return children[0], children[1]


def parse_tag(raw: str) -> ParsedTag:
    """Parse a tag string into ParsedTag; bad input yields parse_ok=False."""
    normalized = raw.strip().upper()
    if not normalized or any(ch.isspace() for ch in normalized):
        return _failed(raw)

    try:
        tree = _parser().parse(normalized)
    except LarkError:
        return _failed(raw)

    letters, loop_number = _TagTransformer().transform(tree)
    measured_code = letters[0]
    function_tokens = _tokenize_function_letters(letters[1:])
    if function_tokens is None:
        return _failed(raw)

    measured_variable = MEASURED_VARIABLE_LABELS.get(measured_code)
    function = _build_function(function_tokens)

    if measured_variable is None or function is None:
        return _failed(raw)

    return ParsedTag(
        raw=raw,
        measured_variable=measured_variable,
        function=function,
        loop_number=loop_number,
        parse_ok=True,
    )


def _tokenize_function_letters(text: str) -> list[str] | None:
    """Greedy tokenization of function letters (AL/AH before single-letter tokens)."""
    if not text:
        return None

    tokens: list[str] = []
    index = 0
    while index < len(text):
        pair = text[index : index + 2]
        if pair in ("AL", "AH"):
            tokens.append(pair)
            index += 2
            continue

        char = text[index]
        if char in "TICVESH":
            tokens.append(char)
            index += 1
            continue

        if char == "L":
            tokens.append("L")
            index += 1
            continue

        if char == "S":
            tokens.append("S")
            index += 1
            continue

        return None

    return tokens


def _build_function(tokens: list[str]) -> str | None:
    """Map function token sequence to a human-readable function label."""
    combined = FUNCTION_COMBINATIONS.get(tuple(tokens))
    if combined is not None:
        return combined

    if not all(token in FUNCTION_TOKEN_LABELS for token in tokens):
        return None

    return " ".join(FUNCTION_TOKEN_LABELS[token] for token in tokens)


def _failed(raw: str) -> ParsedTag:
    """Return a flagged ParsedTag without guessing missing fields."""
    return ParsedTag(
        raw=raw,
        measured_variable=None,
        function=None,
        loop_number=None,
        parse_ok=False,
    )
