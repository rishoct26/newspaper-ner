# Named Entity Recognition from Scanned Newspaper Pages

## Experiential Learning Group Assignment - Project Report

**Course topic:** Language Processing Using Machine Learning and LLMs for Audio, Image, Text and Other Applications  
**Project task:** Named Entity Recognition from Image Documents  
**Project repository:** https://github.com/rishoct26/newspaper-ner  
**Report date:** 12 November 2026  
**Implementation platform:** Windows 11, Python 3.13.13

### Group details - complete before submission

| Member | Name | Roll number | Contribution |
| --- | --- | --- | --- |
| 1 | [Enter name] | [Enter roll number] | [Describe verified contribution] |
| 2 | [Enter name] | [Enter roll number] | [Describe verified contribution] |
| 3 (if applicable) | [Enter name or remove row] | [Enter roll number] | [Describe verified contribution] |
| 4 (if applicable) | [Enter name or remove row] | [Enter roll number] | [Describe verified contribution] |

> The course requires a group of two to four students. Names, roll numbers, and individual contributions were not present in the project materials available for this report, so these fields are intentionally left for the group to complete.

<!-- pagebreak -->

## Table of contents

- Executive summary
- Problem statement, objectives, and output labels
- Methodology and processing pipeline
- Models and software
- Implementation and repository organization
- Data source, provenance, and rights
- Results and sample outputs
- Setup and demonstration
- Limitations, conclusion, future scope, and references

<!-- pagebreak -->

## Executive summary

This project builds a local command-line prototype that reads a scanned newspaper page, detects page layout regions, recognizes printed text, identifies named entities, and maps entity spans back to page-pixel bounding boxes. The English pipeline currently uses PaddleOCR layout detection, Tesseract OCR, and spaCy NER. It produces OCR and NER JSON plus an image overlay that highlights detected people, organizations, locations, and dates.

The implemented demo was run on one development page: *The Cordele Dispatch*, 9 November 1926. The saved layout prediction contained 120 layout regions. Region OCR returned 2,888 words with a mean word confidence of 89.80. The English large spaCy model returned 314 entity predictions on the complete page: 57 PER, 42 ORG, 122 LOC, and 93 DATE. These are output counts, not an accuracy score.

Evaluation on the separate English development annotation set used 24 regions and 148 gold entity mentions. With exact entity-text and label matching and no post-processing rule, `en_core_web_lg` scored 74.2% F1 on verified reference text and 58.0% F1 on reconstructed OCR text. The comparison uses the same regions and model for both inputs. This difference is consistent with OCR and layout errors affecting downstream NER, but it is not a controlled causal estimate. The development set is small and historically narrow; it does not establish performance on modern Indian newspapers.

## 1. Problem statement and motivation

Newspaper pages are images with dense columns, headlines, rules, photographs, advertisements, and varying print quality. A named entity recognizer cannot reliably identify entities directly from the pixels. The page must first be segmented into useful text regions, then converted into text, then processed by an NLP model. To make the results useful for review, recognized entities must also be linked back to their position on the page.

The assignment task is to identify names, organizations, dates, and locations from image documents using OCR plus NER. The project implements this as a modular pipeline rather than coupling the ML logic to a future web interface. The current engineering data consists of historical US newspaper pages; it is used to build and inspect the prototype, not as evidence of performance on present-day Indian newspapers.

## 2. Objectives and expected output

The current English prototype aims to:

1. Accept a scanned newspaper page image.
2. Detect page elements and text-bearing regions with a document-layout model.
3. Run OCR on each selected region and preserve word text, OCR confidence, Tesseract line identifiers, and page coordinates.
4. Run an English NER model and map each entity span to its contributing OCR words and page bounding box.
5. Save structured OCR and NER JSON and draw colored entity boxes on the source page.
6. Evaluate OCR with CER/WER and NER with precision, recall, and F1 on manually checked development data.

The output schema separates `ocr_confidence` from `ner_confidence`. The current spaCy `Doc.ents` pipeline does not provide a calibrated per-entity probability, so `ner_confidence` is explicitly `null`; OCR word confidence is retained separately and aggregated for each mapped entity.

