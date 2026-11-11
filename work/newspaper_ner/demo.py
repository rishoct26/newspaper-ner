"""One-command English page demo with saved-layout reuse and Rich output."""

from __future__ import annotations

import json
import os
import importlib.metadata
import subprocess
import sys
from pathlib import Path
from time import perf_counter

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from .layout_ocr import ocr_layout_regions
from .ner import MODEL_NAME, recognize_entities
from .overlay import draw_entities

app = typer.Typer(help="Run layout detection, OCR, English NER, and overlay in one command.")
console = Console(legacy_windows=True)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LAYOUT_MODEL = "PP-DocLayout_plus-L"


def _layout_source(data: dict) -> Path | None:
    value = data.get("input_path") or data.get("source_image")
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def _load_layout(path: Path, page: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("boxes"), list):
        raise ValueError(f"Layout JSON has no boxes list: {path}")
    source = _layout_source(data)
    if source is not None and source != page.resolve():
        raise ValueError(f"Layout JSON is for a different page: {path}")
    return data


def _find_saved_layout(page: Path, output_dir: Path) -> Path | None:
    candidates = [output_dir / "layout.json"]
    candidates.extend(sorted((PROJECT_ROOT / "outputs").glob("**/layout.json")))
    seen: set[Path] = set()
    for path in candidates:
        path = path.resolve()
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data.get("boxes"), list) and _layout_source(data) == page.resolve():
            return path
    return None


