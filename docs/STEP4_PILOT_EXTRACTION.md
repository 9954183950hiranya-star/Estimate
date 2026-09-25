# Step 4 Pilot Extraction Summary

This document records the pilot extraction completed for the CPWD DSR 2023 source PDFs in the repository, without importing into the live database or modifying any source material.

## Scope

- Source PDFs retained in the ignored source directory at `reference_sources/`
- Pilot candidate CSVs generated under `.pilot_extraction/`
- Validation performed through the repository preview parser only
- No live catalogue import executed

## Source coverage

- Volume I: `DSR_Vol_1_Civil 2023.pdf`, inspected PDF pages 100-103 for the bounded `2.0 EARTH WORK` pilot group. Retained priced rows are on PDF page 102, printed page 91.
- Volume II: `DSR_Vol_2_Civil  2023.pdf`, inspected PDF pages 14-17 for bounded groups under `13.0 FINISHING`, printed pages 217-220.
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

## Validation status

The repository preview parser accepted both candidate files with zero errors:

- `pilot_vol1_candidate.csv`: 11 priced items and 1 heading, 0 preview errors
- `pilot_vol2_candidate.csv`: 8 priced items and 6 headings, 0 preview errors

These outputs are intentionally not imported into the main catalogue tables. They serve as a pilot extraction set for review and refinement before any production run.

## Review checks

- Volume I: 11 priced items and 1 heading. Child descriptions contain the complete source wording for parents `2.1`, `2.2`, `2.3`, `2.6`, `2.7`, `2.8`, and `2.9`. Those parent rows are outside this bounded CSV and are reported explicitly as missing-parent exceptions.
- Volume II: 8 priced items and 6 headings. Parent descriptions include `12 mm cement plaster of mix:`, `6 mm cement plaster of mix:`, and the complete 12 mm plain cement mortar specification.
- OCR was used as a cross-check and is labelled as such. The rendered source images were inspected for comparison evidence; this is not human verification and all records remain unverified.
- Code, description, original unit, canonical unit, and rate comparisons are recorded in the two comparison CSVs. The compound `cm per metre` basis is preserved verbatim and is not normalized to `m`.
- Unresolved structural issues: 9 missing-parent references across 7 Volume I parent codes, plus 1 unsupported compound-unit measurement basis. These are recorded in `pilot_exceptions.csv`.
- The source manifest records SHA-256 and byte size before and after extraction. Both source PDFs were unchanged.

The isolated database check imported only the candidates and confirmed zero incomplete or repeated parent descriptions. It separately reported the nine missing parent references instead of silently accepting them. The application blocks non-Direct measurement modes for `cm per metre` because it has no native compound-unit mode.

The comparison reports are the evidence for item-level checking. Parser acceptance only confirms that the CSV structure and field validation passed; it does not establish rate accuracy.

## Review package

The complete review package is `.pilot_extraction/step4_pilot_review.zip`. It contains both candidate CSVs, both review tables, both comparison reports, exceptions and coverage reports, the source checksum manifest, preview-validation results, this document, and rendered source pages. The full source PDFs are excluded.

## Rule compliance

- Heading rows are permitted without units or rates when `is_heading = true`.
- Priced rows still require rate and normal unit fields.
- Source document names, PDF pages, and section notes are preserved for traceability.

## Notes

This is a limited Step 4 pilot only. It is designed to confirm bounded candidate rows and source traceability while keeping all records unverified, generated outputs out of Git, and the live database untouched.