### Target entity classes

| Output label | Meaning | spaCy labels mapped in the English baseline |
| --- | --- | --- |
| PER | Person | PERSON |
| ORG | Organization | ORG |
| LOC | Location | GPE, LOC |
| DATE | Date or time expression | DATE |

Labels not listed in the mapping are not emitted by the current baseline. The mapping is intentionally simple and may need newspaper-specific rules after a larger, audited annotation set exists.

## 3. Methodology and processing pipeline

The page-to-output flow is:

```text
Scanned page image
        |
        v
PaddleOCR PP-DocLayout_plus-L layout detection (separate Python environment)
        |  layout JSON: class labels, scores, page-pixel boxes
        v
Tesseract region OCR (English; PSM 6 for the demo)
        |  OCR JSON: words, confidence, line IDs, page-pixel boxes
        v
spaCy en_core_web_lg NER
        |  NER JSON: entity label, text, OCR confidence, page-pixel box
        v
Colored entity overlay PNG
```

The diagram is also available as [an SVG](newspaper_ner_pipeline.svg).

### Stage 1: layout detection

The demo looks for a layout JSON whose recorded input path matches the selected source image. If it finds one, it reuses the saved result and reports that in the terminal. If none is found, the demo starts a helper process from the separate `.venv/layout-check` environment. The helper loads PaddleOCR `PP-DocLayout_plus-L` on CPU with MKLDNN disabled and writes layout JSON. Separating Paddle dependencies from the main application environment avoids mixing the heavier layout stack with the OCR/NER CLI.

The layout output stores each detected element's class ID, label, confidence score, and `[xmin, ymin, xmax, ymax]` coordinates. The current OCR stage selects text-bearing classes, orders boxes by top then left coordinate, crops them from the original page, and sends each crop to Tesseract. This is a practical baseline; it is not a complete newspaper article reconstruction algorithm.

### Stage 2: OCR

Tesseract 5.4.0.20240606 is called through `pytesseract` 0.3.13. English uses the `eng` trained-data file. The OCR stage uses OEM 3 and PSM 6 for the full-page layout demo. Each retained word record contains text, language, OCR confidence, `block_num`, `par_num`, `line_num`, and `word_num`. The region offset is added to each crop-relative box so all output boxes use source-page pixels.

The demo page is 5,403 by 6,991 pixels. The current output records the trained-data filename and SHA-256. It does not resize, threshold, or deskew the demo page before Tesseract OCR.

### Stage 3: NER

The English entity recognizer is spaCy 3.8.18 with `en_core_web_lg` 3.8.0. Text is rebuilt from OCR words in Tesseract block, paragraph, line, and word order. spaCy character spans are aligned to OCR words; the entity bounding box is the union of those word boxes. The output includes the original spaCy label and the project's normalized label.

The `en_core_web_lg` model was selected after a same-data comparison against `en_core_web_sm` on development regions. The model choice was based only on development data. No custom NER fine-tuning was done.

### Stage 4: overlay and saved artifacts

The overlay draws entity boxes over the original page image. PER is red, ORG blue, LOC green, and DATE orange. The complete-page overlay is helpful for showing page coverage, while the report also contains tighter crops where labels can be read. JSON files are UTF-8 and preserve the recognized text and page-pixel coordinate convention.

## 4. Models, software, and environment

| Component | Version/configuration | Purpose |
| --- | --- | --- |
| Python | 3.13.13 | Main CLI and separate layout environment |
| PaddlePaddle | 3.3.1 | PaddleOCR inference backend |
| PaddleOCR | 3.7.0 | `PP-DocLayout_plus-L` page-layout detection |
| Tesseract OCR | 5.4.0.20240606 | English OCR engine |
| English OCR data | `eng.traineddata`, SHA-256 `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2` | Tesseract English recognition model |
| pytesseract | 0.3.13 | Python wrapper for Tesseract |
| Pillow | 13.0.0 | Image loading, region cropping, and overlay drawing |
| spaCy | 3.8.18 | English NLP pipeline |
| `en_core_web_lg` | 3.8.0 | English named entity recognition |
| Typer | 0.28.0 | Command-line interface |
| Rich | 15.0.0 | Readable demo terminal output |

