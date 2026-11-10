# Newspaper OCR + NER

A local Python command-line project for processing scanned newspaper pages.
The OCR stage uses Tesseract and returns recognized words, OCR confidence, and
page-pixel bounding boxes. Named-entity recognition is the next milestone; it
is not implemented yet.

## Current data and project limits

The available development scan is a 1926 *Cordele Dispatch* page from the
Library of Congress's Chronicling America collection. It is a historical U.S.
newspaper sample for exercising the OCR and layout pipeline. Results on it do
not represent current Indian newspapers. Hindi and Odia evaluation, and a
representative Indian newspaper set, remain future work.

The annotation and scoring rules for the current English development regions
are in [docs/evaluation.md](docs/evaluation.md). The verified region references
are stored inline in `data/annotations/` and marked `dev`.

## Setup (Windows PowerShell)

Use Python 3.13 and activate a virtual environment from the project root:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Install Tesseract OCR separately. In each PowerShell session, set its
executable path if Tesseract is not already on `PATH`:

```powershell
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

The Tesseract language data files belong in the ignored `models/tessdata/`
directory. The current CLI supports `en` (Tesseract `eng`) and `hi` (Tesseract
`hin`).

## Run OCR

From an activated environment with Tesseract configured:

```powershell
newspaper-ner "scans\en_dev\en_cordele-dispatch_1926-11-09_p01.png" --language en --output "outputs\cordele-p01-ocr.json"
```

For command help:

```powershell
newspaper-ner --help
```

## Local data and scripts

- Put source scans in `scans/`; generated OCR results and crops go in
  `outputs/`. Both are excluded from Git.
- Model weights and Tesseract language data go in `models/`, also excluded
  from Git.
- `scripts/jp2_to_png.py` converts downloaded JP2 pages to PNG.
- `scripts/download_chronam.py` is a small Chronicling America downloader. Its
  API trial currently returns HTTP 403 in this environment, so downloading a
  larger set has not been verified.

The `sources/` directory is treated as read-only. Do not commit scans, model
weights, secrets, caches, or large generated outputs.
