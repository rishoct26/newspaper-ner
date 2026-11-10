"""Draw OCR-linked named entities on their source page image."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from PIL import Image, ImageDraw, ImageFont

app = typer.Typer(help="Draw named-entity boxes on a newspaper page image.")
COLORS = {
    "PER": (220, 40, 40),
    "ORG": (35, 105, 220),
    "LOC": (30, 155, 70),
    "DATE": (220, 135, 20),
}


def draw_entities(page_path: Path, ner_path: Path, output_path: Path) -> int:
    page_path = page_path.resolve()
    ner_path = ner_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = json.loads(ner_path.read_text(encoding="utf-8"))
    with Image.open(page_path) as source:
        page = source.convert("RGB")
        draw = ImageDraw.Draw(page)
        line_width = max(3, page.width // 1800)
        font = ImageFont.load_default(size=max(16, page.width // 250))
        drawn = 0

        for entity in data.get("entities", []):
            label = str(entity.get("label", ""))
            color = COLORS.get(label)
            bbox = entity.get("bbox", {})
            try:
                left = int(bbox["x"])
                top = int(bbox["y"])
                right = left + int(bbox["width"])
                bottom = top + int(bbox["height"])
            except (KeyError, TypeError, ValueError):
                continue
            if color is None or left < 0 or top < 0 or right > page.width or bottom > page.height:
                continue
            if right <= left or bottom <= top:
                continue

            draw.rectangle(
                (left, top, right - 1, bottom - 1),
                outline=color,
                width=line_width,
            )
            tag = f"{label}: {entity.get('text', '')}"
            text_box = draw.textbbox((0, 0), tag, font=font, stroke_width=0)
            padding = 2
            tag_width = text_box[2] - text_box[0] + padding * 2
            tag_height = text_box[3] - text_box[1] + padding * 2
            tag_top = top - tag_height if top >= tag_height else bottom
            tag_bottom = min(page.height, tag_top + tag_height)
            draw.rectangle(
                (left, tag_top, min(page.width - 1, left + tag_width), tag_bottom),
                fill=color,
            )
            draw.text(
                (left + padding, tag_top + padding),
                tag,
                fill=(255, 255, 255),
                font=font,
            )
            drawn += 1

        page.save(output_path)
    return drawn


@app.command()
def render(
    page: Path = typer.Argument(..., exists=True, dir_okay=False),
    ner_result: Path = typer.Argument(..., exists=True, dir_okay=False),
    output: Path = typer.Option(Path("outputs/entity-overlay.png"), "--output", "-o"),
):
    """Draw entity boxes from a NER JSON file on the supplied full-page image."""
    try:
        count = draw_entities(page, ner_result, output)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        raise typer.BadParameter(str(error)) from error
    typer.echo(f"Drew {count} entity box(es) on {output}")


if __name__ == "__main__":
    app()
