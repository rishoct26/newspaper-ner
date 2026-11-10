# Newspaper OCR + NER Project — Progress Report

**Report date:** 2026-11-11  
**Current gate:** English OCR and NER development baselines  
**NER status:** English spaCy baseline implemented; evaluation remains small

## 1. Project goal

Build a local, repeatable pipeline for scanned English, Hindi, and later Odia
newspaper pages. The intended output will identify people (`PER`), organizations
(`ORG`), locations (`LOC`), and dates (`DATE`), with text, language, separate
OCR and NER confidence values, and page-pixel bounding boxes. The ML pipeline
will remain separate from any future web app.

The project now has English OCR, a spaCy NER baseline, and separate OCR and NER
evaluation commands. Available scans are historical U.S. newspapers; their
scores are development checks only and do not represent performance on current
Indian newspapers. Hindi OCR is supported in code but has not been evaluated.
Hindi NER and Odia support remain future work.

## 2. Repository layout

```text
newspaper-ner-work/
├── .gitignore
├── README.md
├── pyproject.toml
├── requirements.txt
├── data/
│   ├── en_dev_sources.csv
│   └── annotations/
│       ├── en_cordele_dispatch_1926-11-09_p01.json
│       ├── en_cordele_body_ner_gold.json
│       ├── az0346_houdini_ner_gold.json
│       └── az0346_header_ner_gold.json
├── docs/
│   ├── evaluation.md
│   └── progress_report.md
├── scripts/
│   ├── download_chronam.py
│   └── jp2_to_png.py
└── work/
    └── newspaper_ner/
        ├── __init__.py
        ├── cli.py
        ├── ocr.py
        ├── evaluation.py
        ├── aggregate.py
        ├── ner.py
        ├── ner_evaluation.py
        └── ner_aggregate.py
```

Local-only directories are `.venv/`, `scans/`, `models/`, and `outputs/`.
They are ignored by Git. `.gitignore` also excludes environment files, Python
caches, build artifacts, model formats, and `sources/`. Treat `sources/` as
read-only.

## 3. What each code file does

- **`work/newspaper_ner/ocr.py`** — Finds Tesseract using `TESSERACT_CMD` or
  `PATH`, checks the selected language model, and runs Tesseract through
  `pytesseract`. English maps to `eng`; Hindi maps to `hin`. OCR uses OEM 3 and
  accepts a PSM value (default 3). It writes word text, language, OCR
  confidence, Tesseract block/paragraph/line/word IDs, and word bounding boxes.
  Optional crop offsets shift each box into full-page pixel coordinates.
  Output records the input dimensions, page dimensions, OCR mode, settings,
  and trained-data SHA-256.
- **`work/newspaper_ner/cli.py`** — Provides the `newspaper-ner` OCR command,
  including `--language`, `--psm`, crop offsets, full-page dimensions, and an
  output JSON path.
- **`work/newspaper_ner/evaluation.py`** — Provides `newspaper-ner-evaluate`.
  It selects words whose box centers fall inside one annotated region, rebuilds
  lines from Tesseract IDs, applies the v1 cleanup and normalization rules, and
  reports CER/WER with and without line-end hyphen joining.
- **`work/newspaper_ner/aggregate.py`** — Provides
  `newspaper-ner-aggregate`, which pools saved region results separately for
  the two scoring variants and lists each region alongside the pooled scores.
- **`work/newspaper_ner/ner.py`** — Provides `newspaper-ner-entities`. It
  rebuilds text from OCR line IDs, runs spaCy, maps PERSON to PER and GPE/LOC
  to LOC, and maps entity spans back to OCR words and page boxes. The baseline
  leaves `ner_confidence` null because spaCy's standard `Doc.ents` output does
  not provide a calibrated score; it stores OCR confidence separately.
- **`work/newspaper_ner/ner_evaluation.py`** — Provides `newspaper-ner-score`
  for exact-span-and-label precision, recall, and F1 against manually checked
  gold annotations.
- **`work/newspaper_ner/ner_aggregate.py`** — Provides
  `newspaper-ner-pool-entities`, which pools NER counts across regions.
- **`scripts/download_chronam.py`** — Attempts to download a small varied
  Chronicling America development sample and write source metadata.
- **`scripts/jp2_to_png.py`** — Converts downloaded JP2 pages to PNG for OCR.

## 4. Evaluation rules and annotation

