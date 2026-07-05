"""Apply confidence threshold to extraction results."""

from pnid_recon.config import settings
from pnid_recon.schemas.extraction import ExtractionResult


def apply_confidence_threshold(
    result: ExtractionResult,
    *,
    threshold: float | None = None,
) -> ExtractionResult:
    """Flag instruments below the configured confidence threshold for review."""
    cutoff = settings.confidence_threshold if threshold is None else threshold
    updated_instruments = [
        instrument.model_copy(
            update={"needs_review": instrument.confidence < cutoff},
        )
        for instrument in result.instruments
    ]
    return result.model_copy(update={"instruments": updated_instruments})
