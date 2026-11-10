"""Score predicted entities against exact-span NER gold annotations."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import typer

from .provenance import git_provenance

app = typer.Typer(help="Evaluate NER predictions against a manually checked gold file.")
LABELS = ("PER", "ORG", "LOC", "DATE")


def _entity_key(entity: dict, gold: bool) -> tuple[int, int, str]:
    if gold:
        start, end = int(entity["start_char"]), int(entity["end_char"])
    else:
        span = entity["char_span"]
        start, end = int(span["start"]), int(span["end"])
    label = str(entity["label"])
    if label not in LABELS:
        raise ValueError(f"Unsupported NER label: {label}")
    return start, end, label


def _metrics(true_positives: int, false_positives: int, false_negatives: int) -> dict:
    predicted = true_positives + false_positives
    gold = true_positives + false_negatives
    precision = true_positives / predicted if predicted else None
    recall = true_positives / gold if gold else None
    f1_denominator = 2 * true_positives + false_positives + false_negatives
    f1 = 2 * true_positives / f1_denominator if f1_denominator else None
    return {
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def score_ner(prediction: dict, gold: dict, prediction_path: Path, gold_path: Path) -> dict:
    if prediction.get("stage") != "ner":
        raise ValueError("Prediction input must be an NER result JSON (stage='ner').")
    if prediction.get("text") != gold.get("input_text"):
        raise ValueError("NER prediction text does not exactly match the gold input_text.")
    if prediction.get("language") != gold.get("language"):
        raise ValueError("NER prediction and gold annotation languages differ.")
    if prediction.get("source_region_id") not in (None, gold.get("source_region_id")):
        raise ValueError("NER prediction and gold annotation region IDs differ.")

    text = gold["input_text"]
    predicted_keys = Counter(_entity_key(entity, gold=False) for entity in prediction["entities"])
    gold_keys = Counter(_entity_key(entity, gold=True) for entity in gold["entities"])

    for entity in prediction["entities"]:
        key = _entity_key(entity, gold=False)
        start, end, _ = key
        if text[start:end] != entity["text"]:
            raise ValueError(f"Predicted entity text does not match its character span: {entity['text']}")
    for entity in gold["entities"]:
        start, end, _ = _entity_key(entity, gold=True)
        if text[start:end] != entity["text"]:
            raise ValueError(f"Gold entity text does not match its character span: {entity['text']}")

    correct = predicted_keys & gold_keys
    per_label = {}
    for label in LABELS:
        tp = sum(count for (_, _, item_label), count in correct.items() if item_label == label)
        fp = sum(
            count for (_, _, item_label), count in (predicted_keys - gold_keys).items()
            if item_label == label
        )
        fn = sum(
            count for (_, _, item_label), count in (gold_keys - predicted_keys).items()
            if item_label == label
        )
        per_label[label] = _metrics(tp, fp, fn)

    tp = sum(correct.values())
    fp = sum((predicted_keys - gold_keys).values())
    fn = sum((gold_keys - predicted_keys).values())
    return {
        "evaluation_rules_version": "ner-span-v1",
        "matching": "exact character span and entity label",
        "split": gold["split"],
        "language": gold["language"],
        "source_region_id": gold["source_region_id"],
        "prediction_file": str(prediction_path),
        "gold_file": str(gold_path),
        "model": prediction.get("ner_model"),
        "confidence_note": prediction.get("confidence_note"),
        "software": git_provenance(),
        "overall": _metrics(tp, fp, fn),
        "by_label": per_label,
        "predictions": prediction["entities"],
        "gold_entities": gold["entities"],
    }


@app.command()
def evaluate(
    prediction_file: Path = typer.Argument(..., exists=True, dir_okay=False),
    gold_file: Path = typer.Argument(..., exists=True, dir_okay=False),
    output: Path = typer.Option(Path("outputs/ner-evaluation.json"), "--output", "-o"),
):
    """Calculate exact-span precision, recall, and F1."""
    try:
        prediction = json.loads(prediction_file.read_text(encoding="utf-8"))
        gold = json.loads(gold_file.read_text(encoding="utf-8"))
        result = score_ner(prediction, gold, prediction_file, gold_file)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise typer.BadParameter(str(error)) from error

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(f"Saved NER evaluation to {output}")


if __name__ == "__main__":
    app()
