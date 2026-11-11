"""Compare clean-reference and OCR-text NER on development annotations."""

from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import spacy
import typer

from .ner import LABEL_MAP, MODEL_NAME
from .ner_evaluation import LABELS, _metrics
from .provenance import git_provenance

app = typer.Typer(help="Compare clean-text and OCR-text NER on annotated development regions.")
COUNT_NAMES = ("true_positives", "false_positives", "false_negatives")
DEFAULT_SEED = 20261111
KNOWN_NEWSPAPER_TITLES = {
    "DOUGLAS DAILY DISPATCH",
    "CORDELE DISPATCH",
    "NEW BRITAIN HERALD",
    "WASHINGTON DAILY NEWS",
}


def _normalize_title(text: str) -> str:
    return " ".join(
        "".join(ch if ch.isalnum() else " " for ch in text.upper()).split()
    )


def _apply_known_title_rule(entities: list[dict]) -> list[dict]:
    """Relabel exact known newspaper mastheads from PER to ORG for a dev trial."""
    updated = []
    for entity in entities:
        item = dict(entity)
        normalized = _normalize_title(str(item["text"]))
        known_titles = {_normalize_title(title) for title in KNOWN_NEWSPAPER_TITLES}
        if item.get("label") == "PER" and normalized in known_titles:
            item["label"] = "ORG"
        updated.append(item)
    return updated


def _exact_counts(predictions: list[dict], gold: list[dict]) -> dict:
    predicted = Counter((str(item["text"]), str(item["label"])) for item in predictions)
    expected = Counter((str(item["text"]), str(item["label"])) for item in gold)
    correct = predicted & expected
    return {
        "true_positives": sum(correct.values()),
        "false_positives": sum((predicted - expected).values()),
        "false_negatives": sum((expected - predicted).values()),
    }


def _lenient_counts(
    predictions: list[dict], gold: list[dict], threshold: float = 0.8
) -> tuple[dict, list[dict]]:
    """Match same-label entities once; partial matches require text ratio >= threshold."""
    remaining_predictions = list(range(len(predictions)))
    remaining_gold = list(range(len(gold)))
    pairs: list[tuple[int, int, float]] = []

    # Consume exact duplicates first so they cannot be used for a second match.
    gold_by_key: dict[tuple[str, str], list[int]] = defaultdict(list)
    for index, item in enumerate(gold):
        gold_by_key[(str(item["text"]), str(item["label"]))].append(index)
    exact_pairs: list[tuple[int, int, float]] = []
    used_predictions: set[int] = set()
    used_gold: set[int] = set()
    for pred_index, item in enumerate(predictions):
        key = (str(item["text"]), str(item["label"]))
        candidates = gold_by_key.get(key, [])
        gold_index = next((i for i in candidates if i not in used_gold), None)
        if gold_index is not None:
            exact_pairs.append((pred_index, gold_index, 1.0))
            used_predictions.add(pred_index)
            used_gold.add(gold_index)

    remaining_predictions = [i for i in remaining_predictions if i not in used_predictions]
    remaining_gold = [i for i in remaining_gold if i not in used_gold]

    # Build eligible edges, sorted by similarity for deterministic tie-breaking.
    edges: dict[int, list[tuple[int, float]]] = {}
    for pred_index in remaining_predictions:
        pred = predictions[pred_index]
        candidates: list[tuple[int, float]] = []
        for gold_index in remaining_gold:
            expected = gold[gold_index]
            if str(pred["label"]) != str(expected["label"]):
                continue
            ratio = SequenceMatcher(
                None, str(pred["text"]), str(expected["text"]), autojunk=False
            ).ratio()
            if ratio >= threshold:
                candidates.append((gold_index, ratio))
        edges[pred_index] = sorted(candidates, key=lambda pair: (-pair[1], pair[0]))

    # Maximum-cardinality bipartite matching; exact pairs were already fixed.
    matched_gold: dict[int, int] = {}

    def augment(pred_index: int, visited: set[int]) -> bool:
        for gold_index, _ratio in edges[pred_index]:
            if gold_index in visited:
                continue
            visited.add(gold_index)
            previous = matched_gold.get(gold_index)
            if previous is None or augment(previous, visited):
                matched_gold[gold_index] = pred_index
                return True
        return False

    for pred_index in sorted(remaining_predictions, key=lambda i: (len(edges[i]), i)):
        augment(pred_index, set())

    partial_pairs = []
    for gold_index, pred_index in matched_gold.items():
        ratio = next(r for index, r in edges[pred_index] if index == gold_index)
        partial_pairs.append((pred_index, gold_index, ratio))

    pairs = exact_pairs + partial_pairs
    counts = {
        "true_positives": len(pairs),
        "false_positives": len(predictions) - len(pairs),
        "false_negatives": len(gold) - len(pairs),
    }
    details = [
        {
            "prediction_text": str(predictions[pred_index]["text"]),
            "gold_text": str(gold[gold_index]["text"]),
            "label": str(gold[gold_index]["label"]),
            "similarity": round(ratio, 4),
            "exact": ratio == 1.0,
        }
        for pred_index, gold_index, ratio in sorted(pairs, key=lambda p: (p[0], p[1]))
    ]
    return counts, details


