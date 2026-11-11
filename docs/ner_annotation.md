# English NER Annotation Rules v1

Annotate entities on the **verified reference text** for a region, never on a
model's OCR output. Store exact reference-text offsets, entity text, and one of
`PER`, `ORG`, `LOC`, or `DATE`. Annotate before viewing spaCy predictions; add a
short note for hard calls. Count repeated mentions separately. Keep non-overlap
spans.

- **PER:** person's name, including initials and suffixes. Exclude titles and
  honorifics (`Judge`, `Mr.`, `Mrs.`, `Miss`, `Dr.`, `Rev.`, `Capt.`,
  `Warden`, and similar designations), even when printed directly before the
  name. **Exception:** keep `Commander` attached to the name, as requested for
  this project. Exclude a grammatical possessive ending. Exclude leading
  `the`; retain `'s` when it is part of an official name such as `Poli's
  Theater`.
- **ORG:** newspapers, businesses, named venues, institutions, government
  bodies, clubs, and spelled-out `Associated Press`. Do not annotate bare AP
  wire-credit tags such as `(AP)` or ship names.
- **LOC:** named geographic places, rivers, mountains, and named physical
  locations. Place names remain `LOC` when used as modifiers (`Georgia banks`).
  Split hierarchies: `Atlanta, Ga.` gives two spans, `Atlanta` and `Ga.`;
  include the period in `Ga.` Do not label demonyms such as `Georgian`.
- **DATE:** calendar dates, named weekdays/months/holidays, and day-level
  references (`today`, `yesterday`, `tomorrow`, `tonight`). Exclude clock
  times, durations, generic phrases such as `the day`, and vague words such as
  `later`.

Report NER on both verified reference text (NER-only) and OCR text (end-to-end).
Use exact entity-text-and-label matching and a separately reported lenient
similarity match; count repeated mentions as separate occurrences. For v1
lenient matching, labels must match and `difflib.SequenceMatcher` character
similarity must be at least 0.8. Pair exact duplicates first, then use a
one-to-one maximum-cardinality match among remaining candidates. Report exact
and lenient scores separately; do not compare them as if they were the same
metric. For uncertainty, resample regions with replacement, pool mention
counts for each replicate, and report the 2.5th and 97.5th percentiles from
1,000 replicates (seed `20261111` in the current report). Freeze these rules
before evaluating test pages. Re-annotate two regions a few days later without
consulting the first pass, and report span-and-label agreement. Test gold must
be completed before viewing test predictions; any rule change after test
evaluation requires v2 and a full rescore.
