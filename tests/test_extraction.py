"""Tests for extraction caching, confidence gating, and T0 schema validation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image, ImageFilter

from pnid_recon.extraction.confidence import apply_confidence_threshold
from pnid_recon.extraction.extract import extract_pid
from pnid_recon.llm.client import _VlmExtractionPayload, _VlmInstrumentPayload
from pnid_recon.schemas.extraction import ExtractedInstrument, ExtractionResult

T0_TAGS = ("PT-101", "TT-102", "LT-104", "FIC-105", "FCV-112")


def _t0_extraction_result(*, confidence: float = 0.95) -> ExtractionResult:
    return ExtractionResult(
        source_image="scenarios/scenario_001/pid.png",
        model_name="mock-vlm",
        instruments=[
            ExtractedInstrument(
                tag=tag,
                instrument_type="Instrument",
                confidence=confidence,
            )
            for tag in T0_TAGS
        ],
    )


def test_apply_confidence_threshold_flags_low_confidence() -> None:
    result = _t0_extraction_result(confidence=0.5)
    gated = apply_confidence_threshold(result, threshold=0.7)
    assert all(instrument.needs_review for instrument in gated.instruments)


def test_apply_confidence_threshold_trusts_high_confidence() -> None:
    result = _t0_extraction_result(confidence=0.95)
    gated = apply_confidence_threshold(result, threshold=0.7)
    assert not any(instrument.needs_review for instrument in gated.instruments)


def test_extract_pid_returns_schema_valid_t0_result(tmp_path: Path) -> None:
    image_path = tmp_path / "pid.png"
    Image.new("RGB", (100, 100), "white").save(image_path)
    payload = _VlmExtractionPayload(
        instruments=[
            _VlmInstrumentPayload(tag=tag, instrument_type="Transmitter", confidence=0.92)
            for tag in T0_TAGS
        ],
    )
    expected = ExtractionResult(
        source_image=str(image_path),
        model_name="gemini-2.0-flash",
        instruments=[
            ExtractedInstrument(tag=tag, instrument_type="Transmitter", confidence=0.92)
            for tag in T0_TAGS
        ],
    )

    with (
        patch(
            "pnid_recon.extraction.extract.extract_from_image",
            return_value=expected,
        ),
        patch(
            "pnid_recon.extraction.extract.settings.extraction_cache_dir",
            tmp_path / "cache",
        ),
    ):
        result = extract_pid(image_path)

    assert isinstance(result, ExtractionResult)
    assert {instrument.tag for instrument in result.instruments} == set(T0_TAGS)
    assert result.source_image == str(image_path)


def test_extract_pid_uses_cache_on_second_call(tmp_path: Path) -> None:
    image_path = tmp_path / "pid.png"
    Image.new("RGB", (64, 64), "white").save(image_path)
    expected = _t0_extraction_result()

    with (
        patch("pnid_recon.extraction.extract.settings.extraction_cache_dir", tmp_path),
        patch(
            "pnid_recon.extraction.extract.extract_from_image",
            return_value=expected,
        ) as mock_extract,
    ):
        first = extract_pid(image_path)
        second = extract_pid(image_path)

    assert mock_extract.call_count == 1
    assert first.model_dump() == second.model_dump()


def test_noisy_variant_triggers_needs_review(tmp_path: Path) -> None:
    """Simulate a noisy P&ID read with low VLM confidence."""
    clean_path = tmp_path / "clean.png"
    noisy_path = tmp_path / "noisy.png"
    clean = Image.new("RGB", (200, 200), "white")
    clean.save(clean_path)
    noisy = clean.filter(ImageFilter.GaussianBlur(radius=4))
    noisy.putpixel((10, 10), (120, 120, 120))
    noisy.save(noisy_path)

    clean_result = _t0_extraction_result(confidence=0.95)
    noisy_result = _t0_extraction_result(confidence=0.45)

    with (
        patch(
            "pnid_recon.extraction.extract.extract_from_image",
            side_effect=[clean_result, noisy_result],
        ),
        patch(
            "pnid_recon.extraction.extract.settings.extraction_cache_dir",
            tmp_path / "cache",
        ),
    ):
        clean_gated = extract_pid(clean_path)
        noisy_gated = extract_pid(noisy_path)

    assert not any(i.needs_review for i in clean_gated.instruments)
    assert all(i.needs_review for i in noisy_gated.instruments)


@pytest.mark.skipif(
    not Path(".env").exists(),
    reason="Live Gemini extraction requires a configured .env",
)
def test_live_t0_scenario_extraction_if_configured() -> None:
    """Optional live check against the generated T0 scenario when API key is present."""
    from pnid_recon.config import settings

    if not settings.gemini_api_key or settings.gemini_api_key.startswith("your-"):
        pytest.skip("GEMINI_API_KEY not configured")

    scenario_image = settings.scenarios_dir / "scenario_001" / "pid.png"
    if not scenario_image.exists():
        pytest.skip("T0 scenario image not generated")

    result = extract_pid(scenario_image)
    assert isinstance(result, ExtractionResult)
    assert result.instruments