def _predict_layout(page: Path, layout_path: Path, python_path: Path) -> None:
    if not python_path.is_absolute():
        python_path = PROJECT_ROOT / python_path
    if not python_path.is_file():
        raise FileNotFoundError(f"Layout venv Python not found: {python_path}")
    layout_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    paddle_home = PROJECT_ROOT / "outputs" / "paddle-home"
    paddle_home.mkdir(parents=True, exist_ok=True)
    env["HOME"] = str(paddle_home)
    env["USERPROFILE"] = str(paddle_home)
    helper = PROJECT_ROOT / "scripts" / "predict_layout_paddle.py"
    completed = subprocess.run(
        [str(python_path), str(helper), str(page), str(layout_path)],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip().splitlines()
        message = detail[-1] if detail else "layout inference failed"
        raise RuntimeError(message)


def _stage(label: str, action):
    started = perf_counter()
    result = action()
    elapsed = perf_counter() - started
    return result, elapsed


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


@app.command()
def run(
    page: Path = typer.Argument(..., help="Newspaper page image to process."),
    output_dir: Path = typer.Option(Path("outputs/cordele-demo"), "--output-dir"),
    layout_json: Path | None = typer.Option(None, "--layout-json", help="Optional saved layout JSON."),
    layout_python: Path = typer.Option(
        Path(".venv/layout-check/Scripts/python.exe"),
        "--layout-python",
        help="Python executable in the separate PaddleOCR layout venv.",
    ),
    psm: int = typer.Option(6, "--psm", min=0, max=13),
):
    """Run the complete English layout-to-OCR-to-NER-to-overlay demo."""
    try:
        page = (PROJECT_ROOT / page).resolve() if not page.is_absolute() else page.resolve()
        if not page.is_file():
            raise FileNotFoundError(f"Page image not found: {page}")
        output_dir = (PROJECT_ROOT / output_dir).resolve() if not output_dir.is_absolute() else output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            ner_version = importlib.metadata.version(MODEL_NAME)
        except importlib.metadata.PackageNotFoundError:
            ner_version = "version unknown"
        console.print(Panel.fit(
            f"[bold]Page:[/] {page.name}\n"
            f"[bold]Layout:[/] {LAYOUT_MODEL} (separate PaddleOCR venv, CPU)\n"
            f"[bold]NER:[/] {MODEL_NAME} {ner_version}",
            title="Newspaper NER demo",
            box=box.ASCII,
        ))

        if layout_json is not None:
            selected_layout = (PROJECT_ROOT / layout_json).resolve() if not layout_json.is_absolute() else layout_json.resolve()
            layout_cached = True
        else:
            selected_layout = _find_saved_layout(page, output_dir)
            layout_cached = selected_layout is not None
            if selected_layout is None:
                selected_layout = output_dir / "layout.json"

        if layout_cached:
            def read_layout():
                return _load_layout(selected_layout, page)
            layout_data, seconds = _stage("layout", read_layout)
            status = f"cached JSON: {_display_path(selected_layout)}"
        else:
            def infer_layout():
                _predict_layout(page, selected_layout, layout_python)
                return _load_layout(selected_layout, page)
            layout_data, seconds = _stage("layout", infer_layout)
            status = f"inferred with {LAYOUT_MODEL}"
        console.print(f"[green]OK Layout[/] {status} [dim]({seconds:.2f}s)[/]")

        ocr_path = output_dir / "ocr.json"
        ner_path = output_dir / "ner.json"
        overlay_path = output_dir / "entities.png"

        def do_ocr():
            result = ocr_layout_regions(page, selected_layout, "en", psm, ocr_path)
            ocr_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return result
        ocr_result, seconds = _stage("OCR", do_ocr)
        console.print(f"[green]OK OCR[/] [dim]({seconds:.2f}s)[/]")

        def do_ner():
            result = recognize_entities(ocr_result, ocr_path)
            ner_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            return result
        ner_result, seconds = _stage("NER", do_ner)
        console.print(f"[green]OK NER[/] [dim]({seconds:.2f}s)[/]")

        def do_overlay():
            return draw_entities(page, ner_path, overlay_path)
        overlay_count, seconds = _stage("overlay", do_overlay)
        console.print(f"[green]OK Overlay[/] [dim]({seconds:.2f}s)[/]")

        words = ocr_result.get("words", [])
        confidences = [float(word["ocr_confidence"]) for word in words if word.get("ocr_confidence") is not None]
        mean_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        counts = {label: 0 for label in ("PER", "ORG", "LOC", "DATE")}
        for entity in ner_result.get("entities", []):
            if entity.get("label") in counts:
                counts[entity["label"]] += 1

        summary = Table(title="Run summary", show_header=True, header_style="bold cyan", box=box.ASCII)
        summary.add_column("Measure")
        summary.add_column("Value", justify="right")
        summary.add_row("Layout regions", str(len(ocr_result.get("layout_regions", []))))
        summary.add_row("OCR words", str(len(words)))
        summary.add_row("Mean OCR confidence", f"{mean_confidence:.2f}")
        summary.add_row("Entities", str(len(ner_result.get("entities", []))))
        console.print(summary)

        labels = Table(title="Entities by label", show_header=True, header_style="bold cyan", box=box.ASCII)
        labels.add_column("Label")
        labels.add_column("Count", justify="right")
        for label, count in counts.items():
            labels.add_row(label, str(count))
        console.print(labels)

        top = Table(title="Top 10 entities (highest OCR confidence)", show_header=True, header_style="bold cyan", box=box.ASCII)
        top.add_column("Label")
        top.add_column("Entity text")
        top.add_column("OCR conf.", justify="right")
        ordered = sorted(ner_result.get("entities", []), key=lambda item: float(item.get("ocr_confidence") or 0), reverse=True)
        for entity in ordered[:10]:
            text = " ".join(str(entity.get("text", "")).split())
            if len(text) > 38:
                text = text[:35] + "..."
            top.add_row(str(entity.get("label", "")), text, f"{float(entity.get('ocr_confidence') or 0):.1f}")
        console.print(top)

        paths = Table(title="Output files", show_header=True, header_style="bold cyan", box=box.ASCII)
        paths.add_column("Artifact")
        paths.add_column("Path")
        paths.add_row("Layout JSON", _display_path(selected_layout))
        paths.add_row("OCR JSON", _display_path(ocr_path))
        paths.add_row("NER JSON", _display_path(ner_path))
        paths.add_row("Entity overlay", _display_path(overlay_path))
        console.print(paths)
        console.print(f"[dim]Overlay boxes drawn: {overlay_count}[/]")
    except Exception as error:
        message = " ".join(str(error).split())
        if "Tesseract was not found" in message:
            message = "Tesseract not found; set TESSERACT_CMD to its executable path."
        if len(message) > 220:
            message = message[:217] + "..."
        console.print(f"[bold red]Error:[/] {message}")
        raise typer.Exit(code=1) from None


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")
    app()
