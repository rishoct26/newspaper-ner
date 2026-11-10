"""Recursive, projection-based layout regions for newspaper page images."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from PIL import Image, ImageDraw

app = typer.Typer(help="Split a newspaper page into layout regions using white-space cuts.")
ANALYSIS_WIDTH = 1200


def _percentile(histogram: list[int], fraction: float) -> int:
    target = sum(histogram) * fraction
    count = 0
    for value, frequency in enumerate(histogram):
        count += frequency
        if count >= target:
            return value
    return 255


def _adaptive_ink_threshold(gray: Image.Image) -> tuple[int, int]:
    """Estimate paper brightness, then set a page-relative ink cutoff."""
    background = _percentile(gray.histogram(), 0.88)
    threshold = max(95, min(225, round(background * 0.80)))
    return threshold, background


def _find_gaps(
    pixels,
    box: tuple[int, int, int, int],
    axis: str,
    ink_threshold: int,
    min_gap: int,
    min_child: int,
) -> list[tuple[int, int]]:
    left, top, right, bottom = box
    if axis == "horizontal":
        axis_start, axis_end = top, bottom
        cross_length = right - left
        # Tolerate sparse dark pixels from a small photo or side item while
        # separating broad low-ink horizontal bands.
        ink_limit = 0.20
        occupancy = [
            sum(pixels[x, y] < ink_threshold for x in range(left, right)) / cross_length
            for y in range(top, bottom)
        ]
    else:
        axis_start, axis_end = left, right
        cross_length = bottom - top
        ink_limit = 0.025
        occupancy = [
            sum(pixels[x, y] < ink_threshold for y in range(top, bottom)) / cross_length
            for x in range(left, right)
        ]

    candidates = []
    edge_margin = max(2, round((axis_end - axis_start) * 0.02))
    allowed_start = axis_start + edge_margin
    allowed_end = axis_end - edge_margin
    index = 0
    while index < len(occupancy):
        if occupancy[index] > ink_limit:
            index += 1
            continue
        run_start = index
        while index < len(occupancy) and occupancy[index] <= ink_limit:
            index += 1
        run_end = index
        absolute_start = axis_start + run_start
        absolute_end = axis_start + run_end
        if (
            run_end - run_start >= min_gap
            and absolute_start >= allowed_start
            and absolute_end <= allowed_end
        ):
            candidates.append((absolute_start, absolute_end))

    # Keep cuts that leave enough content on both sides; reject outer margins.
    cuts = []
    previous_end = axis_start
    for gap_start, gap_end in candidates:
        if gap_start - previous_end < min_child or axis_end - gap_end < min_child:
            continue
        cuts.append((gap_start, gap_end))
        previous_end = gap_end

    if cuts and axis_end - cuts[-1][1] < min_child:
        cuts.pop()
    return cuts


def _segments(
    box: tuple[int, int, int, int],
    axis: str,
    cuts: list[tuple[int, int]],
) -> list[tuple[int, int, int, int]]:
    left, top, right, bottom = box
    segments = []
    cursor = top if axis == "horizontal" else left
    for gap_start, gap_end in cuts:
        if axis == "horizontal":
            if gap_start > cursor:
                segments.append((left, cursor, right, gap_start))
        else:
            if gap_start > cursor:
                segments.append((cursor, top, gap_start, bottom))
        cursor = gap_end
    axis_end = bottom if axis == "horizontal" else right
    if cursor < axis_end:
        if axis == "horizontal":
            segments.append((left, cursor, right, bottom))
        else:
            segments.append((cursor, top, right, bottom))
    return segments


def detect_columns(
    image: Image.Image,
    *,
    analysis_width: int = ANALYSIS_WIDTH,
) -> list[tuple[int, int, int, int]]:
    """Recursively find horizontal bands, then vertical column regions.

    Returned boxes are leaf regions in original page pixels, ordered by
    recursion (horizontal bands top-to-bottom, columns left-to-right). This is
    a first heuristic; page-wide banners and photo-heavy layouts need visual
    inspection in the generated overlay.
    """
    page_width, page_height = image.size
    if page_width <= 0 or page_height <= 0:
        raise ValueError("Page image must have positive width and height.")

    scale = min(1.0, analysis_width / page_width)
    small_width = max(1, round(page_width * scale))
    small_height = max(1, round(page_height * scale))
    gray = image.convert("L").resize(
        (small_width, small_height), Image.Resampling.BILINEAR
    )
    threshold, background = _adaptive_ink_threshold(gray)
    pixels = gray.load()
    scale_x = page_width / small_width
    scale_y = page_height / small_height
    min_width = max(28, round(small_width * 0.045))
    min_height = max(26, round(small_height * 0.035))
    h_gap = max(10, round(small_height * 0.01))
    v_gap = max(2, round(small_width * 0.002))
    leaves: list[tuple[int, int, int, int]] = []

    def recurse(box: tuple[int, int, int, int], depth: int = 0) -> None:
        left, top, right, bottom = box
        if depth >= 10 or right - left < min_width * 2 or bottom - top < min_height * 2:
            leaves.append(box)
            return

        # First isolate broad horizontal bands, such as mastheads or banners.
        horizontal = _find_gaps(
            pixels, box, "horizontal", threshold, h_gap, min_height
        )
        if horizontal:
            for part in _segments(box, "horizontal", horizontal):
                recurse(part, depth + 1)
            return

        vertical = _find_gaps(
            pixels, box, "vertical", threshold, v_gap, min_width
        )
        if vertical:
            for part in _segments(box, "vertical", vertical):
                recurse(part, depth + 1)
            return
        leaves.append(box)

    recurse((0, 0, small_width, small_height))
    return [
        (
            max(0, round(left * scale_x)),
            max(0, round(top * scale_y)),
            min(page_width, round(right * scale_x)),
            min(page_height, round(bottom * scale_y)),
        )
        for left, top, right, bottom in leaves
        if right > left and bottom > top
    ] or [(0, 0, page_width, page_height)]


def split_page(image_path: Path, output_dir: Path) -> dict:
    image_path = image_path.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as image:
        page_width, page_height = image.size
        small_width = min(ANALYSIS_WIDTH, page_width)
        small_height = max(1, round(page_height * small_width / page_width))
        analysis_image = image.convert("L").resize(
            (small_width, small_height), Image.Resampling.BILINEAR
        )
        threshold, background = _adaptive_ink_threshold(analysis_image)
        boxes = detect_columns(image)
        regions = []
        overlay = image.convert("RGB")
        draw = ImageDraw.Draw(overlay)
        line_width = max(2, page_width // 2500)
        for index, (left, top, right, bottom) in enumerate(boxes, start=1):
            crop_path = output_dir / f"{image_path.stem}_region_{index:02}.png"
            image.crop((left, top, right, bottom)).save(crop_path)
            draw.rectangle(
                (left, top, right - 1, bottom - 1),
                outline=(255, 40, 40),
                width=line_width,
            )
            draw.text(
                (left + line_width + 2, top + line_width + 2),
                f"R{index}",
                fill=(255, 255, 0),
                stroke_width=2,
                stroke_fill=(0, 0, 0),
            )
            regions.append({
                "region_index": index,
                "bbox_xyxy": [left, top, right, bottom],
                "crop_image": str(crop_path.resolve()),
            })
        overlay_path = output_dir / f"{image_path.stem}_layout_overlay.png"
        overlay.save(overlay_path)

    return {
        "stage": "layout",
        "method": "recursive horizontal bands then vertical gutters",
        "threshold_method": "80% of estimated 88th-percentile paper brightness",
        "estimated_background_gray": background,
        "ink_threshold_gray": threshold,
        "source_image": str(image_path),
        "page_width": page_width,
        "page_height": page_height,
        "reading_order": "recursive top_to_bottom then left_to_right",
        "debug_overlay": str(overlay_path.resolve()),
        "regions": regions,
    }


@app.command()
def split(
    image: Path = typer.Argument(..., exists=True, dir_okay=False),
    output_dir: Path = typer.Option(Path("outputs/layout"), "--output-dir"),
    output: Path = typer.Option(Path("outputs/layout.json"), "--output", "-o"),
):
    """Detect recursive layout regions; save crop images and a debug overlay."""
    try:
        result = split_page(image, output_dir)
    except (OSError, ValueError) as error:
        raise typer.BadParameter(str(error)) from error
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(
        f"Detected {len(result['regions'])} layout region(s); saved crops and overlay to {output_dir}"
    )


if __name__ == "__main__":
    app()
