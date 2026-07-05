"""VLM extraction orchestration with caching and confidence gating."""

from __future__ import annotations

import hashlib
import logging
import tempfile
from pathlib import Path

from pnid_recon.config import settings
from pnid_recon.extraction.confidence import apply_confidence_threshold
from pnid_recon.ingest.images import preprocess_image
from pnid_recon.llm.client import extract_from_image
from pnid_recon.llm.prompts import EXTRACTION_PROMPT_VERSION
from pnid_recon.schemas.extraction import ExtractionResult, ExtractedInstrument
from pnid_recon.tagparse.parse import parse_tag

logger = logging.getLogger(__name__)


def extract_pid(image_path: Path | str) -> ExtractionResult:
    """Extract instruments from a P&ID image with cache and confidence gating."""
    path = Path(image_path)
    preprocessed = preprocess_image(str(path))
    cache_key = _build_cache_key(preprocessed)
    cached = _load_cache(cache_key)
    if cached is not None:
        logger.info("Extraction cache hit image=%s", path)
        return apply_confidence_threshold(cached)

    result = _extract_from_preprocessed(path, preprocessed)
    _save_cache(cache_key, result)
    return apply_confidence_threshold(result)


def _extract_from_preprocessed(path: Path, preprocessed: bytes) -> ExtractionResult:
    """Run the VLM on preprocessed PNG bytes and attach tag parse metadata."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(preprocessed)
        tmp_path = Path(tmp.name)

    try:
        result = extract_from_image(tmp_path, model_name=settings.vlm_model_name)
    finally:
        tmp_path.unlink(missing_ok=True)

    result = result.model_copy(update={"source_image": str(path)})
    return _attach_parsed_tags(result)


def _attach_parsed_tags(result: ExtractionResult) -> ExtractionResult:
    """Populate parsed_tag (including parse_ok) for each extracted instrument."""
    instruments: list[ExtractedInstrument] = []
    for instrument in result.instruments:
        instruments.append(
            instrument.model_copy(update={"parsed_tag": parse_tag(instrument.tag)})
        )
    return result.model_copy(update={"instruments": instruments})


def _build_cache_key(preprocessed: bytes) -> str:
    """Hash preprocessed bytes with model and prompt version for cache invalidation."""
    image_hash = hashlib.sha256(preprocessed).hexdigest()
    payload = (
        f"{image_hash}:{settings.vlm_model_name}:{EXTRACTION_PROMPT_VERSION}:"
        f"{settings.extraction_prompt_version}"
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _cache_path(cache_key: str) -> Path:
    return settings.extraction_cache_dir / f"{cache_key}.json"


def _load_cache(cache_key: str) -> ExtractionResult | None:
    """Load a cached ExtractionResult when present."""
    path = _cache_path(cache_key)
    if not path.exists():
        return None
    return ExtractionResult.model_validate_json(path.read_text(encoding="utf-8"))


def _save_cache(cache_key: str, result: ExtractionResult) -> None:
    """Persist an ExtractionResult to the extraction cache."""
    directory = settings.extraction_cache_dir
    directory.mkdir(parents=True, exist_ok=True)
    path = _cache_path(cache_key)
    path.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
