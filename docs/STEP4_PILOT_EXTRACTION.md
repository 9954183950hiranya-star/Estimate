# Step 4 Pilot Extraction Summary

This document records the pilot extraction completed for the CPWD DSR 2023 source PDFs in the repository, without importing into the live database or modifying any source material.

## Scope

- Source PDFs retained in the ignored source directory at `reference_sources/`
- Pilot candidate CSVs generated under `.pilot_extraction/`
- Validation performed through the repository preview parser only
- No live catalogue import executed

## Source coverage

- Volume I pilot: `DSR_Vol_1_Civil 2023.pdf`, section `2.0`, including cross-page `2.9.3` on PDF page 103 / printed page 92.
- Volume II pilot: `DSR_Vol_2_Civil  2023.pdf`, selected groups under `13.0 FINISHING`; the section note on PDF page 14 is retained in the source review evidence.
- Step 4B inventories every PDF page and extracts remaining chapters under `.chapter_extraction/`; it does not regenerate or replace the pilot.

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
- `.chapter_extraction/step4b_chapter_review.zip` contains the remaining-chapter candidates and source-driven extraction evidence.

## Validation status

The repository preview parser accepted both candidate files with zero errors:

- `pilot_vol1_candidate.csv`: counts are generated from the CSV contents; see `counts_report.txt`
- `pilot_vol2_candidate.csv`: counts are generated from the CSV contents; see `counts_report.txt`

These outputs are intentionally not imported into the main catalogue tables. They serve as a pilot extraction set for review and refinement before any production run.

## Review checks

- Volume I pilot: actual parent records and all selected children are retained, including `2.9.3` on PDF page 103.
- Volume II pilot: actual parent records and all selected children are retained; compound-unit exceptions apply to `13.28.1` through `13.28.4`, each preserved as `cm per metre`.
- The Finishing section note is preserved in the source page inventory and review evidence.
- OCR was used as a cross-check and is labelled as such. The rendered source images were inspected for comparison evidence; this is not human verification and all records remain unverified.
- Code, description, original unit, canonical unit, and rate comparisons are recorded in the two comparison CSVs. The compound `cm per metre` basis is preserved verbatim and is not normalized to `m`.
- Pilot unresolved parent references: `0`; invalid parent records: `0`; incomplete or repeated inherited parent descriptions: `0`; complete parent wording checks: `22`. Compound-unit exceptions for `13.28.1`-`13.28.4` are recorded in the Step 4B review package.
- The source manifest records SHA-256 and byte size before and after extraction. Both source PDFs were unchanged.

The isolated database check imported only the candidates and required zero unresolved parent references. It confirmed every populated `parent_item_code` resolves to exactly one included heading parent and every child contains the complete parent description exactly once. The application blocks non-Direct measurement modes for `cm per metre` because it has no native compound-unit mode.

The comparison reports are the evidence for item-level checking. Parser acceptance only confirms that the CSV structure and field validation passed; it does not establish rate accuracy.

## Review package

The complete pilot review package is `.pilot_extraction/step4_pilot_review.zip`. The separate Step 4B package is `.chapter_extraction/step4b_chapter_review.zip`. Generated data and source PDFs remain excluded from Git.

## Rule compliance

- Heading rows are permitted without units or rates when `is_heading = true`.
- Priced rows still require rate and normal unit fields.
- Source document names, PDF pages, and section notes are preserved for traceability.

## Notes

The pilot remains a bounded review. Step 4B extends extraction to the remaining chapters using OCR and resumable checkpoints while keeping all records unverified, generated outputs out of Git, the live database untouched, and correction slips unprocessed.
