"""Evaluate OCR text against one annotated newspaper region."""

from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
import unicodedata
from pathlib import Path

import PIL
import pytesseract
import typer

from .provenance import git_provenance

app = typer.Typer(help="Evaluate OCR output against an annotated region.")
HYPHENS = {"-", "‐", "‑", "\u00ad"}
DASHES = {
    "‐", "‑", "‒", "–", "—", "―", "−", "﹘", "﹣", "－", "\u00ad"
}
QUOTE_MAP = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})


def _has_letter_or_decimal_digit(line: str) -> bool:
    return any(
        unicodedata.category(char).startswith("L")
        or unicodedata.category(char) == "Nd"
        for char in line
    )


def _reconstruct_lines(words: list[dict], bbox: list[int]) -> list[str]:
    left, top, right, bottom = bbox
    selected = []
    for word in words:
        box = word["bbox"]
        center_x = box["x"] + box["width"] / 2
        center_y = box["y"] + box["height"] / 2
        if left <= center_x < right and top <= center_y < bottom:
            selected.append(word)

    grouped: dict[tuple[int, int, int], list[dict]] = {}
    for word in selected:
        key = (int(word["block_num"]), int(word["par_num"]), int(word["line_num"]))
        grouped.setdefault(key, []).append(word)

    physical_lines = []
    for key in sorted(grouped):
        ordered = sorted(grouped[key], key=lambda word: int(word["word_num"]))
        line = " ".join(str(word["text"]) for word in ordered).replace("|", "").strip()
        if line and _has_letter_or_decimal_digit(line):
            physical_lines.append(line)
    return physical_lines


def _join_physical_lines(lines: list[str], join_hyphens: bool) -> str:
    if not lines:
        return ""

    result = lines[0]
    for next_line in lines[1:]:
        if result.endswith("—") or next_line.startswith("—"):
            result += next_line
        elif (
            join_hyphens
            and result[-1:] in HYPHENS
            and next_line
            and unicodedata.category(next_line[0]) == "Ll"
        ):
            result = result[:-1] + next_line
        else:
            result += " " + next_line
    return result


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = "".join("-" if char in DASHES else char for char in text)
    text = text.translate(QUOTE_MAP)
    return re.sub(r"\s+", " ", text).strip()


def _edit_distance(source: list, target: list) -> int:
    previous = list(range(len(target) + 1))
    for row, source_item in enumerate(source, start=1):
        current = [row]
        for column, target_item in enumerate(target, start=1):
            current.append(min(
                current[-1] + 1,
                previous[column] + 1,
                previous[column - 1] + (source_item != target_item),
            ))
        previous = current
    return previous[-1]


def _score(reference: str, hypothesis: str) -> dict:
    ref_chars, hyp_chars = list(reference), list(hypothesis)
    ref_words, hyp_words = reference.split(), hypothesis.split()
    char_edits = _edit_distance(hyp_chars, ref_chars)
    word_edits = _edit_distance(hyp_words, ref_words)
    return {
        "cer": {"edits": char_edits, "reference_length": len(ref_chars),
                "rate": char_edits / len(ref_chars) if ref_chars else None},
        "wer": {"edits": word_edits, "reference_length": len(ref_words),
                "rate": word_edits / len(ref_words) if ref_words else None},
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tesseract_version(executable: str) -> str | None:
    try:
        result = subprocess.run(
            [executable, "--version"], capture_output=True, text=True,
            check=True, timeout=10,
        )
        return result.stdout.splitlines()[0].removeprefix("tesseract ")
    except (OSError, subprocess.SubprocessError, IndexError):
        return None


def evaluate_region(ocr_data: dict, annotation: dict, region_id: str, ocr_path: Path) -> dict:
    regions = {region["region_id"]: region for region in annotation["regions"]}
    if region_id not in regions:
        raise ValueError(f"Region ID not found in annotation: {region_id}")
    region = regions[region_id]
    lines = _reconstruct_lines(ocr_data.get("words", []), region["bbox_xyxy"])
    raw_ocr = "\n".join(lines)
    reference = _normalize(region["reference_text"])

    no_join_text = _normalize(_join_physical_lines(lines, join_hyphens=False))
    joined_text = _normalize(_join_physical_lines(lines, join_hyphens=True))
    no_join_score = _score(reference, no_join_text)
    joined_score = _score(reference, joined_text)

    settings = ocr_data.get("ocr_settings", {})
    model_file = settings.get("model_file")
    model_hash = settings.get("model_sha256")
    tessdata_dir = settings.get("tessdata_dir")
    if model_file and tessdata_dir:
        model_path = Path(tessdata_dir) / model_file
        if model_path.is_file():
            model_hash = _sha256(model_path)

    page = annotation["derived_png"]
    jp2 = annotation["original_jp2"]
    return {
        "evaluation_rules_version": "v1",
        "annotation_revision": annotation["annotation_revision"],
        "source": {
            "image_filename": page["filename"], "image_sha256": page["sha256"],
            "jp2_filename": jp2["filename"], "jp2_sha256": jp2["sha256"],
            "source_url": annotation["source_url"],
        },
        "region": {
            "region_id": region["region_id"], "region_type": region["region_type"],
            "coordinates": region["bbox_xyxy"], "split": region["split"],
            "language": region["language"], "reference_text": region["reference_text"],
        },
        "ocr": {
            "input_file": str(ocr_path), "mode": ocr_data.get("ocr_mode", "unknown"),
            "input_image": ocr_data.get("source_image"), "psm": settings.get("psm"),
            "oem": settings.get("oem"), "tessdata_dir": tessdata_dir,
            "language_combination": settings.get("tesseract_language"),
            "model_file": model_file, "model_sha256": model_hash,
            "coordinate_offset": ocr_data.get("coordinate_offset", {"x": 0, "y": 0}),
            "preprocessing": "none",
        },
        "inputs": {"reconstructed_ocr_text": raw_ocr, "normalized_reference": reference,
                   "no_join_hypothesis": no_join_text,
                   "line_end_hyphens_joined_hypothesis": joined_text},
        "results": {
            "no_join": no_join_score,
            "line_end_hyphens_joined": joined_score,
            "pooled": {
                "region_count": 1,
                "no_join": no_join_score,
                "line_end_hyphens_joined": joined_score,
            },
        },
        "software": {
            "python": platform.python_version(), "pytesseract": pytesseract.__version__,
            "pillow": PIL.__version__,
            "tesseract": _tesseract_version(settings.get("tesseract_executable", "tesseract")),
            **git_provenance(),
        },
    }


@app.command()
def evaluate(
    ocr_result: Path = typer.Argument(..., exists=True, dir_okay=False),
    annotation: Path = typer.Argument(..., exists=True, dir_okay=False),
    region_id: str = typer.Option(..., "--region-id", help="Region ID from the annotation JSON."),
    output: Path = typer.Option(Path("outputs/evaluation.json"), "--output", "-o"),
):
    """Score one OCR result against one annotated region."""
    try:
        ocr_data = json.loads(ocr_result.read_text(encoding="utf-8"))
        annotation_data = json.loads(annotation.read_text(encoding="utf-8"))
        result = evaluate_region(ocr_data, annotation_data, region_id, ocr_result)
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as error:
        raise typer.BadParameter(str(error)) from error

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(f"Saved evaluation result to {output}")


if __name__ == "__main__":
    app()
