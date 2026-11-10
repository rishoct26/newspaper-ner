"""Pool saved exact-span NER evaluation results."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .ner_evaluation import LABELS, _metrics

app = typer.Typer(help="Pool NER evaluation results across annotated regions.")
COUNT_NAMES = ("true_positives", "false_positives", "false_negatives")


def _recalculate(metrics: dict) -> dict:
    return _metrics(**{key: metrics[key] for key in COUNT_NAMES})


@app.command()
def aggregate(
    evaluation_files: list[Path] = typer.Argument(..., exists=True, dir_okay=False),
    output: Path = typer.Option(Path("outputs/pooled-ner-evaluation.json"), "--output", "-o"),
):
    """Combine exact-span counts and compute pooled NER metrics."""
    try:
        region_results = [
            json.loads(path.read_text(encoding="utf-8")) for path in evaluation_files
        ]
        for result in region_results:
            if result.get("evaluation_rules_version") != "ner-span-v1":
                raise ValueError("All inputs must use NER scoring rules ner-span-v1.")

        region_ids = [result["source_region_id"] for result in region_results]
        if len(region_ids) != len(set(region_ids)):
            raise ValueError("Each region may appear only once in the pooled input.")
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise typer.BadParameter(str(error)) from error

    overall_counts = {
        key: sum(item["overall"][key] for item in region_results)
        for key in COUNT_NAMES
    }
    pooled_overall = _metrics(**overall_counts)

    pooled_by_label = {}
    for label in LABELS:
        counts = {
            key: sum(item["by_label"][label][key] for item in region_results)
            for key in COUNT_NAMES
        }
        pooled_by_label[label] = _metrics(**counts)

    result = {
        "evaluation_rules_version": "ner-span-v1",
        "matching": "exact character span and entity label",
        "region_count": len(region_results),
        "input_files": [str(path) for path in evaluation_files],
        "per_region": [
            {
                "source_region_id": item["source_region_id"],
                "split": item["split"],
                "overall": _recalculate(item["overall"]),
                "by_label": {
                    label: _recalculate(item["by_label"][label]) for label in LABELS
                },
            }
            for item in region_results
        ],
        "overall": pooled_overall,
        "by_label": pooled_by_label,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(f"Saved pooled NER evaluation to {output}")


if __name__ == "__main__":
    app()