The main Python packages and spaCy model are pinned in `pyproject.toml` and the generated requirements snapshot. PaddleOCR runs from its own environment and uses its downloaded model cache outside Git. Tesseract is a separate Windows installation and is located through `TESSERACT_CMD` or `PATH`.

## 5. Implementation and repository organization

```text
newspaper-ner/
|-- README.md                         Project overview and Windows run guide
|-- pyproject.toml                    Package metadata and CLI entry points
|-- requirements.txt                  Main environment dependency snapshot
|-- work/newspaper_ner/
|   |-- cli.py                        Tesseract OCR command
|   |-- ocr.py                        OCR wrapper, boxes, IDs, confidence, offsets
|   |-- layout_ocr.py                 OCR each text-bearing layout crop
|   |-- demo.py                       Single-command end-to-end English demo
|   |-- ner.py                        spaCy NER and word-box alignment
|   |-- overlay.py                    Entity overlay image generation
|   |-- evaluation.py                 OCR region CER/WER evaluation
|   |-- aggregate.py                  Pooled OCR region evaluation
|   |-- ner_evaluation.py              Exact NER scoring
|   |-- ner_aggregate.py               Pooled NER evaluation
|   `-- comparison.py                 Clean-text/OCR-text model comparison
|-- scripts/
|   |-- predict_layout_paddle.py      Helper called inside layout venv
|   |-- jp2_to_png.py                 JP2 conversion utility
|   `-- download_chronam.py            Chronicling America download attempt
|-- data/annotations/                 Small, manually checked dev gold data
|-- docs/
|   |-- evaluation.md                 OCR evaluation rules v1
|   |-- ner_annotation.md             NER annotation rules
|   |-- newspaper_ner_pipeline.svg    Editable source vector diagram
|   `-- project_report.md              Editable report source
|-- tests/                            OCR/evaluation unit tests
|-- scans/                            Local input scans; excluded from Git
|-- models/                           Local model data; excluded from Git
|-- outputs/                          Generated results and caches; excluded
`-- samples/                          Local Cordele demo samples; rights review pending
```

### Main commands

The project exposes command-line entry points for OCR, OCR evaluation and aggregation, NER, NER scoring and aggregation, clean/OCR model comparison, overlay generation, and the full demo. The demo command is the shortest way to show the image-to-entity result. The full installation and run instructions are in the README's **How to run** section.

The pipeline is locally reproducible from the recorded versions and source. Model weights, scans, generated caches, and large outputs are not tracked. The source tree's `sources/` content is treated as read-only.

## 6. Data source, provenance, and rights handling

Development scans are historical US newspaper pages from the Library of Congress Chronicling America collection. The demo page is the 9 November 1926 front page of *The Cordele Dispatch*. Its source record is `https://www.loc.gov/item/2022239700/1926-11-09/ed-1/`. The local manifest `data/en_dev_sources.csv` records page metadata, checksums, development split, and a rights-status field.

The scan master and generated full-resolution image are local-only. The manifest currently records redistributability as `unknown`. Accordingly, scan-derived sample images and output figures are prepared locally but are not assumed to be cleared for public redistribution. The `samples/` directory is not staged by this report task. The group should review the item rights information and decide what may be included in the public repository before adding those files to GitHub.

This data does not represent current Indian English, Hindi, or Odia newspapers. No Hindi or Odia NER result is claimed. The repository has English support and some Hindi OCR plumbing, but multilingual evaluation and current Indian newspaper validation remain future work.

## 7. Results and sample outputs

### 7.1 OCR evaluation on one Cordele article body region

The region reference contains 370 normalized characters and 67 words. The saved region evaluation reports two variants:

| OCR variant | CER edits / reference length | CER | WER edits / reference length | WER |
| --- | ---: | ---: | ---: | ---: |
| No line-end hyphen joining | 9 / 370 | 2.43% | 9 / 67 | 13.43% |
| Line-end hyphens joined | 1 / 370 | 0.27% | 1 / 67 | 1.49% |

