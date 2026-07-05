"""Provider-agnostic LLM/VLM client — all model calls route through here."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar, cast

import instructor
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from groq import APIStatusError, BadRequestError, Groq, RateLimitError
from instructor import from_groq
from instructor.exceptions import InstructorRetryException
from instructor.multimodal import Image
from ollama import Client as OllamaClient
from ollama import Options as OllamaOptions
from pydantic import BaseModel, Field, ValidationError

from pnid_recon.config import settings
from pnid_recon.llm.prompts import EXTRACTION_SYSTEM_PROMPT, build_extraction_prompt
from pnid_recon.schemas.extraction import ExtractedInstrument, ExtractionResult

logger = logging.getLogger(__name__)

T = TypeVar("T")


class _VlmInstrumentPayload(BaseModel):
    """Gemini-compatible instrument shape (no open dict fields)."""

    tag: str
    instrument_type: str | None = None
    design_pressure: str | None = Field(
        default=None,
        description=(
            "Design pressure printed on the drawing below or beside the tag "
            "(e.g. '50 bar'); null when not shown"
        ),
    )
    range: str | None = Field(
        default=None,
        description="Instrument range when visible on the drawing; null otherwise",
    )
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


# Maps payload field names to ExtractedInstrument.properties keys (prompt v2).
_VLM_PROPERTY_FIELDS: tuple[tuple[str, str], ...] = (
    ("design_pressure", "design_pressure"),
    ("range", "range"),
)


def _build_instrument_properties(
    instrument: _VlmInstrumentPayload,
) -> dict[str, str]:
    """Copy non-null payload spec fields into the schema properties dict."""
    properties: dict[str, str] = {}
    for payload_field, property_key in _VLM_PROPERTY_FIELDS:
        value = getattr(instrument, payload_field)
        if value:
            properties[property_key] = value
    return properties


class _VlmExtractionPayload(BaseModel):
    """Structured VLM output before ExtractionResult post-processing."""

    instruments: list[_VlmInstrumentPayload]
    warnings: list[str] = Field(default_factory=list)


_GROQ_REFUSAL_PHRASES: tuple[str, ...] = (
    "falls outside",
    "outside of the scope",
    "insufficient",
    "unable to fulfill",
    "unable to execute",
    "exceeds the limitations",
    "not able to complete",
)


def _find_groq_bad_request(exc: BaseException) -> BadRequestError | None:
    """Return a Groq BadRequestError from an exception chain, if present."""
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, BadRequestError):
            return current
        current = current.__cause__
    return None


def _groq_tool_use_error_details(error: BadRequestError) -> dict[str, Any]:
    """Extract the nested Groq error payload from a BadRequestError."""
    body = error.body
    if not isinstance(body, dict):
        return {}
    nested = body.get("error")
    if isinstance(nested, dict):
        return nested
    return {}


def _is_groq_model_refusal(failed_generation: str) -> bool:
    """Return True when failed_generation is a plain-text model refusal."""
    text = failed_generation.strip()
    if not text:
        return False
    if text.startswith("{") or text.startswith("["):
        return False
    lowered = text.lower()
    return any(phrase in lowered for phrase in _GROQ_REFUSAL_PHRASES)


def _parse_groq_failed_generation(failed_generation: str) -> _VlmExtractionPayload | None:
    """Parse Groq failed_generation JSON into a VLM payload when possible."""
    text = failed_generation.strip()
    if not text:
        return None

    try:
        data: object = json.loads(text)
    except json.JSONDecodeError:
        try:
            return _VlmExtractionPayload.model_validate_json(text)
        except ValidationError:
            return None

    if isinstance(data, list) and data:
        data = data[0]
    if isinstance(data, dict) and "_VlmExtractionPayload" in data:
        nested = data["_VlmExtractionPayload"]
        if isinstance(nested, dict):
            data = nested

    if isinstance(data, dict):
        try:
            return _VlmExtractionPayload.model_validate(data)
        except ValidationError:
            return None
    return None


def _recover_groq_tool_use_failure(exc: Exception) -> _VlmExtractionPayload | None:
    """Recover from Groq tool_use_failed refusals or malformed tool JSON."""
    bad_request = _find_groq_bad_request(exc)
    if bad_request is None and isinstance(exc, InstructorRetryException) and exc.args:
        inner = exc.args[0]
        if isinstance(inner, BaseException):
            bad_request = _find_groq_bad_request(inner)

    if bad_request is None:
        return None

    details = _groq_tool_use_error_details(bad_request)
    if details.get("code") != "tool_use_failed":
        return None

    failed_generation = details.get("failed_generation", "")
    if not isinstance(failed_generation, str):
        return None

    parsed = _parse_groq_failed_generation(failed_generation)
    if parsed is not None:
        recovery_warning = "Recovered extraction from Groq malformed tool output."
        if recovery_warning in parsed.warnings:
            return parsed
        return parsed.model_copy(
            update={"warnings": [*parsed.warnings, recovery_warning]},
        )

    if _is_groq_model_refusal(failed_generation):
        return _VlmExtractionPayload(
            instruments=[],
            warnings=[f"Model refused extraction: {failed_generation.strip()}"],
        )

    return _VlmExtractionPayload(
        instruments=[],
        warnings=["Groq tool call failed; could not parse model output."],
    )


def _to_extracted_instruments(
    instruments: list[_VlmInstrumentPayload],
) -> list[ExtractedInstrument]:
    """Map Gemini-safe payload rows into schema ExtractedInstrument objects."""
    extracted: list[ExtractedInstrument] = []
    for instrument in instruments:
        extracted.append(
            ExtractedInstrument(
                tag=instrument.tag,
                instrument_type=instrument.instrument_type,
                properties=_build_instrument_properties(instrument),
                confidence=instrument.confidence,
            )
        )
    return extracted


def extract_from_image(
    image_path: Path | str,
    *,
    model_name: str | None = None,
) -> ExtractionResult:
    """Run VLM extraction on a P&ID image and return structured instruments."""
    path = Path(image_path)
    resolved_model = model_name or settings.vlm_model_name
    provider = settings.llm_provider.lower()

    if provider == "gemini":
        payload = _extract_gemini(path, model_name=resolved_model)
    elif provider == "groq":
        payload = _extract_groq(path, model_name=resolved_model)
    elif provider == "local":
        payload = _extract_ollama(path, model_name=resolved_model)
    else:
        msg = f"LLM provider {settings.llm_provider!r} is not implemented"
        raise NotImplementedError(msg)

    return ExtractionResult(
        source_image=str(path),
        instruments=_to_extracted_instruments(payload.instruments),
        model_name=resolved_model,
        warnings=payload.warnings,
    )


def text_complete(
    prompt: str,
    *,
    model_name: str | None = None,
    temperature: float = 0.0,
) -> str:
    """Complete a text prompt via the configured LLM provider."""
    resolved_model = model_name or settings.text_model_name
    provider = settings.llm_provider.lower()

    if provider == "gemini":
        return _text_complete_gemini(
            prompt,
            model_name=resolved_model,
            temperature=temperature,
        )
    if provider == "groq":
        return _text_complete_groq(
            prompt,
            model_name=resolved_model,
            temperature=temperature,
        )
    if provider == "local":
        return _text_complete_ollama(
            prompt,
            model_name=resolved_model,
            temperature=temperature,
        )

    msg = f"LLM provider {settings.llm_provider!r} is not implemented"
    raise NotImplementedError(msg)


def _extract_gemini(path: Path, *, model_name: str) -> _VlmExtractionPayload:
    """Gemini vision extraction via instructor structured output."""
    if not settings.gemini_api_key:
        msg = "GEMINI_API_KEY is required for Gemini extraction"
        raise ValueError(msg)

    client = _gemini_instructor_client()
    prompt = build_extraction_prompt(source_image=str(path), model_name=model_name)
    started = time.perf_counter()

    logger.info(
        "VLM extraction start model=%s image=%s prompt_version=%s",
        model_name,
        path,
        settings.extraction_prompt_version,
    )

    messages: Any = [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                prompt,
                Image.from_path(path),
            ],
        },
    ]

    def _call() -> _VlmExtractionPayload:
        response = client.create(
            model=model_name,
            messages=messages,
            response_model=_VlmExtractionPayload,
        )
        return response

    payload = _with_retry(_call)
    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "VLM extraction done model=%s instruments=%d latency_ms=%.1f",
        model_name,
        len(payload.instruments),
        elapsed_ms,
    )
    return payload


def _extract_groq(path: Path, *, model_name: str) -> _VlmExtractionPayload:
    """Groq vision extraction via instructor structured output."""
    if not settings.groq_api_key or settings.groq_api_key.startswith("your-"):
        msg = "GROQ_API_KEY is required for Groq extraction"
        raise ValueError(msg)

    client = _groq_instructor_client()
    prompt = build_extraction_prompt(source_image=str(path), model_name=model_name)
    started = time.perf_counter()

    logger.info(
        "VLM extraction start model=%s image=%s prompt_version=%s",
        model_name,
        path,
        settings.extraction_prompt_version,
    )

    messages: Any = [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                prompt,
                Image.from_path(path),
            ],
        },
    ]

    def _call() -> _VlmExtractionPayload:
        try:
            response = client.create(
                model=model_name,
                messages=messages,
                response_model=_VlmExtractionPayload,
                temperature=settings.extraction_temperature,
            )
            return response
        except Exception as exc:
            recovered = _recover_groq_tool_use_failure(exc)
            if recovered is not None:
                logger.warning(
                    "Recovered Groq extraction failure model=%s image=%s warnings=%s",
                    model_name,
                    path,
                    recovered.warnings,
                )
                return recovered
            raise

    try:
        payload = _with_retry(_call)
    except Exception as exc:
        recovered = _recover_groq_tool_use_failure(exc)
        if recovered is not None:
            logger.warning(
                "Recovered Groq extraction failure after retry model=%s image=%s warnings=%s",
                model_name,
                path,
                recovered.warnings,
            )
            payload = recovered
        else:
            raise
    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "VLM extraction done model=%s instruments=%d latency_ms=%.1f",
        model_name,
        len(payload.instruments),
        elapsed_ms,
    )
    return payload


def _parse_ollama_extraction_content(content: str) -> _VlmExtractionPayload:
    """Parse Ollama JSON chat content into a VLM payload."""
    text = content.strip()
    if not text:
        msg = "Ollama extraction returned empty response"
        raise RuntimeError(msg)

    try:
        return _VlmExtractionPayload.model_validate_json(text)
    except ValidationError:
        try:
            data: object = json.loads(text)
        except json.JSONDecodeError as exc:
            msg = "Ollama extraction returned non-JSON content"
            raise RuntimeError(msg) from exc

        if isinstance(data, dict):
            return _VlmExtractionPayload.model_validate(data)
        msg = "Ollama extraction JSON did not match expected schema"
        raise RuntimeError(msg)


def _extract_ollama(path: Path, *, model_name: str) -> _VlmExtractionPayload:
    """Ollama vision extraction via JSON schema structured output."""
    client = _ollama_client(timeout_seconds=settings.vlm_timeout_seconds)
    prompt = build_extraction_prompt(source_image=str(path), model_name=model_name)
    started = time.perf_counter()

    logger.info(
        "VLM extraction start model=%s image=%s prompt_version=%s provider=local",
        model_name,
        path,
        settings.extraction_prompt_version,
    )

    messages: Any = [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": prompt,
            "images": [str(path)],
        },
    ]

    def _call() -> _VlmExtractionPayload:
        response = client.chat(
            model=model_name,
            messages=messages,
            format=_VlmExtractionPayload.model_json_schema(),
            options=_ollama_options(temperature=settings.extraction_temperature),
            stream=False,
        )
        content = response.message.content
        if content is None:
            msg = "Ollama extraction returned empty message content"
            raise RuntimeError(msg)
        return _parse_ollama_extraction_content(content)

    payload = _with_retry(_call)
    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "VLM extraction done model=%s instruments=%d latency_ms=%.1f provider=local",
        model_name,
        len(payload.instruments),
        elapsed_ms,
    )
    return payload


def _text_complete_ollama(
    prompt: str,
    *,
    model_name: str,
    temperature: float,
) -> str:
    """Ollama text completion for fuzzy matching and other text tasks."""
    client = _ollama_client(timeout_seconds=settings.text_timeout_seconds)
    started = time.perf_counter()
    logger.info("Text completion start model=%s provider=local", model_name)

    def _call() -> str:
        response = client.chat(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            options=_ollama_options(temperature=temperature),
            stream=False,
        )
        text = response.message.content
        if text is None:
            msg = "Ollama text completion returned empty response"
            raise RuntimeError(msg)
        return text

    result = _with_retry(_call)
    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "Text completion done model=%s latency_ms=%.1f provider=local",
        model_name,
        elapsed_ms,
    )
    return result


def _text_complete_groq(
    prompt: str,
    *,
    model_name: str,
    temperature: float,
) -> str:
    """Groq text completion for fuzzy matching and other text tasks."""
    if not settings.groq_api_key or settings.groq_api_key.startswith("your-"):
        msg = "GROQ_API_KEY is required for Groq text completion"
        raise ValueError(msg)

    raw_client = _groq_raw_client(timeout_seconds=settings.text_timeout_seconds)
    started = time.perf_counter()
    logger.info("Text completion start model=%s", model_name)

    def _call() -> str:
        response = raw_client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        text = response.choices[0].message.content
        if text is None:
            msg = "Groq text completion returned empty response"
            raise RuntimeError(msg)
        return text

    result = _with_retry(_call)
    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info("Text completion done model=%s latency_ms=%.1f", model_name, elapsed_ms)
    return result


def _text_complete_gemini(
    prompt: str,
    *,
    model_name: str,
    temperature: float,
) -> str:
    """Gemini text completion for fuzzy matching and other text tasks."""
    if not settings.gemini_api_key:
        msg = "GEMINI_API_KEY is required for Gemini text completion"
        raise ValueError(msg)

    raw_client = _gemini_raw_client()
    started = time.perf_counter()
    logger.info("Text completion start model=%s", model_name)

    def _call() -> str:
        response = raw_client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=genai_types.GenerateContentConfig(temperature=temperature),
        )
        text = response.text
        if text is None:
            msg = "Gemini text completion returned empty response"
            raise RuntimeError(msg)
        return text

    result = _with_retry(_call)
    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info("Text completion done model=%s latency_ms=%.1f", model_name, elapsed_ms)
    return result


def _ollama_client(*, timeout_seconds: float) -> OllamaClient:
    """Build a configured Ollama client."""
    return OllamaClient(
        host=settings.ollama_base_url,
        timeout=timeout_seconds,
    )


def _ollama_options(*, temperature: float) -> OllamaOptions:
    """Return deterministic Ollama runtime options."""
    return OllamaOptions(temperature=temperature, seed=0)


def _groq_raw_client(*, timeout_seconds: float) -> Groq:
    """Build a configured Groq client."""
    return Groq(
        api_key=settings.groq_api_key,
        timeout=timeout_seconds,
    )


def _groq_instructor_client() -> instructor.Instructor:
    """Patch the Groq client with instructor for structured outputs."""
    raw = _groq_raw_client(timeout_seconds=settings.vlm_timeout_seconds)
    patched = from_groq(
        raw,
        mode=instructor.Mode.TOOLS,
    )
    return cast(instructor.Instructor, patched)


def _gemini_raw_client() -> genai.Client:
    """Build a configured Google GenAI client."""
    timeout_ms = int(settings.vlm_timeout_seconds * 1000)
    return genai.Client(
        api_key=settings.gemini_api_key,
        http_options=genai_types.HttpOptions(timeout=timeout_ms),
    )


def _gemini_instructor_client() -> instructor.Instructor:
    """Patch the GenAI client with instructor for structured outputs."""
    raw = _gemini_raw_client()
    _patch_genai_generate_content(
        raw,
        temperature=settings.extraction_temperature,
    )
    patched = instructor.from_genai(
        raw,
        mode=instructor.Mode.GENAI_STRUCTURED_OUTPUTS,
    )
    return cast(instructor.Instructor, patched)


def _patch_genai_generate_content(
    client: genai.Client,
    *,
    temperature: float,
) -> None:
    """Ensure GenAI calls use `config`, not legacy `generation_config`."""
    original = client.models.generate_content

    def generate_content(*args: Any, **kwargs: Any) -> Any:
        kwargs.pop("generation_config", None)
        config = kwargs.get("config")
        if config is not None:
            kwargs["config"] = config.model_copy(update={"temperature": temperature})
        return original(*args, **kwargs)

    client.models.generate_content = generate_content  # type: ignore[method-assign]


def _with_retry(operation: Callable[[], T]) -> T:
    """Retry provider calls with exponential backoff on rate limits."""
    last_error: Exception | None = None
    for attempt in range(settings.max_retries + 1):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            if not _is_rate_limit_error(exc) or attempt >= settings.max_retries:
                raise
            delay = 2**attempt
            logger.warning(
                "Rate limited (attempt %d/%d), retrying in %ss: %s",
                attempt + 1,
                settings.max_retries,
                delay,
                exc,
            )
            time.sleep(delay)

    assert last_error is not None
    raise last_error


def _is_rate_limit_error(exc: Exception) -> bool:
    """Return True when the provider indicates a retryable rate limit."""
    if isinstance(exc, genai_errors.ClientError):
        return exc.code == 429
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APIStatusError) and exc.status_code == 429:
        return True
    message = str(exc).lower()
    return (
        "429" in message
        or "rate limit" in message
        or "resource exhausted" in message
    )
