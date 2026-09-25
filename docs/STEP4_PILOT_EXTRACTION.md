# Step 4 Pilot Extraction Summary

This document records the pilot extraction completed for the CPWD DSR 2023 source PDFs in the repository, without importing into the live database or modifying any source material.

## Scope

- Source PDFs retained in the ignored source directory at `reference_sources/`
- Pilot candidate CSVs generated under `.pilot_extraction/`
- Validation performed through the repository preview parser only
- No live catalogue import executed

## Source coverage

- Volume I: `DSR_Vol_1_Civil 2023.pdf`, bounded section `2.0` with groups `2.1`, `2.2`, `2.3`, `2.6`, `2.7`, `2.8`, and `2.9`, plus standalone items `2.4` and `2.5`; all children are included, including cross-page `2.9.3`. Inspected PDF pages 100-104; retained rows are on PDF pages 102-103, printed pages 91-92.
- Volume II: `DSR_Vol_2_Civil  2023.pdf`, bounded groups `13.1`, `13.2`, `13.16`, `13.28`, and `13.39` under `13.0 FINISHING`, including all children in those groups; inspected PDF pages 14-18, printed pages 217-220.
- Remaining pages in both source PDFs have not yet been inventoried.

## Pilot files

- `.pilot_extraction/pilot_vol1_candidate.csv`
- `.pilot_extraction/pilot_vol2_candidate.csv`
- `.pilot_extraction/pilot_vol1_review.csv`
- `.pilot_extraction/pilot_vol2_review.csv`
- `.pilot_extraction/pilot_vol1_comparison.csv`
- `.pilot_extraction/pilot_vol2_comparison.csv`
- `.pilot_extraction/page_inventory.csv`
- `.pilot_extraction/coverage_report.txt`
- `.pilot_extraction/pilot_exceptions.csv`
- `.pilot_extraction/parent_integrity_report.txt`
- `.pilot_extraction/source_summary.txt`
- `.pilot_extraction/counts_report.txt` is recalculated from the generated candidate CSV rows.

## Validation status

The repository preview parser accepted both candidate files with zero errors:

- `pilot_vol1_candidate.csv`: counts are generated from the CSV contents; see `counts_report.txt`
- `pilot_vol2_candidate.csv`: counts are generated from the CSV contents; see `counts_report.txt`

These outputs are intentionally not imported into the main catalogue tables. They serve as a pilot extraction set for review and refinement before any production run.

## Review checks

- Volume I: Actual parent records for `2.1`, `2.2`, `2.3`, `2.6`, `2.7`, `2.8`, and `2.9` are included. Standalone priced items `2.4` and `2.5` are also included. All selected children are included, including `2.7.3` and cross-page `2.9.3`.
- Volume II: Actual parent records and all children are included for `13.1`, `13.2`, `13.16`, `13.28`, and `13.39`; `13.28.2`, `.3`, and `.4` are included.
- The explicit selected boundaries and per-group child counts are recorded in `coverage_report.txt`; generated totals are Volume I: 21 rows, 13 priced items, 8 headings; Volume II: 17 rows, 11 priced items, 6 headings.
- OCR was used as a cross-check and is labelled as such. The rendered source images were inspected for comparison evidence; this is not human verification and all records remain unverified.
- Code, description, original unit, canonical unit, and rate comparisons are recorded in the two comparison CSVs. The compound `cm per metre` basis is preserved verbatim and is not normalized to `m`.
- Unresolved parent references: `0`; invalid parent records: `0`; incomplete or repeated inherited parent descriptions: `0`; complete parent wording checks: `22`. The only remaining exception is the unsupported compound-unit measurement basis for `13.28.1`, recorded in `pilot_exceptions.csv`.
- The source manifest records SHA-256 and byte size before and after extraction. Both source PDFs were unchanged.

The isolated database check imported only the candidates and required zero unresolved parent references. It confirmed every populated `parent_item_code` resolves to exactly one included heading parent and every child contains the complete parent description exactly once. The application blocks non-Direct measurement modes for `cm per metre` because it has no native compound-unit mode.

The comparison reports are the evidence for item-level checking. Parser acceptance only confirms that the CSV structure and field validation passed; it does not establish rate accuracy.

## Review package

The complete review package is `.pilot_extraction/step4_pilot_review.zip`. It contains both corrected candidate CSVs, both review tables, both comparison reports, exceptions and coverage reports, the source checksum manifest, parent-integrity results, actual full-suite test output, preview-validation results, this document, and rendered source pages. The full source PDFs are excluded.

## Rule compliance

- Heading rows are permitted without units or rates when `is_heading = true`.
- Priced rows still require rate and normal unit fields.
- Source document names, PDF pages, and section notes are preserved for traceability.

## Notes

This is a limited Step 4 pilot only. It is designed to confirm bounded candidate rows and source traceability while keeping all records unverified, generated outputs out of Git, and the live database untouched.
