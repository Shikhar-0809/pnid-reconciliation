#!/usr/bin/env python3
"""Batch extraction: POST /extract for each image in a directory."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def _post_extract(*, base_url: str, image_path: Path) -> dict[str, object]:
    """Call POST /extract for one image and return the JSON response."""
    body = json.dumps({"image_path": str(image_path.resolve())}).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/extract",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.loads(response.read().decode("utf-8"))


def _iter_images(directory: Path) -> list[Path]:
    """Return image files in a directory, sorted by name."""
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def main(argv: list[str] | None = None) -> int:
    """Extract instruments from every image in a directory via the API."""
    parser = argparse.ArgumentParser(
        description="Run POST /extract on each image in a directory.",
    )
    parser.add_argument(
        "images_dir",
        type=Path,
        help="Directory containing P&ID images (PNG, JPEG, etc.)",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Base URL of the running pnid-recon API (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("extract_results"),
        help="Directory for per-image ExtractionResult JSON files",
    )
    parser.add_argument(
        "--fail-log",
        type=Path,
        nargs="?",
        const=Path("fail_logs"),
        default=None,
        help=(
            "Write full HTTP error response bodies to this directory "
            "(default: fail_logs/)"
        ),
    )
    args = parser.parse_args(argv)

    if not args.images_dir.is_dir():
        print(f"Images directory not found: {args.images_dir}", file=sys.stderr)
        return 1

    images = _iter_images(args.images_dir)
    if not images:
        print(f"No images found in {args.images_dir}", file=sys.stderr)
        return 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.fail_log is not None:
        args.fail_log.mkdir(parents=True, exist_ok=True)
    failures = 0

    for image_path in images:
        output_path = args.output_dir / f"{image_path.stem}.json"
        try:
            payload = _post_extract(base_url=args.base_url, image_path=image_path)
            output_path.write_text(
                json.dumps(payload, indent=2) + "\n",
                encoding="utf-8",
            )
            instrument_count = len(payload.get("instruments", []))
            print(f"OK {image_path.name} -> {output_path} ({instrument_count} instruments)")
        except urllib.error.HTTPError as exc:
            failures += 1
            detail = exc.read().decode("utf-8", errors="replace")
            print(f"FAIL {image_path.name}: HTTP {exc.code} {detail}", file=sys.stderr)
            if args.fail_log is not None:
                fail_path = args.fail_log / f"{image_path.name}.txt"
                fail_path.write_text(
                    f"HTTP {exc.code}\n{detail}\n",
                    encoding="utf-8",
                )
        except urllib.error.URLError as exc:
            failures += 1
            message = f"URL error: {exc.reason}\n"
            print(f"FAIL {image_path.name}: {exc.reason}", file=sys.stderr)
            if args.fail_log is not None:
                fail_path = args.fail_log / f"{image_path.name}.txt"
                fail_path.write_text(message, encoding="utf-8")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
