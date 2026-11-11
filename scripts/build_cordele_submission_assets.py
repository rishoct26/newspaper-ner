"""Build report figures and untracked, downscaled Cordele demo samples."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "scans/en_dev/en_cordele-dispatch_1926-11-09_p01.png"
LAYOUT = ROOT / "outputs/layout-only/layout.json"
EVALUATION = ROOT / "outputs/cordele-layout-detected-body-evaluation.json"
DEMO = ROOT / "outputs/cordele-submission-demo"
FIGURES = ROOT / "outputs/figures"
SAMPLES = ROOT / "samples"
COLORS = {"PER": (220, 40, 40), "ORG": (35, 105, 220), "LOC": (30, 155, 70), "DATE": (220, 135, 20)}


def font(size: int, bold: bool = False):
    options = ["arialbd.ttf", "Arial Bold.ttf"] if bold else ["arial.ttf", "Arial.ttf"]
    for name in options:
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def wrap(text: str, draw: ImageDraw.ImageDraw, fnt, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if line and draw.textlength(candidate, font=fnt) > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def layout_figure(page: Image.Image, layout: dict, target: Path) -> None:
    width = 1800
    scale = width / page.width
    canvas = page.convert("RGB").resize((width, round(page.height * scale)))
    draw = ImageDraw.Draw(canvas)
    small = font(17, True)
    colors = {"text": (0, 170, 70), "doc_title": (0, 120, 255), "paragraph_title": (0, 120, 255), "header": (255, 175, 0), "image": (160, 200, 0), "table": (180, 50, 190), "figure": (210, 70, 70)}
    for item in layout.get("boxes", []):
        coords = item.get("coordinate", [])
        if len(coords) != 4:
            continue
        x1, y1, x2, y2 = [round(float(value) * scale) for value in coords]
        label = str(item.get("label", "region"))
        color = colors.get(label, (0, 160, 190))
        draw.rectangle((x1, y1, x2, y2), outline=color, width=3)
        caption = f"{label} {float(item.get('score', 0)):.2f}"
        text_box = draw.textbbox((x1, y1), caption, font=small)
        draw.rectangle(text_box, fill=color)
        draw.text((x1, y1), caption, font=small, fill="white")
    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target)


def article_figure(page: Image.Image, evaluation: dict, target: Path) -> None:
    crop_box = (210, 2680, 905, 3300)
    crop = page.crop(crop_box)
    metrics = evaluation["results"]["line_end_hyphens_joined"]
    text = evaluation["inputs"]["line_end_hyphens_joined_hypothesis"]
    canvas = Image.new("RGB", (1800, 790), "white")
    draw = ImageDraw.Draw(canvas)
    title = font(32, True)
    body = font(25)
    draw.text((35, 25), "Article-region OCR and evaluation", font=title, fill="black")
    crop.thumbnail((760, 950), Image.Resampling.LANCZOS)
    canvas.paste(crop, (30, 95))
    draw.text((830, 95), "OCR text (line-end hyphens joined)", font=font(26, True), fill="black")
    lines = wrap(text, draw, body, 920)
    y = 145
    for line in lines:
        draw.text((830, y), line, font=body, fill=(30, 30, 30))
        y += 34
    cer = metrics["cer"]
    wer = metrics["wer"]
    caption = f"Region CER {cer['rate']:.2%} ({cer['edits']}/{cer['reference_length']} chars) | WER {wer['rate']:.2%} ({wer['edits']}/{wer['reference_length']} words)"
    draw.text((35, 745), caption, font=font(24, True), fill=(30, 70, 120))
    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target)


def entity_figure(page: Image.Image, ner: dict, target: Path) -> None:
    areas = [
        ("Cordele masthead", (800, 100, 3200, 450)),
        ("Hunter article body", (210, 2680, 905, 3300)),
        ("Mid-page news column", (1800, 1000, 2650, 1700)),
    ]
    canvas = Image.new("RGB", (1500, 3400), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((28, 18), "NER entities mapped to page regions (en_core_web_lg)", font=font(34, True), fill="black")
    x = 28
    for label in ("PER", "ORG", "LOC", "DATE"):
        color = COLORS[label]
        draw.rectangle((x, 68, x + 30, 98), fill=color)
        draw.text((x + 40, 65), label, font=font(28, True), fill="black")
        x += 190
    y0 = 130
    for name, box in areas:
        draw.text((28, y0), name, font=font(32, True), fill="black")
        crop = page.crop(box)
        scale = min(1.6, 1440 / crop.width, 900 / crop.height)
        crop = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.Resampling.LANCZOS)
        draw_y = y0 + 52
        canvas.paste(crop, (28, draw_y))
        ent_draw = ImageDraw.Draw(canvas)
        left, top, _, _ = box
        for entity in ner.get("entities", []):
            label = entity.get("label")
            if label not in COLORS:
                continue
            bb = entity.get("bbox", {})
            cx = float(bb.get("x", 0)) + float(bb.get("width", 0)) / 2
            cy = float(bb.get("y", 0)) + float(bb.get("height", 0)) / 2
            if not (box[0] <= cx < box[2] and box[1] <= cy < box[3]):
                continue
            x1 = 28 + round((float(bb["x"]) - left) * scale)
            y1 = draw_y + round((float(bb["y"]) - top) * scale)
            x2 = x1 + max(2, round(float(bb["width"]) * scale))
            y2 = y1 + max(2, round(float(bb["height"]) * scale))
            color = COLORS[label]
            ent_draw.rectangle((x1, y1, x2, y2), outline=color, width=3)
            tag = f"{label}: {' '.join(str(entity.get('text', '')).split())[:30]}"
            tag_font = font(28, True)
            tb = ent_draw.textbbox((x1, max(draw_y, y1 - 22)), tag, font=tag_font)
            ent_draw.rectangle(tb, fill=color)
            ent_draw.text((tb[0], tb[1]), tag, font=tag_font, fill="white")
        y0 = draw_y + crop.height + 55
    canvas = canvas.crop((0, 0, 1500, y0 + 10))
    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target)


def scaled_copy(source: Path, target: Path, scale: float) -> None:
    data = json.loads(source.read_text(encoding="utf-8"))
    data["page_width"] = round(data["page_width"] * scale)
    data["page_height"] = round(data["page_height"] * scale)
    for word in data.get("words", []):
        bb = word.get("bbox", {})
        for key in ("x", "y", "width", "height"):
            if key in bb:
                bb[key] = round(bb[key] * scale)
    for region in data.get("layout_regions", []):
        bb = region.get("bbox_xyxy")
        if bb:
            region["bbox_xyxy"] = [round(value * scale) for value in bb]
    data["source_image"] = "cordele-page.png"
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    with Image.open(PAGE) as image:
        page = image.convert("RGB")
    layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
    evaluation = json.loads(EVALUATION.read_text(encoding="utf-8"))
    ocr_path, ner_path = DEMO / "ocr.json", DEMO / "ner.json"
    ner = json.loads(ner_path.read_text(encoding="utf-8"))
    figure_paths = [FIGURES / "cordele-layout-detection.png", FIGURES / "cordele-article-ocr-evaluation.png", FIGURES / "cordele-ner-regions.png"]
    layout_figure(page, layout, figure_paths[0])
    article_figure(page, evaluation, figure_paths[1])
    entity_figure(page, ner, figure_paths[2])

    SAMPLES.mkdir(parents=True, exist_ok=True)
    sample_page = SAMPLES / "cordele-page.png"
    sample_width = 1800
    scale = sample_width / page.width
    page.resize((sample_width, round(page.height * scale)), Image.Resampling.LANCZOS).save(sample_page)
    scaled_copy(ocr_path, SAMPLES / "cordele-ocr.json", scale)
    sample_ner_path = SAMPLES / "cordele-ner.json"
    sample_ner = json.loads(ner_path.read_text(encoding="utf-8"))
    sample_ner["page_width"] = round(sample_ner["page_width"] * scale)
    sample_ner["page_height"] = round(sample_ner["page_height"] * scale)
    for entity in sample_ner.get("entities", []):
        bb = entity.get("bbox", {})
        for key in ("x", "y", "width", "height"):
            if key in bb:
                bb[key] = round(bb[key] * scale)
    sample_ner["source_image"] = "cordele-page.png"
    sample_ner["source_ocr_result"] = "cordele-ocr.json"
    sample_ner_path.write_text(json.dumps(sample_ner, ensure_ascii=False, indent=2), encoding="utf-8")
    from newspaper_ner.overlay import draw_entities
    draw_entities(sample_page, sample_ner_path, SAMPLES / "cordele-overlay.png")
    for figure in figure_paths:
        shutil.copy2(figure, SAMPLES / figure.name)
    print("Created Cordele report figures and sample files.")


if __name__ == "__main__":
    main()
