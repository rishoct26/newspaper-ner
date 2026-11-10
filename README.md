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

The English NER baseline uses spaCy with `en_core_web_sm`. Install the model
in the active virtual environment after installing the project:

```powershell
python -m spacy download en_core_web_sm
```

## Run OCR

From an activated environment with Tesseract configured:

```powershell
newspaper-ner "scans\en_dev\en_cordele-dispatch_1926-11-09_p01.png" --language en --output "outputs\cordele-p01-ocr.json"
```

For command help:

```powershell
newspaper-ner --help
```

Run the English NER stage on a word-level OCR JSON file:

```powershell
newspaper-ner-entities "outputs\cordele-body-region-ocr.json" -o "outputs\cordele-body-ner.json"
```

Score named entities against a manually checked gold annotation:

```powershell
newspaper-ner-score "outputs\cordele-body-ner.json" `
  "data\annotations\en_cordele_body_ner_gold.json" `
  -o "outputs\cordele-body-ner-evaluation.json"
```

Pool several region-level NER evaluations by summing their exact-span counts:

```powershell
newspaper-ner-pool-entities `
  "outputs\cordele-body-ner-evaluation.json" `
  "outputs\az0346-houdini-ner-evaluation.json" `
  "outputs\az0346-header-ner-evaluation.json" `
  -o "outputs\pooled-ner-evaluation.json"
```

The spaCy baseline provides entity labels and spans but no calibrated
per-entity confidence score. The NER output therefore leaves
`ner_confidence` null; it reports OCR confidence separately for the words
forming each entity.

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