The OCR evaluation specification is in [`evaluation.md`](evaluation.md),
version `v1`. It defines region-level and page-level OCR modes, center-based box
selection, word reading order, OCR artifact cleanup, Unicode normalization,
hyphen and em-dash handling, case- and punctuation-sensitive scoring, and
pooled CER/WER. References are inline in the annotation JSON and represent
logical text. The two Cordele OCR regions are marked `dev`. The three existing
NER gold files were built against OCR text; under the revised English NER rules
they must be migrated to verified region reference text before adding new gold
annotations. The three regions are development data.

The annotation ties the English Cordele Dispatch issue dated 1926-11-09 to its
PNG and JP2 filenames, SHA-256 checksums, source URL, page dimensions, crop
coordinates, region type, reference text, and verification details. The
headline and article body are separate regions.

`data/en_dev_sources.csv` contains 17 rows for the 17 local JP2 filenames, with
title, issue date, page identifier, Library of Congress issue URL, SHA-256, and
split. Eight rows are `dev` (Cordele and Douglas) and nine are `test` (New
Britain Herald, Washington Daily News, Indianapolis Times, California Eagle).
Some `page` values preserve the source image sequence where the printed page
number has not been checked. The LOC downloader trial returned HTTP 403; the
pages were obtained manually from the Library of Congress. The local
`scans/en_dev/` folder has 17 JP2 filenames and 17 PNG files. Two JP2 filenames
are byte-identical copies of the Cordele page, so there are 16 unique JP2 files
by checksum. The 11-page visual review is a curated subset of this folder;
Douglas page 3 (`...0347.jp2`) is present locally. All 17 JP2 files have
manifest rows. Scans, crops, OCR outputs, and model files remain outside Git.

## 5. Environment and installed packages

The demonstrated environment is Windows PowerShell with Python **3.13.13** and
Tesseract **5.4.0.20240606**. Tesseract is a separate system installation; it
is not installed by `pip`. In a new PowerShell session, set its path if it is
not already on `PATH`:

```powershell
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

Tesseract language data are stored locally in the ignored
`models/tessdata/` directory: `eng.traineddata` and `hin.traineddata`.
The OCR module uses `TESSDATA_PREFIX` to avoid Windows quoting problems.

Direct Python project dependencies in `pyproject.toml` are:

- `typer==0.28.0`
- `pillow==13.0.0`
- `pytesseract==0.3.13`
- `spacy==3.8.18`

The installed English spaCy model is `en_core_web_sm==3.8.0`. Install it in a
fresh environment with `python -m spacy download en_core_web_sm`; the frozen
`requirements.txt` records the current model wheel reference.

`requirements.txt` is the current pinned environment snapshot. It also lists
the installed transitive packages: `annotated-doc==0.0.5`,
`colorama==0.4.6`, `markdown-it-py==4.2.0`, `mdurl==0.1.2`,
`packaging==26.3`, `Pygments==2.21.0`, `rich==15.0.0`, and
`shellingham==1.5.4`, plus the editable `newspaper-ner==0.1.0` install.

## 6. Commands used

Create and activate the environment, then install the project in editable mode:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Run OCR on a full page:

```powershell
newspaper-ner "scans\en_dev\en_cordele-dispatch_1926-11-09_p01.png" `
  --language en --psm 3 -o outputs\cordele-page-ocr-v1.json
```

Run OCR on a crop and map boxes back to full-page coordinates (this example is
the body region at x=210, y=2680 on a 5403 × 6991 page):

```powershell
newspaper-ner "outputs\cordele-body-region.png" `
  --language en --psm 6 --offset-x 210 --offset-y 2680 `
  --page-width 5403 --page-height 6991 `
  -o outputs\cordele-body-region-ocr.json
```

Evaluate one region and aggregate the headline and body results:

```powershell
newspaper-ner-evaluate "outputs\cordele-body-region-ocr.json" `
  "data\annotations\en_cordele_dispatch_1926-11-09_p01.json" `
  --region-id cordele-dispatch-1926-11-09-p01-article-body `
  -o outputs\cordele-body-region-evaluation.json

newspaper-ner-aggregate `
  "outputs\cordele-body-region-evaluation.json" `
  "outputs\cordele-headline-region-evaluation.json" `
  -o outputs\cordele-dev-pooled.json

