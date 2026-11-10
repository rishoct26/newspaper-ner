import json
from pathlib import Path

import typer

from .ocr import recognize_page

app = typer.Typer(help="Process newspaper page images.")


@app.command()
def ocr(
    image: Path = typer.Argument(..., exists=True, dir_okay=False),
    language: str = typer.Option(..., "--language", "-l"),
    output: Path = typer.Option(Path("outputs/ocr-result.json"), "--output", "-o"),
    psm: int = typer.Option(3, "--psm", min=0, max=13, help="Tesseract page segmentation mode (0–13)."),
    offset_x: int = typer.Option(0, "--offset-x", min=0, help="Crop's left position on the full page, in pixels."),
    offset_y: int = typer.Option(0, "--offset-y", min=0, help="Crop's top position on the full page, in pixels."),
    page_width: int | None = typer.Option(None, "--page-width", min=1, help="Full scanned page width in pixels (required with crop offsets)."),
    page_height: int | None = typer.Option(None, "--page-height", min=1, help="Full scanned page height in pixels (required with crop offsets)."),
):
    result = recognize_page(
        image,
        language,
        psm,
        offset_x,
        offset_y,
        page_width,
        page_height,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    typer.echo(f"Saved OCR result to {output}")


if __name__ == "__main__":
    app()
