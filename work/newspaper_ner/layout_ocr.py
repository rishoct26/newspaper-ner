"""OCR text boxes predicted by the optional PaddleOCR layout stage."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import typer
from PIL import Image

from .ocr import recognize_page

app = typer.Typer(help="OCR text regions from a layout-detection JSON file.")
TEXT_LABELS = {"text", "paragraph_title", "doc_title", "header", "aside_text"}


def _coordinates(box: dict) -> tuple[int, int, int, int]:
    value = box.get("coordinate")
    if isinstance(value, str):
        values = [float(part) for part in value.split()]
    else:
        values = [float(part) for part in value]
    if len(values) != 4:
        raise ValueError("Each layout box must contain four coordinates.")
    left, top, right, bottom = values
    return round(left), round(top), round(right), round(bottom)


def ocr_layout_regions(
    page_path: Path,
    layout_path: Path,
    language: str,
    psm: int,
    output_path: Path,
) -> dict:
    page_path = page_path.resolve()
    layout_path = layout_path.resolve()
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    layout_data = json.loads(layout_path.read_text(encoding="utf-8"))
    with Image.open(page_path) as source:
        page = source.convert("RGB")
        page_width, page_height = page.size
        candidates = []
        for item in layout_data.get("boxes", []):
            if item.get("label") not in TEXT_LABELS:
                continue
            left, top, right, bottom = _coordinates(item)
            left = max(0, min(page_width, left))
            right = max(0, min(page_width, right))
            top = max(0, min(page_height, top))
            bottom = max(0, min(page_height, bottom))
            if right > left and bottom > top:
                candidates.append({
                    "label": item["label"],
                    "score": float(item.get("score", 0.0)),
                    "bbox_xyxy": [left, top, right, bottom],
                })

        # Use deterministic top-to-bottom, left-to-right ordering. Each box is
        # assigned a unique Tesseract block range below, so line IDs never mix.
        candidates.sort(key=lambda item: (
            item["bbox_xyxy"][1], item["bbox_xyxy"][0], item["bbox_xyxy"][3]
        ))

        words = []
        settings = None
        with tempfile.TemporaryDirectory(
            prefix="layout-ocr-", dir=str(output_path.parent)
        ) as temporary_dir:
            temporary_dir = Path(temporary_dir)
            block_offset = 0
            for index, region in enumerate(candidates, start=1):
                left, top, right, bottom = region["bbox_xyxy"]
                crop_path = temporary_dir / f"region-{index:04}.png"
                page.crop((left, top, right, bottom)).save(crop_path)
                result = recognize_page(
                    crop_path,
                    language,
                    psm=psm,
                    offset_x=left,
                    offset_y=top,
                    full_page_width=page_width,
                    full_page_height=page_height,
                )
                if settings is None:
                    settings = result["ocr_settings"]
                max_block = max(
                    (word["block_num"] for word in result["words"]), default=0
                )
                for word in result["words"]:
                    word["block_num"] += block_offset
                    word["layout_region_index"] = index
                    words.append(word)
                block_offset += max(1, max_block + 1)

    return {
        "stage": "ocr",
        "ocr_mode": "layout_regions",
        "source_image": str(page_path),
        "page_width": page_width,
        "page_height": page_height,
        "ocr_settings": settings or {},
        "layout_source": str(layout_path),
        "layout_regions": candidates,
        "words": words,
    }


@app.command()
def run(
    page: Path = typer.Argument(..., exists=True, dir_okay=False),
    layout: Path = typer.Argument(..., exists=True, dir_okay=False),
    language: str = typer.Option(..., "--language", "-l"),
    psm: int = typer.Option(6, "--psm", min=0, max=13),
    output: Path = typer.Option(Path("outputs/layout-ocr.json"), "--output", "-o"),
):
    """OCR all recognized text blocks and retain page-pixel word boxes."""
    try:
        result = ocr_layout_regions(page, layout, language, psm, output)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise typer.BadParameter(str(error)) from error
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(
        f"OCR'd {len(result['layout_regions'])} layout region(s) and "
        f"{len(result['words'])} word(s); saved to {output}"
    )


if __name__ == "__main__":
    app()