newspaper-ner-entities "outputs\cordele-body-region-ocr.json" `
  -o outputs\cordele-body-ner.json

newspaper-ner-score "outputs\cordele-body-ner.json" `
  "data\annotations\en_cordele_body_ner_gold.json" `
  -o outputs\cordele-body-ner-evaluation.json

newspaper-ner-pool-entities `
  "outputs\cordele-body-ner-evaluation.json" `
  "outputs\az0346-houdini-ner-evaluation.json" `
  "outputs\az0346-header-ner-evaluation.json" `
  -o outputs\ner-dev-pooled.json
```

The current OCR, evaluation, and pooled-result JSON files are in ignored
`outputs/`; rerun the commands to regenerate them.

## 7. Development results so far

These are manual development checks from one historic page, not a representative
accuracy estimate.

| Region / mode | Variant | CER | WER | Edits / reference length |
|---|---|---:|---:|---|
| Article body, page mode | No joining | 28.9% | 56.7% | CER 107/370; WER 38/67 |
| Article body, page mode | Line-end hyphens joined | 27.8% | 52.2% | CER 103/370; WER 35/67 |
| Article body, region mode | No joining | 2.4% | 13.4% | CER 9/370; WER 9/67 |
| Article body, region mode | Line-end hyphens joined | 0.3% | 1.5% | CER 1/370; WER 1/67 |
| Headline, region mode | Both variants | 3.0% | 16.7% | CER 1/33; WER 1/6 |
| Pooled two regions | No joining | 2.5% | 13.7% | CER 10/403; WER 10/73 |
| Pooled two regions | Line-end hyphens joined | 0.5% | 2.7% | CER 2/403; WER 2/73 |

The page-mode result demonstrates the effect of newspaper layout on OCR. The
region-mode results are more useful for recognition quality because Tesseract
receives one region crop at a time. The body result’s remaining recognized
error is `hich` for `high`; the headline has one character error (`VISTT` for
`VISIT`). Joining printed line-break hyphens substantially lowers the body
error count. The OCR sample above is only two regions from the Cordele page.

NER was evaluated on three small development regions across two historical
American pages:

| NER region | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Cordele article body | 2 | 2 | 1 | 50.0% | 66.7% | 57.1% |
| Douglas Houdini opening | 3 | 0 | 1 | 100.0% | 75.0% | 85.7% |
| Douglas page header | 1 | 1 | 1 | 50.0% | 50.0% | 50.0% |
| Pooled three regions | 6 | 3 | 3 | 66.7% | 66.7% | 66.7% |

Pooled label F1: `PER` 66.7%, `ORG` 0%, `LOC` 100% (one mention), and `DATE`
80%. These results are development-only. The model mislabeled newspaper names
as `PER` and once predicted “the day” as `DATE`.

## 8. Git and verification status

The current branch is `codex/english-dev-data-expansion`. Evaluation provenance
and OCR tests are committed as `04943b6`; the manifest is committed as
`715dbba`; earlier history includes NER pooling commit `7ec0ce5`, OCR commit
`15c002b`, and English NER baseline commit `d92fd5d`. `main` has not yet been
advanced from the initial skeleton.

The OCR, NER, evaluation, and aggregation commands have been run manually on
the sample data. Word IDs, PSM/settings, crop offsets, individual CER/WER,
entity outputs, and pooled results were inspected in PowerShell. The JP2 to
PNG script has been run on the local pages. Four automated `unittest` checks
now cover line-end hyphen joining, em-dash joining at either edge of a line,
and crop-offset mapping. They pass with the project virtual environment's
Python. OCR and NER evaluation outputs now record the current Git commit and
whether the working tree is dirty; this code is not committed yet.

## 9. Current limitations and next gate

- The spaCy NER baseline is not fine-tuned and has only three small gold
  regions. `ner_confidence` remains null until a defensible method is chosen.
- The installed OCR models support English and Hindi only; Odia is deferred.
- There is no current Indian newspaper dataset yet. The present historical
  American sample cannot validate target-domain performance.
- The Chronicling America downloader received HTTP 403; the source manifest
  now tracks manually downloaded pages and their Library of Congress issue
  URLs.
- All current NER annotations are development-only. Test titles are now
  recorded in the manifest; do not run or inspect their OCR output until the
  pipeline is frozen.
- Evaluation currently runs for one region per command; the separate pooling
  command combines saved region evaluations. Dynamic Git commit-hash capture
  is implemented, but should be committed before producing final evaluation
  outputs.
