# OCR evaluation rules — v1

Rule version: `v1`. Until the first test-set evaluation, v1 may be edited using
development data. Before evaluating the test set, commit and tag the frozen
specification and evaluator (for example, `eval-rules-v1`). After test-set
results have been viewed, any rule change requires a v2 specification and a
complete rerun. Never revise rules to improve a test-set score.

Every result must record `evaluation_rules_version: "v1"` while these rules
are in force.

## Scope, regions, and references

Calculate character error rate (CER) and word error rate (WER) for each
annotated region, comparing OCR text with the verified reference for that exact
region. A region crop must contain only the text represented by its reference,
and the reference must transcribe all text in the crop. Keep crop edges off
neighboring articles, gutters, ornaments, and separator rules. Do not remove
OCR garbage with letters or digits using an extra cleanup rule; exclude it by
making the crop match the reference. Annotate a headline and article body as
separate regions.

Store each region's reference inline in the annotation JSON as
`reference_text`; do not keep a separate reference text file. Store logical
text: resolve printed line-break hyphenation, preserve real compound-word
hyphens, and separate paragraphs with a blank line. Do not store line-break
hyphens in a reference. A physical line break adjacent to an em dash is not a
space: transcribe `ducks—yesterday`, not `ducks —yesterday`.

Never score a whole-page OCR result against a smaller region's reference.
Report each region's edit counts, reference lengths, and rates, plus pooled
results across regions. For each scoring variant, pooled CER is the sum of
character edits divided by the sum of reference characters; pooled WER is the
sum of word edits divided by the sum of reference words. Include the region
count and list per-region results beside the pooled results.

## OCR modes

Record the mode used for every result, and never combine results from the two
modes into one score:

- **Region mode (v1 primary):** crop the source page to the annotated region
  and run OCR on that crop. Record all OCR settings, including page-segmentation
  mode (PSM). OCR word boxes are relative to the crop. Add the crop's page
  `left` and `top` offsets to each word's `x` and `y` before region selection or
  reporting page coordinates.
- **Page mode:** run OCR once on the full page, then select words for each
  annotated region. This measures recognition together with page-layout
  handling before a column splitter.

Select a word for a region only when the center of its bounding box falls inside
the region's half-open page-pixel box: `left <= center_x < right` and
`top <= center_y < bottom`. For region mode, first translate the crop-relative
box to page coordinates using the crop offset, then apply the same center rule.

Preprocessing in v1 is none: do not resize, pad, deskew, threshold, or alter a
crop before OCR. If a later version preprocesses an image, record the operation
and parameters. For padding, subtract the padding offset when mapping boxes
back to page coordinates.

## OCR text input and reading order

For either mode, build region text from the OCR JSON's Tesseract word records.
The records must retain `block_num`, `par_num`, `line_num`, and `word_num`.
Group words by `(block_num, par_num, line_num)`, sort groups by that tuple, and
sort words within each group by `word_num`. Preserve physical line boundaries
until normalization is complete.

## OCR artifact cleanup

Apply this cleanup to reconstructed OCR text only, before metric normalization:

1. Remove vertical column-rule artifacts (`|`).
2. Strip leading and trailing whitespace from each physical line.
3. Drop blank lines and lines containing neither a Unicode character in
   category `L*` nor one in category `Nd`. Numeric-only lines are content and
   must be retained.

For line handling, “the next line” means the next line that survives these
steps; blank and dropped lines do not count. Do not remove other OCR text based
on confidence or whether it appears to be garbage. Keep this cleanup fixed as
part of the v1 pipeline.

## Metric normalization

Apply the following steps in order. NFC, dash, quote, and whitespace
normalization apply to both the verified logical reference and cleaned OCR
text. Preserve OCR physical line boundaries until the line-edge decisions are
complete. The logical reference is never line-end hyphen joined.

1. Normalize both texts to Unicode NFC.
2. In both OCR scoring variants, remove a physical line break directly before
   or after an em dash U+2014 without inserting a space; retain the em dash.
   This also joins an em dash to a following parenthetical such as `(AP)`.
   Accept the limitation that a deliberately spaced em dash at a line edge is
   joined.
3. For the **line-end hyphens joined** variant only, process OCR physical lines
   and join a line ending when it ends with U+002D (`-`), U+2010 (`‐`), U+2011
   (`‑`), or U+00AD (soft hyphen), and the next surviving line begins with a
   character in Unicode category `Ll`. Remove that line-ending hyphen and line
   break. This baseline rule can also join a real compound word split at a
   hyphen, such as `well-` / `known`; accept and report this limitation.
4. Normalize remaining Unicode dash variants to ASCII hyphen-minus U+002D
   (`-`). The line-end hyphen check happens first, so an em dash is never
   treated as a line-end hyphen.
5. Map curly single quotes/apostrophes U+2018 and U+2019 to ASCII apostrophe
   (`'`), and curly double quotes U+201C and U+201D to ASCII quotation mark
   (`"`).
6. Preserve letter case; scoring is case-sensitive.
7. Collapse every run of whitespace, including remaining line breaks, to one
   ASCII space, then trim leading and trailing whitespace.
8. Keep punctuation in CER and WER comparisons. WER treats punctuation as part
   of its whitespace-separated token (for example, `ducks` and `ducks,` differ).
   This is intentionally strict and is not directly comparable with results
   that normalize case or punctuation differently.

Report two variants, each with CER and WER:

1. **No joining:** preserve OCR line-end hyphens, apply the em-dash line-break
   rule, then apply the remaining normalization steps. Compare against the
   logical reference.
2. **Line-end hyphens joined:** apply the em-dash rule and the OCR hyphen
   joining rule, then the remaining normalization steps. Compare against the
   same logical reference.

## Metric definitions

- **CER** = character-level Levenshtein edit distance divided by the number of
  characters in the normalized reference.
- **WER** = word-level Levenshtein edit distance divided by the number of
  whitespace-separated words in the normalized reference.

For each region and pooled score, report edit count, reference length, and the
rate. Rates may exceed 100% when insertions exceed the reference length. If a
reference is empty, report the metric as undefined rather than dividing by
zero. Keep unrounded rates for aggregation and comparisons; display percentages
to one decimal place.

## Annotation and reporting

Every region must have a unique `region_id`, a `region_type` (`headline` or
`article_body`), language, `split` (`dev` or `test`), page-pixel box, and
inline `reference_text`. The annotation records its revision and ties regions
to the exact source image bytes with a SHA-256 checksum. Also record the source
JP2 filename and checksum and a source URL.

Every evaluation result records source image and JP2 filenames/checksums,
source URL, region ID and coordinates, split, language, reference and OCR
inputs, annotation revision, OCR mode, PSM, OEM, tessdata directory, language
combination, model filenames and SHA-256 checksums, preprocessing, cleanup,
both normalization variants, per-region edit counts/lengths/rates, pooled
edit counts/lengths/rates, region count, and
`evaluation_rules_version: "v1"`. Also record Python, Tesseract, pytesseract,
and Pillow versions, plus the Git commit hash containing the evaluator.

Small manually transcribed development regions are sanity checks, not general
accuracy claims. Create test references before tuning and do not inspect test
OCR output while developing the pipeline.
