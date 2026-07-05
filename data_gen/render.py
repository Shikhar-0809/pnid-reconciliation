"""SVG P&ID rendering (svgwrite) and PNG export (cairosvg)."""

from __future__ import annotations

from pathlib import Path

import svgwrite  # type: ignore[import-untyped]
from PIL import Image, ImageDraw, ImageFont

from data_gen.models import TruthInstrument
from pnid_recon.schemas.extraction import BoundingBox

CANVAS_WIDTH = 1400
CANVAS_HEIGHT = 900
BUBBLE_RADIUS_T0 = 58
TAG_FONT_SIZE_T0 = 26
SUBTITLE_FONT_SIZE_T0 = 14
BUBBLE_RADIUS_T1 = 42
TAG_FONT_SIZE_T1 = 18
SUBTITLE_FONT_SIZE_T1 = 12
EQUIPMENT_WIDTH = 320
EQUIPMENT_HEIGHT = 120
EQUIPMENT_WIDTH_T1 = 240
EQUIPMENT_HEIGHT_T1 = 100


def render_pid(
    instruments: list[TruthInstrument],
    svg_path: Path,
    png_path: Path,
    *,
    tier: str,
) -> list[TruthInstrument]:
    """Render a legible P&ID SVG and PNG; return instruments with normalized bboxes."""
    if tier == "T0":
        return _render_t0(instruments, svg_path, png_path)
    if tier == "T1":
        return _render_t1(instruments, svg_path, png_path)
    msg = f"Unsupported tier {tier!r}; supported tiers: T0, T1"
    raise ValueError(msg)


def _render_t0(
    instruments: list[TruthInstrument],
    svg_path: Path,
    png_path: Path,
) -> list[TruthInstrument]:
    """T0: large bubbles, generous spacing, single equipment shape."""
    positions = _layout_bubble_centers(len(instruments))
    dwg = svgwrite.Drawing(
        str(svg_path),
        size=(CANVAS_WIDTH, CANVAS_HEIGHT),
        profile="full",
    )
    dwg.add(
        dwg.rect(
            insert=(0, 0),
            size=(CANVAS_WIDTH, CANVAS_HEIGHT),
            fill="white",
        )
    )
    _draw_title_block(dwg, tier="T0")
    _draw_equipment(dwg)

    updated: list[TruthInstrument] = []
    for instrument, (cx, cy) in zip(instruments, positions, strict=True):
        subtitle = None
        if instrument.show_pressure_on_drawing:
            subtitle = instrument.design_pressure
        _draw_instrument_bubble(
            dwg,
            cx,
            cy,
            instrument.tag,
            subtitle,
            radius=BUBBLE_RADIUS_T0,
            tag_font_size=TAG_FONT_SIZE_T0,
            subtitle_font_size=SUBTITLE_FONT_SIZE_T0,
        )
        bbox = _bubble_bbox(
            cx,
            cy,
            BUBBLE_RADIUS_T0,
            subtitle is not None,
            subtitle_offset=30.0,
        )
        updated.append(instrument.model_copy(update={"bbox": bbox}))

    dwg.save()
    if not _try_cairosvg(svg_path, png_path):
        _write_png_pillow_t0(instruments, positions, png_path)
    return updated


def _render_t1(
    instruments: list[TruthInstrument],
    svg_path: Path,
    png_path: Path,
) -> list[TruthInstrument]:
    """T1: normal spacing, two equipment shapes, up to two instrument rows."""
    positions = _layout_bubble_centers_t1(len(instruments))
    dwg = svgwrite.Drawing(
        str(svg_path),
        size=(CANVAS_WIDTH, CANVAS_HEIGHT),
        profile="full",
    )
    dwg.add(
        dwg.rect(
            insert=(0, 0),
            size=(CANVAS_WIDTH, CANVAS_HEIGHT),
            fill="white",
        )
    )
    _draw_title_block(dwg, tier="T1")
    _draw_equipment_t1(dwg)

    updated: list[TruthInstrument] = []
    for instrument, (cx, cy) in zip(instruments, positions, strict=True):
        subtitle = None
        if instrument.show_pressure_on_drawing:
            subtitle = instrument.design_pressure
        _draw_instrument_bubble(
            dwg,
            cx,
            cy,
            instrument.tag,
            subtitle,
            radius=BUBBLE_RADIUS_T1,
            tag_font_size=TAG_FONT_SIZE_T1,
            subtitle_font_size=SUBTITLE_FONT_SIZE_T1,
            line_y=500,
        )
        bbox = _bubble_bbox(
            cx,
            cy,
            BUBBLE_RADIUS_T1,
            subtitle is not None,
            subtitle_offset=22.0,
        )
        updated.append(instrument.model_copy(update={"bbox": bbox}))

    dwg.save()
    if not _try_cairosvg(svg_path, png_path):
        _write_png_pillow_t1(instruments, positions, png_path)
    return updated