- OCR confidence must not be interpreted as entity confidence or overall text
  accuracy.

## 10. Remaining gates and data-size planning

Roughly **six major gates** remain; the number of small coding and annotation
steps depends on the pages and languages available:

1. Annotate more English dev regions; source rows and title-level splits are
   now recorded.
2. Commit the evaluation provenance and OCR regression tests, then regenerate
   the development evaluation outputs so their hash identifies that code.
3. Improve OCR layout handling and compare it on additional dev pages.
4. Improve or fine-tune English NER, decide on an honest confidence method,
   and evaluate on untouched pages.
5. Evaluate Hindi OCR and build Hindi NER data/model support.
6. Add Odia later with its own manually checked gold test set, then consolidate
   the multilingual output and CLI. A web app remains a later project.

There is no fixed number of newspaper titles to train on: the model learns from
annotated text, while title diversity helps test generalization. A practical
pilot target is **20–30 annotated page regions from 3–5 titles**, split by
page/title into training, development, and test data. This is a planning
estimate, not a guaranteed minimum or a basis for broad accuracy claims. spaCy
guidance says training from scratch usually needs at least a few hundred
examples for both training and evaluation; this project is fine-tuning a
pretrained model, so that guidance is not a direct threshold. Historical OCR
NER work has used corpora of 100 scanned pages, illustrating that robust
historical evaluation can require much more data. [spaCy training guidance](https://spacy.io/usage/training),
[historical OCR NER study](https://arxiv.org/abs/2107.00927).

The 17 local pages are enough to continue the English workflow pilot, but all
are historical American newspapers. They cannot validate performance on
current Indian English, Hindi, or Odia newspapers.

## 11. Scan review and data-split decisions (2026-11-11)

A visual review of 11 selected JP2 pages found all usable for OCR. The review
ranked New Britain Herald, Washington Daily News, and the Douglas front page as
strong text pages; Cordele Nov. 9 and its Nov. 10 Social Activities column as
useful dev material; and the California Eagle and Indianapolis Times pages as
mixed but useful test material. Douglas page 3 and two Cordele ad-heavy pages
are primarily layout stress cases and should receive little or no NER gold
annotation. The review omitted Douglas page 3 from its 10-page prior list, but
that file exists as `...0347.jp2` in the local folder.

Proposed split: keep the already-used Cordele and Douglas issues in `dev`, and
hold out New Britain Herald, Washington Daily News, Indianapolis Times, and
California Eagle as `test`. Do not run or inspect OCR on held-out test pages
until the pipeline is frozen. The two Indiana-named page files ending in
`0139.jp2` and `0139 (1).jp2` are different pages: visual inspection identifies
the plain `0139` page as Douglas Daily Dispatch and `0139 (1)` as Indianapolis
Times. The user confirmed both were obtained from the Library of Congress.
Their SHA-256 values are `CF4156DA5E5FD6A2ED7C2EF1A833C5B6AE698684E96F337AC7D2A11DFAC047EF`
for plain `0139.jp2` and `E1E5C828C137FB95121E57436CC38C8D69C65176DEA1D97C49547AD4D39F470A`
for `0139 (1).jp2`. The manifest is committed as `715dbba`. The plain
`0139.jp2` row uses the Douglas Daily Dispatch LCCN `sn84020064` and the
Douglas issue URL for 1926-11-09, despite the Indiana-batch filename; the title
and date are from the masthead. The other file is Indianapolis Times and is in
the `test` split. The test split is recorded; test-page OCR remains untouched.
Some image sequence identifiers still need visual confirmation against
printed page numbers.

The current NER gate is to migrate the existing gold annotations to verified
reference text, finalize the revised annotation rules, and then annotate 8–10
additional manually checked dev regions. The existing three-region NER score
is too small for a meaningful quality claim. Automated OCR checks for line-end
joining, em-dash handling, and crop-offset mapping now pass. Evaluation outputs
record the code commit hash and working-tree state. A lenient NER score remains
to be implemented beside exact matching; keep the two results separate.

The recommended title split is based on visual inspection only. Existing
development OCR on Cordele/Douglas remains valid; held-out pages have not been
OCR-evaluated as part of this review. The Chronicling America HTTP 403 remains
unresolved; a later retry with a longer delay is optional while manual source
downloads continue.