These are region-level sanity-check results from one short development crop, not a general OCR accuracy estimate. The joined variant resolves line-break hyphenation and leaves one OCR character error (`hich` for `high`).

An earlier page-mode run on this same annotated body region produced 107 character edits over 370 reference characters (28.92% CER) and 38 word edits over 67 reference words (56.72% WER) with no joining. The hand-cropped region-mode run produced 9/370 CER edits (2.43%) and 9/67 WER edits (13.43%) on the same no-join variant. This comparison shows that layout handling strongly affects this example; it is not a multi-page controlled average.

![Cordele article crop, OCR text, CER and WER](../outputs/figures/cordele-article-ocr-evaluation.png)

### 7.2 NER model comparison on English development regions

The development-only comparison used the same 24 regions, same 148 gold mentions, exact text-and-label matching, no post-processing rules, spaCy 3.8.18, and 1,000 region-bootstrap samples with seed `20261111`.

| Model | Input to NER | TP / FP / FN | Precision | Recall | Exact F1 | Region-bootstrap 95% interval |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `en_core_web_sm` 3.8.0 | Verified reference text | 105 / 49 / 43 | 68.2% | 70.9% | 69.5% | 60.6-79.9% |
| `en_core_web_lg` 3.8.0 | Verified reference text | 115 / 47 / 33 | 71.0% | 77.7% | 74.2% | 63.7-84.3% |
| `en_core_web_sm` 3.8.0 | OCR text | 84 / 76 / 64 | 52.5% | 56.8% | 54.5% | 47.8-61.4% |
| `en_core_web_lg` 3.8.0 | OCR text | 92 / 77 / 56 | 54.4% | 62.2% | 58.0% | 49.7-65.8% |

On this development sample, `en_core_web_lg` is 4.7 percentage points higher in exact F1 on clean text and 3.5 points higher on OCR text than `en_core_web_sm`. The bootstrap intervals overlap substantially, so this comparison does not establish a reliable general improvement. OCR text has lower exact F1 than clean reference text for both models. Because OCR can alter, join, or omit entity text, this paired difference is informative about the pipeline but is not a controlled causal estimate of OCR damage alone.

For `en_core_web_lg` on OCR text without rules, the per-label F1 values were PER 54.9%, ORG 37.0%, LOC 77.8%, and DATE 52.3%. The gold set contains only nine ORG mentions, so the ORG result is particularly uncertain. Exact matching also counts an OCR-altered surface form as an unmatched prediction and unmatched gold mention.

A separate development-only rule check removed the generic DATE phrase `the day` from both prediction sets. For `en_core_web_lg`, exact F1 changed from 74.2% to 74.9% on clean text and from 58.0% to 58.6% on OCR text. The current full-page demo displays unfiltered model output; this small rule check is reported separately and is not silently mixed into the demo counts.

### 7.3 Full-page Cordele demo run

The successful end-to-end command reused the saved layout prediction at `outputs/layout-only/layout.json`. The terminal reported layout 0.00 seconds, OCR 40.67 seconds, NER 3.18 seconds, and overlay 4.41 seconds for that run. OCR produced 120 layout regions, 2,888 words, and mean OCR confidence 89.80. NER produced 314 predictions: 57 PER, 42 ORG, 122 LOC, and 93 DATE. These counts describe this one page and are not precision/recall/F1.

The final output files are `outputs/cordele-submission-demo/ocr.json`, `outputs/cordele-submission-demo/ner.json`, and `outputs/cordele-submission-demo/entities.png`. The three report figures are generated by `scripts/build_cordele_submission_assets.py`.

![PaddleOCR layout boxes on the Cordele page](../outputs/figures/cordele-layout-detection.png)

![NER boxes on three Cordele regions](../outputs/figures/cordele-ner-regions.png)

### 7.4 Reading the output