def _try_cairosvg(svg_path: Path, png_path: Path) -> bool:
    """Return True when cairosvg successfully rasterizes the SVG."""
    png_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import cairosvg  # type: ignore[import-untyped]
    except OSError:
        return False

    try:
        cairosvg.svg2png(
            url=str(svg_path),
            write_to=str(png_path),
            output_width=CANVAS_WIDTH,
            output_height=CANVAS_HEIGHT,
        )
    except OSError:
        return False
    return True


def _write_png_pillow_t0(
    instruments: list[TruthInstrument],
    positions: list[tuple[float, float]],
    png_path: Path,
) -> None:
    """Draw the T0 layout with Pillow when cairosvg cannot load Cairo."""
    png_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), "white")
    draw = ImageDraw.Draw(image)
    title_font = _load_font(22)
    label_font = _load_font(16)
    tag_font = _load_font(TAG_FONT_SIZE_T0)
    subtitle_font = _load_font(SUBTITLE_FONT_SIZE_T0)
    equip_font = _load_font(28)
    equip_sub_font = _load_font(18)

    draw.rectangle((40, 40, 460, 130), outline="black", width=2)
    draw.text((60, 55), "P&ID — Reactor Area (T0)", fill="black", font=title_font)
    draw.text((60, 85), "DWG-001", fill="black", font=label_font)

    cx = CANVAS_WIDTH / 2
    cy = 280.0
    ex = cx - (EQUIPMENT_WIDTH / 2)
    ey = cy - (EQUIPMENT_HEIGHT / 2)
    draw.rectangle(
        (ex, ey, ex + EQUIPMENT_WIDTH, ey + EQUIPMENT_HEIGHT),
        fill="#f5f5f5",
        outline="black",
        width=3,
    )
    draw.text((cx - 45, cy - 18), "V-101", fill="black", font=equip_font)
    draw.text((cx - 35, cy + 14), "Reactor", fill="black", font=equip_sub_font)
    draw.line((cx, cy + (EQUIPMENT_HEIGHT / 2), cx, 520), fill="black", width=4)

    for instrument, (bubble_cx, bubble_cy) in zip(instruments, positions, strict=True):
        subtitle = (
            instrument.design_pressure if instrument.show_pressure_on_drawing else None
        )
        left = bubble_cx - BUBBLE_RADIUS_T0
        top = bubble_cy - BUBBLE_RADIUS_T0
        right = bubble_cx + BUBBLE_RADIUS_T0
        bottom = bubble_cy + BUBBLE_RADIUS_T0
        draw.ellipse((left, top, right, bottom), outline="black", width=3, fill="white")
        tag_bbox = draw.textbbox((0, 0), instrument.tag, font=tag_font)
        tag_w = tag_bbox[2] - tag_bbox[0]
        draw.text(
            (bubble_cx - (tag_w / 2), bubble_cy - 12),
            instrument.tag,
            fill="black",
            font=tag_font,
        )
        if subtitle is not None:
            sub_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
            sub_w = sub_bbox[2] - sub_bbox[0]
            draw.text(
                (bubble_cx - (sub_w / 2), bubble_cy + BUBBLE_RADIUS_T0 + 8),
                subtitle,
                fill="black",
                font=subtitle_font,
            )
        draw.line(
            (bubble_cx, bubble_cy - BUBBLE_RADIUS_T0, bubble_cx, 520),
            fill="black",
            width=4,
        )

    image.save(png_path, format="PNG")


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a readable font, preferring Arial on Windows."""
    for path in (
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def svg_to_png(svg_path: Path, png_path: Path) -> None:
    """Convert an SVG file to PNG via cairosvg."""
    if not _try_cairosvg(svg_path, png_path):
        msg = (
            "Cairo library not available for cairosvg. "
            "Install GTK3 Runtime or regenerate via render_pid()."
        )
        raise OSError(msg)


def _layout_bubble_centers(count: int) -> list[tuple[float, float]]:
    """Place instrument bubbles in a single horizontal row with generous T0 spacing."""
    margin_x = 120.0
    y = 620.0
    usable = CANVAS_WIDTH - (2 * margin_x)
    if count == 1:
        return [(CANVAS_WIDTH / 2, y)]
    step = usable / (count - 1)
    return [(margin_x + (i * step), y) for i in range(count)]


def _layout_bubble_centers_t1(count: int) -> list[tuple[float, float]]:
    """Place instrument bubbles in one or two rows with normal T1 spacing."""
    margin_x = 80.0
    row1_y = 560.0
    row2_y = 720.0
    usable = CANVAS_WIDTH - (2 * margin_x)

    if count <= 6:
        if count == 1:
            return [(CANVAS_WIDTH / 2, row1_y)]
        step = usable / (count - 1)
        return [(margin_x + (i * step), row1_y) for i in range(count)]

    row1_count = (count + 1) // 2
    row2_count = count - row1_count
    positions: list[tuple[float, float]] = []
    if row1_count == 1:
        positions.append((CANVAS_WIDTH / 2, row1_y))
    else:
        step = usable / (row1_count - 1)
        positions.extend(
            (margin_x + (i * step), row1_y) for i in range(row1_count)
        )
    if row2_count == 1:
        positions.append((CANVAS_WIDTH / 2, row2_y))
    else:
        step = usable / (row2_count - 1)
        positions.extend(
            (margin_x + (i * step), row2_y) for i in range(row2_count)
        )
    return positions


def _draw_title_block(dwg: svgwrite.Drawing, *, tier: str) -> None:
    title = f"P&ID — Reactor Area ({tier})"
    dwg.add(
        dwg.rect(
            insert=(40, 40),
            size=(420, 90),
            fill="white",
            stroke="black",
            stroke_width=2,
        )
    )
    dwg.add(
        dwg.text(
            title,
            insert=(60, 75),
            fill="black",
            font_size=22,
            font_family="Arial",
            font_weight="bold",
        )
    )
    dwg.add(
        dwg.text(
            "DWG-001",
            insert=(60, 105),
            fill="black",
            font_size=16,
            font_family="Arial",
        )
    )


def _draw_equipment(dwg: svgwrite.Drawing) -> None:
    cx = CANVAS_WIDTH / 2
    cy = 280.0
    _draw_equipment_rect(
        dwg,
        cx,
        cy,
        EQUIPMENT_WIDTH,
        EQUIPMENT_HEIGHT,
        "V-101",
        "Reactor",
    )
    _draw_process_line(dwg, cx, cy + (EQUIPMENT_HEIGHT / 2), cx, 520)


def _draw_equipment_t1(dwg: svgwrite.Drawing) -> None:
    """Draw reactor and separator equipment shapes for T1."""
    reactor_cx = CANVAS_WIDTH / 2
    reactor_cy = 260.0
    _draw_equipment_rect(
        dwg,
        reactor_cx,
        reactor_cy,
        EQUIPMENT_WIDTH_T1,
        EQUIPMENT_HEIGHT_T1,
        "V-101",
        "Reactor",
    )
    separator_cx = 280.0
    separator_cy = 380.0
    _draw_equipment_rect(
        dwg,
        separator_cx,
        separator_cy,
        EQUIPMENT_WIDTH_T1,
        EQUIPMENT_HEIGHT_T1,
        "T-102",
        "Separator",
    )
    _draw_process_line(
        dwg,
        reactor_cx,
        reactor_cy + (EQUIPMENT_HEIGHT_T1 / 2),
        reactor_cx,
        500,
    )
    _draw_process_line(
        dwg,
        separator_cx,
        separator_cy + (EQUIPMENT_HEIGHT_T1 / 2),
        separator_cx,
        500,
    )


def _draw_equipment_rect(
    dwg: svgwrite.Drawing,
    cx: float,
    cy: float,
    width: float,
    height: float,
    label: str,
    subtitle: str,
) -> None:
    x = cx - (width / 2)
    y = cy - (height / 2)
    dwg.add(
        dwg.rect(
            insert=(x, y),
            size=(width, height),
            fill="#f5f5f5",
            stroke="black",
            stroke_width=3,
        )
    )
    dwg.add(
        dwg.text(
            label,
            insert=(cx, cy + 8),
            fill="black",
            font_size=24,
            font_family="Arial",
            font_weight="bold",
            text_anchor="middle",
        )
    )
    dwg.add(
        dwg.text(
            subtitle,
            insert=(cx, cy + 32),
            fill="black",
            font_size=16,
            font_family="Arial",
            text_anchor="middle",
        )
    )


def _draw_process_line(
    dwg: svgwrite.Drawing,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> None:
    dwg.add(
        dwg.line(
            start=(x1, y1),
            end=(x2, y2),
            stroke="black",
            stroke_width=4,
        )
    )


def _draw_instrument_bubble(
    dwg: svgwrite.Drawing,
    cx: float,
    cy: float,
    tag: str,
    subtitle: str | None,
    *,
    radius: float,
    tag_font_size: int,
    subtitle_font_size: int,
    line_y: float = 520,
) -> None:
    dwg.add(
        dwg.circle(
            center=(cx, cy),
            r=radius,
            fill="white",
            stroke="black",
            stroke_width=3,
        )
    )
    dwg.add(
        dwg.text(
            tag,
            insert=(cx, cy + 8),
            fill="black",
            font_size=tag_font_size,
            font_family="Arial",
            font_weight="bold",
            text_anchor="middle",
        )
    )
    if subtitle is not None:
        dwg.add(
            dwg.text(
                subtitle,
                insert=(cx, cy + radius + 18),
                fill="black",
                font_size=subtitle_font_size,
                font_family="Arial",
                text_anchor="middle",
            )
        )
    _draw_process_line(dwg, cx, cy - radius, cx, line_y)


def _bubble_bbox(
    cx: float,
    cy: float,
    radius: float,
    has_subtitle: bool,
    *,
    subtitle_offset: float,
) -> BoundingBox:
    left = cx - radius
    top = cy - radius
    width = float(2 * radius)
    height = float(2 * radius)
    if has_subtitle:
        height += subtitle_offset
    return BoundingBox(
        x=left / CANVAS_WIDTH,
        y=top / CANVAS_HEIGHT,
        width=width / CANVAS_WIDTH,
        height=height / CANVAS_HEIGHT,
    )


def _write_png_pillow_t1(
    instruments: list[TruthInstrument],
    positions: list[tuple[float, float]],
    png_path: Path,
) -> None:
    """Draw the T1 layout with Pillow when cairosvg cannot load Cairo."""
    png_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), "white")
    draw = ImageDraw.Draw(image)
    title_font = _load_font(22)
    label_font = _load_font(16)
    tag_font = _load_font(TAG_FONT_SIZE_T1)
    subtitle_font = _load_font(SUBTITLE_FONT_SIZE_T1)
    equip_font = _load_font(24)
    equip_sub_font = _load_font(16)

    draw.rectangle((40, 40, 460, 130), outline="black", width=2)
    draw.text((60, 55), "P&ID — Reactor Area (T1)", fill="black", font=title_font)
    draw.text((60, 85), "DWG-001", fill="black", font=label_font)

    for cx, cy, label, subtitle in (
        (CANVAS_WIDTH / 2, 260.0, "V-101", "Reactor"),
        (280.0, 380.0, "T-102", "Separator"),
    ):
        ex = cx - (EQUIPMENT_WIDTH_T1 / 2)
        ey = cy - (EQUIPMENT_HEIGHT_T1 / 2)
        draw.rectangle(
            (ex, ey, ex + EQUIPMENT_WIDTH_T1, ey + EQUIPMENT_HEIGHT_T1),
            fill="#f5f5f5",
            outline="black",
            width=3,
        )
        draw.text((cx - 35, cy - 10), label, fill="black", font=equip_font)
        draw.text((cx - 40, cy + 16), subtitle, fill="black", font=equip_sub_font)
        draw.line((cx, cy + (EQUIPMENT_HEIGHT_T1 / 2), cx, 500), fill="black", width=4)

    for instrument, (bubble_cx, bubble_cy) in zip(instruments, positions, strict=True):
        subtitle = (
            instrument.design_pressure if instrument.show_pressure_on_drawing else None
        )
        left = bubble_cx - BUBBLE_RADIUS_T1
        top = bubble_cy - BUBBLE_RADIUS_T1
        right = bubble_cx + BUBBLE_RADIUS_T1
        bottom = bubble_cy + BUBBLE_RADIUS_T1
        draw.ellipse((left, top, right, bottom), outline="black", width=3, fill="white")
        tag_bbox = draw.textbbox((0, 0), instrument.tag, font=tag_font)
        tag_w = tag_bbox[2] - tag_bbox[0]
        draw.text(
            (bubble_cx - (tag_w / 2), bubble_cy - 10),
            instrument.tag,
            fill="black",
            font=tag_font,
        )
        if subtitle is not None:
            sub_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
            sub_w = sub_bbox[2] - sub_bbox[0]
            draw.text(
                (bubble_cx - (sub_w / 2), bubble_cy + BUBBLE_RADIUS_T1 + 6),
                subtitle,
                fill="black",
                font=subtitle_font,
            )
        draw.line(
            (bubble_cx, bubble_cy - BUBBLE_RADIUS_T1, bubble_cx, 500),
            fill="black",
            width=4,
        )

    image.save(png_path, format="PNG")
