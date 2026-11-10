"""Pool saved per-region OCR evaluation results."""

from __future__ import annotations

import json
from pathlib import Path

import typer

app = typer.Typer(help="Pool OCR evaluation results from multiple regions.")
VARIANTS = ("no_join", "line_end_hyphens_joined")


def _pooled_metric(region_results: list[dict], metric: str, variant: str) -> dict:
    edits = sum(item["results"][variant][metric]["edits"] for item in region_results)
    reference_length = sum(
        item["results"][variant][metric]["reference_length"] for item in region_results
    )
    return {
        "edits": edits,
        "reference_length": reference_length,
        "rate": edits / reference_length if reference_length else None,
    }


@app.command()
def aggregate(
    evaluation_files: list[Path] = typer.Argument(..., exists=True, dir_okay=False),
    output: Path = typer.Option(Path("outputs/pooled-evaluation.json"), "--output", "-o"),
):
    """Combine per-region evaluation JSON files into pooled scores."""
    try:
        region_results = [
            json.loads(path.read_text(encoding="utf-8")) for path in evaluation_files
        ]
        for result in region_results:
            if result.get("evaluation_rules_version") != "v1":
                raise ValueError("All results must use evaluation rules v1.")

        region_ids = [result["region"]["region_id"] for result in region_results]
        if len(region_ids) != len(set(region_ids)):
            raise ValueError("Each region may appear only once in the pooled input.")
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise typer.BadParameter(str(error)) from error

    pooled = {}
    for variant in VARIANTS:
        pooled[variant] = {
            metric: _pooled_metric(region_results, metric, variant)
            for metric in ("cer", "wer")
        }

    result = {
        "evaluation_rules_version": "v1",
        "region_count": len(region_results),
        "input_files": [str(path) for path in evaluation_files],
        "per_region": [
            {
                "region_id": item["region"]["region_id"],
                "region_type": item["region"]["region_type"],
                "split": item["region"]["split"],
                "results": {variant: item["results"][variant] for variant in VARIANTS},
            }
            for item in region_results
        ],
        "pooled": pooled,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(f"Saved pooled evaluation result to {output}")


if __name__ == "__main__":
    app()