def _score_variants(predictions: list[dict], gold: list[dict], threshold: float) -> dict:
    exact = _exact_counts(predictions, gold)
    lenient, matches = _lenient_counts(predictions, gold, threshold)
    exact_by_label = {}
    lenient_by_label = {}
    for label in LABELS:
        label_predictions = [item for item in predictions if item["label"] == label]
        label_gold = [item for item in gold if item["label"] == label]
        exact_by_label[label] = _metrics(**_exact_counts(label_predictions, label_gold))
        label_counts, _ = _lenient_counts(label_predictions, label_gold, threshold)
        lenient_by_label[label] = _metrics(**label_counts)
    return {
        "exact": {"overall": _metrics(**exact), "by_label": exact_by_label},
        "lenient": {"overall": _metrics(**lenient), "by_label": lenient_by_label},
        "lenient_match_details": matches,
    }


def _newspaper(region_id: str) -> str:
    if region_id.startswith("cordele-"):
        return "Cordele Dispatch"
    if region_id.startswith(("douglas-", "az0346-")):
        return "Douglas Daily Dispatch"
    if region_id.startswith("new-britain-"):
        return "New Britain Herald"
    if region_id.startswith("washington-"):
        return "Washington Daily News"
    return "Other"


def _pool(rows: list[dict], mode: str, variant: str) -> dict:
    counts = {
        key: sum(row[mode][variant]["overall"][key] for row in rows)
        for key in COUNT_NAMES
    }
    by_label = {}
    for label in LABELS:
        label_counts = {
            key: sum(row[mode][variant]["by_label"][label][key] for row in rows)
            for key in COUNT_NAMES
        }
        by_label[label] = _metrics(**label_counts)
    return {
        "region_count": len(rows),
        "gold_entity_count": counts["true_positives"] + counts["false_negatives"],
        "prediction_count": counts["true_positives"] + counts["false_positives"],
        "overall": _metrics(**counts),
        "by_label": by_label,
    }


