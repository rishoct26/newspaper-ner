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
):
    result = recognize_page(image, language)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    typer.echo(f"Saved OCR result to {output}")


if __name__ == "__main__":
    app()
