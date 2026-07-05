"""P&ID image path helpers and preprocessing for VLM ingest."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

MAX_IMAGE_DIMENSION = 2048


def resolve_image_path(path: Path | str) -> Path:
    """Return a validated path to a P&ID image file."""
    image_path = Path(path)
    if not image_path.is_file():
        msg = f"P&ID image not found: {image_path}"
        raise FileNotFoundError(msg)
    return image_path


def preprocess_image(path: str) -> bytes:
    """Load, normalize, resize, and encode a P&ID image as PNG bytes for the VLM."""
    image_path = Path(path)
    if not image_path.is_file():
        msg = f"P&ID image not found: {image_path}"
        raise FileNotFoundError(msg)

    with Image.open(image_path) as img:
        rgb = img.convert("RGB")
        width, height = rgb.size
        longest = max(width, height)
        if longest > MAX_IMAGE_DIMENSION:
            scale = MAX_IMAGE_DIMENSION / longest
            new_size = (int(width * scale), int(height * scale))
            rgb = rgb.resize(new_size, Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        rgb.save(buffer, format="PNG")
        return buffer.getvalue()