def _percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    position = (len(sorted_values) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = position - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def _bootstrap_f1(rows: list[dict], mode: str, variant: str, samples: int, seed: int) -> dict:
    rng = random.Random(seed)
    values: list[float] = []
    for _ in range(samples):
        selected = [rows[rng.randrange(len(rows))] for _ in rows]
        counts = {
            key: sum(row[mode][variant]["overall"][key] for row in selected)
            for key in COUNT_NAMES
        }
        values.append(_metrics(**counts)["f1"] or 0.0)
    values.sort()
    pooled_counts = {
        key: sum(row[mode][variant]["overall"][key] for row in rows)
        for key in COUNT_NAMES
    }
    return {
        "point_estimate": _metrics(**pooled_counts)["f1"],
        "confidence_level": 0.95,
        "interval": [_percentile(values, 0.025), _percentile(values, 0.975)],
        "method": "percentile bootstrap; sample regions with replacement; pool mention counts per replicate",
        "resampling_unit": "region",
        "samples": samples,
        "seed": seed,
    }


def _clean_text_entities(nlp, text: str) -> list[dict]:
    doc = nlp(text)
    result = []
    for entity in doc.ents:
        label = LABEL_MAP.get(entity.label_)
        if label is not None:
            result.append({
                "text": entity.text,
                "label": label,
                "source_label": entity.label_,
                "char_span": {"start": entity.start_char, "end": entity.end_char},
            })
    return result


@app.command()
def compare(
    input_dir: Path = typer.Option(Path("outputs"), "--input-dir", "-i", exists=True, file_okay=False),
    output: Path = typer.Option(Path("outputs/ner-dev-comparison.json"), "--output", "-o"),
    threshold: float = typer.Option(0.8, min=0.0, max=1.0, help="Minimum character similarity for lenient matching."),
    bootstrap_samples: int = typer.Option(1000, min=1, help="Region bootstrap resamples."),
    seed: int = typer.Option(DEFAULT_SEED, help="Seed for reproducible bootstrap and false-positive sample."),
    newspaper_title_rule: bool = typer.Option(False, "--newspaper-title-rule", help="Apply the dev-known exact masthead PER-to-ORG correction."),
    scope_review: Path | None = typer.Option(None, "--scope-review", exists=True, dir_okay=False, help="JSON file listing regions excluded from paired evaluation due to crop/reference mismatch."),
):
    """Compare OCR and verified-reference NER, exact/lenient, by region and title."""
    try:
        evaluations = []
        for path in sorted(input_dir.glob("**/*evaluation*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if (
                data.get("evaluation_rules_version") == "ner-text-v1"
                and data.get("split") == "dev"
                and data.get("source_region_id")
            ):
                evaluations.append((path, data))
        ids = [data["source_region_id"] for _, data in evaluations]
        if not evaluations:
            raise ValueError("No ner-text-v1 development-region evaluations found.")
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate development source_region_id in evaluation files.")
        excluded_region_ids: set[str] = set()
        scope_review_note = None
        if scope_review is not None:
            review = json.loads(scope_review.read_text(encoding="utf-8"))
            excluded_region_ids = set(review.get("exclude_from_paired_evaluation", []))
            unknown = excluded_region_ids - set(ids)
            if unknown:
                raise ValueError(f"Scope-review IDs have no matching dev evaluation: {sorted(unknown)}")
            evaluations = [
                pair for pair in evaluations
                if pair[1]["source_region_id"] not in excluded_region_ids
            ]
            scope_review_note = review.get("method")
            if not evaluations:
                raise ValueError("Scope review excluded every development region.")

        nlp = spacy.load(MODEL_NAME)
        rows = []
        for path, evaluation in evaluations:
            gold_path = Path(evaluation["gold_file"])
            if not gold_path.is_absolute():
                gold_path = Path.cwd() / gold_path
            gold_data = json.loads(gold_path.read_text(encoding="utf-8"))
            if gold_data.get("split") != "dev":
                raise ValueError(f"Gold file is not dev data: {gold_path}")
            if gold_data.get("source_region_id") != evaluation["source_region_id"]:
                raise ValueError(f"Evaluation/gold region mismatch: {path}")
            gold_entities = gold_data["entities"]
            ocr_predictions = evaluation["predictions"]
            clean_predictions = _clean_text_entities(nlp, gold_data["input_text"])
            if newspaper_title_rule:
                ocr_predictions = _apply_known_title_rule(ocr_predictions)
                clean_predictions = _apply_known_title_rule(clean_predictions)
            rows.append({
                "source_region_id": evaluation["source_region_id"],
                "newspaper": _newspaper(evaluation["source_region_id"]),
                "evaluation_file": str(path),
                "gold_file": str(gold_path),
                "gold_entity_count": len(gold_entities),
                "ocr": _score_variants(ocr_predictions, gold_entities, threshold),
                "clean_text": _score_variants(clean_predictions, gold_entities, threshold),
                "clean_text_predictions": clean_predictions,
                "gold_entities": gold_entities,
                "ocr_predictions": ocr_predictions,
            })

        by_title: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            by_title[row["newspaper"]].append(row)

        def summarize(items: list[dict]) -> dict:
            return {
                mode: {
                    variant: _pool(items, mode, variant)
                    for variant in ("exact", "lenient")
                }
                for mode in ("ocr", "clean_text")
            }

        result = {
            "evaluation_rules_version": "ner-text-v1",
            "lenient_matching": {
                "method": "same-label character similarity using difflib.SequenceMatcher; maximum one-to-one matching after exact matches",
                "threshold": threshold,
                "repeated_mentions": "counted separately",
            },
            "clean_text_source": "verified input_text from each gold annotation; same spaCy model as OCR-text predictions",
            "ocr_text_source": "saved prediction entities from per-region ner-text-v1 evaluation JSONs",
            "postprocessing": (
                "Exact known newspaper-title PER-to-ORG correction applied to clean and OCR entities."
                if newspaper_title_rule else "None"
            ),
            "scope_review": {
                "file": str(scope_review) if scope_review is not None else None,
                "excluded_region_count": len(excluded_region_ids),
                "excluded_region_ids": sorted(excluded_region_ids),
                "method": scope_review_note,
            },
            "model": {"name": MODEL_NAME, "version": nlp.meta.get("version")},
            "software": git_provenance(),
            "region_count": len(rows),
            "gold_entity_count": sum(row["gold_entity_count"] for row in rows),
            "overall": summarize(rows),
            "by_newspaper": {title: summarize(items) for title, items in sorted(by_title.items())},
            "bootstrap": {
                mode: {
                    variant: _bootstrap_f1(rows, mode, variant, bootstrap_samples, seed)
                    for variant in ("exact", "lenient")
                }
                for mode in ("ocr", "clean_text")
            },
            "per_region": rows,
        }
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise typer.BadParameter(str(error)) from error

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(f"Compared {len(rows)} development regions; saved to {output}")


if __name__ == "__main__":
    app()