An OCR word record includes a recognized token, language, OCR confidence, Tesseract line identifiers, and page-pixel bounding box. An NER entity record includes text, normalized label, source spaCy label, language, nullable NER confidence, mean OCR confidence for mapped words, page-pixel box, and OCR-word indices. The overlay uses the same page coordinates. The sample folder contains a downscaled image and correspondingly scaled JSON boxes, plus the overlay and report figures; it must not be confused with the full-resolution evaluation input.

## 8. Usability: setup and demonstration

The demo is a local command-line application run from Windows PowerShell. It needs Windows 11, Python 3.13, Tesseract OCR 5.4, an internet connection for first-time package/model downloads, and the project source. Tesseract is a separate Windows program; the tested executable path is shown below and should be changed if installed elsewhere.

### 4.2 Instructions for Running the Application

Clone the source code and enter the repository:

```powershell
git clone https://github.com/rishoct26/newspaper-ner.git
cd newspaper-ner
```

The newspaper page is not included in Git. Download the Cordele Dispatch, 9 November 1926 page image from its [Library of Congress item record](https://www.loc.gov/item/2022239700/1926-11-09/ed-1/), and save the JP2 file as `scans\en_dev\en_cordele-dispatch_1926-11-09_p01.jp2`. Create the folder if it does not exist. Review the source item's rights; the source link is provided for provenance and is not a redistribution license.

Create and activate the main Python environment, install the project dependencies, and download the English Tesseract model file used by this project:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
New-Item -ItemType Directory -Force models\tessdata | Out-Null
Invoke-WebRequest "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/4.1.0/eng.traineddata" -OutFile "models\tessdata\eng.traineddata"
python scripts\jp2_to_png.py scans\en_dev
```

The package installation downloads the pinned spaCy model. The Tesseract English model file is stored locally and is not tracked by Git. The JP2 conversion script creates the PNG used in the demo.

Create the separate PaddleOCR environment once if it is not already present:

```powershell
py -3.13 -m venv .venv\layout-check
.\.venv\layout-check\Scripts\python.exe -m ensurepip --upgrade
.\.venv\layout-check\Scripts\python.exe -m pip install paddlepaddle==3.3.1 paddleocr==3.7.0
```

Run the one-command Cordele demonstration from the repository root:

```powershell
python -m newspaper_ner.demo "scans\en_dev\en_cordele-dispatch_1926-11-09_p01.png" --output-dir "outputs\cordele-submission-demo"
```

To open generated files from PowerShell:

```powershell
code outputs\cordele-submission-demo\entities.png
code outputs\cordele-submission-demo\ocr.json
code outputs\cordele-submission-demo\ner.json
```

Layout inference downloads or uses PaddleOCR model weights in its local cache. A fresh clone does not contain the generated layout JSON, so the first demo run performs layout inference; later runs can reuse a matching saved layout file. Generated scans, model weights, caches, and outputs are deliberately kept out of the Git source tree.

## 9. Limitations and risks

1. **Domain mismatch:** the scanned development pages are historical US newspapers. Current Indian English, Hindi, and Odia pages have not been validated.
2. **Small gold sample:** 24 development regions and 148 mentions support early error analysis, not a broad deployment claim. There are only nine ORG mentions.
3. **OCR and layout errors:** columns, multi-column headlines, photographs, ads, and poor scans can cause missed text, overlaps, incorrect ordering, and OCR errors.
4. **No calibrated NER confidence:** `ner_confidence` is null. OCR confidence must not be presented as model confidence.
5. **Label ambiguity:** newspaper mastheads, titles, AP credits, vague date phrases, all-caps headings, and OCR-corrupted names can be misclassified. The reported `en_core_web_lg` remains a pretrained baseline, not a fine-tuned newspaper model.
6. **Coordinate limitations:** boxes are page-pixel axis-aligned rectangles; they do not describe rotated or polygonal text shapes.
7. **Rights and publication:** source manifest rows currently mark redistribution as unknown. The group must review source rights before adding scan-derived sample assets to a public repository.
8. **Not a web application:** the current deliverable is a local command-line prototype. A web upload interface is outside the present implementation.

## 10. Conclusion and future scope

The project demonstrates a complete English image-to-entity workflow on a real newspaper page: layout detection, region OCR, spaCy NER, page-coordinate mapping, JSON output, and a visual entity overlay. The Cordele development OCR experiment also demonstrates why region/layout handling matters: the same short body region scores much better after a suitable crop than in the early whole-page run. Development NER results are stronger on verified reference text than OCR text, which identifies OCR and text alignment as important pipeline limitations.

The next technical priorities are to package the demo cleanly, review the generated samples and publication rights, improve layout and OCR quality on varied development pages, and expand manually checked NER regions where the data can be shared. Before claiming generalization, prepare new, image-only references for a clearly separated test set, freeze the rules and code, and run that set once. Hindi OCR/NER and Odia data collection, annotation, OCR, and evaluation should be separate later milestones. Current Indian newspaper scans are required before making claims about those languages or publication environments. Fine-tuning should wait until a substantially larger and more varied annotation set exists.

## 11. Repository and contribution details

GitHub repository: https://github.com/rishoct26/newspaper-ner

The repository contains the Python package, command-line tools, documentation, evaluation rules, source scripts, and development annotation files. Local image scans, model weights, secrets, caches, and generated outputs are excluded from Git. The sample assets prepared for this report remain local pending the group's rights decision. The README links to setup instructions and the pipeline diagram.

### Contribution record - complete before submission

| Member | Work completed | Evidence to verify |
| --- | --- | --- |
| [Member 1] | [Fill in actual work] | [Commits, files, presentation segment] |
| [Member 2] | [Fill in actual work] | [Commits, files, presentation segment] |
| [Member 3, if applicable] | [Fill in actual work] | [Commits, files, presentation segment] |
| [Member 4, if applicable] | [Fill in actual work] | [Commits, files, presentation segment] |

The course submission also expects a recorded presentation/demo. It is not included in this report because no recording or approved video link was provided. The group must add an accessible recording link to the README before final submission.

## References

1. Library of Congress, [*The Cordele Dispatch*, 9 November 1926, item record](https://www.loc.gov/item/2022239700/1926-11-09/ed-1/).
2. Library of Congress, [Chronicling America collection overview](https://www.loc.gov/collections/chronicling-america/about-this-collection/).
3. Library of Congress, [Chronicling America datasets and bulk OCR](https://www.loc.gov/collections/chronicling-america/datasets/).
4. [Tesseract OCR 5.x User Manual](https://tesseract-ocr.github.io/tessdoc/).
5. [PaddleOCR 3.x layout detection documentation](https://www.paddleocr.ai/main/en/version3.x/module_usage/layout_detection.html).
6. spaCy, [English model documentation (`en_core_web_lg`)](https://spacy.io/models/en#en_core_web_lg).
7. spaCy, [trained pipeline usage documentation](https://spacy.io/usage/models).
8. [Python 3.13 documentation](https://docs.python.org/3.13/).
9. [Pillow documentation](https://pillow.readthedocs.io/).
10. [Project source repository](https://github.com/rishoct26/newspaper-ner).

## Appendix A: local sample artifacts prepared

The local `samples/` folder contains a downscaled Cordele page, scaled-coordinate OCR and NER JSON, an overlay aligned to the downscaled page, and the three report figures. These files have not been staged or committed because the source manifest still marks redistribution as `unknown`.

| Local sample file | Size |
| --- | ---: |
| `cordele-page.png` | 4,443,152 bytes |
| `cordele-ocr.json` | 965,855 bytes |
| `cordele-ner.json` | 154,013 bytes |
| `cordele-overlay.png` | 4,192,511 bytes |
| `cordele-layout-detection.png` | 4,158,790 bytes |
| `cordele-article-ocr-evaluation.png` | 455,717 bytes |
| `cordele-ner-regions.png` | 1,521,486 bytes |
| **Total** | **15,891,524 bytes (about 15.9 MB)** |

Recheck sizes from PowerShell with:

```powershell
Get-ChildItem samples -File | Select-Object Name, Length
```
