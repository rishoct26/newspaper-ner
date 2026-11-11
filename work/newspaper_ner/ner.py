"""Run a baseline spaCy English named-entity recognizer on OCR JSON."""

from __future__ import annotations

import json
from pathlib import Path

import spacy
import typer

app = typer.Typer(help="Recognize named entities in OCR output.")
MODEL_NAME = "en_core_web_lg"
LABEL_MAP = {
    "PERSON": "PER",
    "ORG": "ORG",
    "GPE": "LOC",
    "LOC": "LOC",
    "DATE": "DATE",
}


def _rebuild_text(words: list[dict]) -> tuple[str, list[dict]]:
    """Rebuild text in Tesseract reading order and retain word character spans."""
    grouped: dict[tuple[int, int, int], list[tuple[int, dict]]] = {}
    for index, word in enumerate(words):
        key = (int(word["block_num"]), int(word["par_num"]), int(word["line_num"]))
        grouped.setdefault(key, []).append((index, word))

    pieces: list[str] = []
    aligned_words: list[dict] = []
    cursor = 0
    for line_index, line_key in enumerate(sorted(grouped)):
        if line_index:
            pieces.append("\n")
            cursor += 1
        line_words = sorted(grouped[line_key], key=lambda item: int(item[1]["word_num"]))
        for word_index, word in line_words:
            if aligned_words and aligned_words[-1]["line_key"] == line_key:
                pieces.append(" ")
                cursor += 1
            text = str(word["text"])
            start = cursor
            pieces.append(text)
            cursor += len(text)
            aligned_words.append({
                "index": word_index,
                "start": start,
                "end": cursor,
                "line_key": line_key,
                "word": word,
            })
    return "".join(pieces), aligned_words


def recognize_entities(ocr_data: dict, source_path: Path) -> dict:
    words = ocr_data.get("words", [])
    if not words:
        raise ValueError("OCR result has no recognized words.")
    languages = {word.get("language") for word in words}
    if languages != {"en"}:
        raise ValueError("This first NER baseline supports English OCR results only.")

    text, aligned_words = _rebuild_text(words)
    try:
        nlp = spacy.load(MODEL_NAME)
    except OSError as error:
        raise FileNotFoundError(
            "English spaCy model is missing. Install it with: "
            "python -m spacy download en_core_web_lg"
        ) from error
    doc = nlp(text)

    entities = []
    for entity in doc.ents:
        mapped_label = LABEL_MAP.get(entity.label_)
        if mapped_label is None:
            continue

        source_items = [
            item for item in aligned_words
            if item["start"] < entity.end_char and item["end"] > entity.start_char
        ]
        if not source_items:
            continue
        source_words = [item["word"] for item in source_items]

        boxes = [word["bbox"] for word in source_words]
        left = min(box["x"] for box in boxes)
        top = min(box["y"] for box in boxes)
        right = max(box["x"] + box["width"] for box in boxes)
        bottom = max(box["y"] + box["height"] for box in boxes)
        ocr_confidences = [word["ocr_confidence"] for word in source_words]

        entities.append({
            "text": entity.text,
            "label": mapped_label,
            "source_label": entity.label_,
            "language": "en",
            "ner_confidence": None,
            "ocr_confidence": round(sum(ocr_confidences) / len(ocr_confidences), 2),
            "bbox": {"x": left, "y": top, "width": right - left, "height": bottom - top},
            "ocr_word_indices": [item["index"] for item in source_items],
            "char_span": {"start": entity.start_char, "end": entity.end_char},
        })

    return {
        "stage": "ner",
        "source_ocr_result": str(source_path.resolve()),
        "source_region_id": ocr_data.get("region_id"),
        "source_image": ocr_data.get("source_image"),
        "page_width": ocr_data.get("page_width"),
        "page_height": ocr_data.get("page_height"),
        "language": "en",
        "ner_model": {"name": MODEL_NAME, "version": nlp.meta.get("version")},
        "confidence_note": (
            "spaCy Doc.ents does not expose calibrated entity confidence; "
            "ner_confidence is null. ocr_confidence is the mean OCR confidence "
            "of the words mapped to the entity."
        ),
        "text": text,
        "entities": entities,
    }


@app.command()
def entities(
    ocr_result: Path = typer.Argument(..., exists=True, dir_okay=False),
    output: Path = typer.Option(Path("outputs/ner-result.json"), "--output", "-o"),
):
    """Run English NER on a word-level OCR result JSON."""
    try:
        data = json.loads(ocr_result.read_text(encoding="utf-8"))
        result = recognize_entities(data, ocr_result)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise typer.BadParameter(str(error)) from error

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(f"Saved NER result to {output} ({len(result['entities'])} entities)")


if __name__ == "__main__":
    app()
