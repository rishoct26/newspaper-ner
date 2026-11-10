# English NER Annotation Rules v1

Annotate entities on the **verified reference text** for a region, never on a
model's OCR output. Store exact reference-text offsets, entity text, and one of
`PER`, `ORG`, `LOC`, or `DATE`. Annotate before viewing spaCy predictions; add a
short note for hard calls. Count repeated mentions separately. Keep non-overlap
spans.

- **PER:** person's name, including initials and suffixes. Exclude titles
  (`Judge`, `Mr.`, `Dr.`) and a grammatical possessive ending. Exclude leading
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
similarity match; count repeated mentions as separate occurrences. Freeze the
lenient matching rule before evaluating test pages. Re-annotate two regions a
few days later without consulting the first pass, and report span-and-label
agreement. Test gold must be completed before viewing test predictions; any
rule change after test evaluation requires v2 and a full rescore.
