"""Run the OCR, NER, and overlay stages using saved layout detections."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .layout_ocr import ocr_layout_regions
from .ner import recognize_entities
from .overlay import draw_entities

app = typer.Typer(
    help="Run OCR, English NER, and entity overlay using a page and layout JSON."
)


def run_page(
    page: Path,
    layout: Path,
    language: str,
    output_dir: Path,
    psm: int = 6,
) -> dict:
    page = page.resolve()
    layout = layout.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    ocr_path = output_dir / f"{page.stem}_ocr.json"
    ner_path = output_dir / f"{page.stem}_ner.json"
    overlay_path = output_dir / f"{page.stem}_entities.png"

    ocr_result = ocr_layout_regions(page, layout, language, psm, ocr_path)
    ocr_path.write_text(
        json.dumps(ocr_result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    ner_result = recognize_entities(ocr_result, ocr_path)
    ner_path.write_text(
        json.dumps(ner_result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    overlay_count = draw_entities(page, ner_path, overlay_path)
    return {
        "ocr_path": ocr_path,
        "ner_path": ner_path,
        "overlay_path": overlay_path,
        "region_count": len(ocr_result["layout_regions"]),
        "word_count": len(ocr_result["words"]),
        "entity_count": len(ner_result["entities"]),
        "overlay_count": overlay_count,
    }


@app.command()
def run(
    page: Path = typer.Argument(..., exists=True, dir_okay=False),
    layout: Path = typer.Argument(..., exists=True, dir_okay=False),
    language: str = typer.Option(..., "--language", "-l"),
    output_dir: Path = typer.Option(Path("outputs/run-page"), "--output-dir"),
    psm: int = typer.Option(6, "--psm", min=0, max=13),
):
    """Create page-level OCR JSON, NER JSON, and a colored entity overlay."""
    try:
        result = run_page(page, layout, language, output_dir, psm)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise typer.BadParameter(str(error)) from error
    typer.echo(
        f"Processed {result['region_count']} layout region(s) and "
        f"{result['word_count']} OCR word(s); found "
        f"{result['entity_count']} entity/entities.\n"
        f"OCR: {result['ocr_path']}\n"
        f"NER: {result['ner_path']}\n"
        f"Overlay: {result['overlay_path']}"
    )


if __name__ == "__main__":
    app()
