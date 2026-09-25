# Step 4 Pilot Extraction Summary

This document records the pilot extraction completed for the CPWD DSR 2023 source PDFs in the repository, without importing into the live database or modifying any source material.

## Scope

- Source PDFs retained in the ignored source directory at `reference_sources/`
- Pilot candidate CSVs generated under `.pilot_extraction/`
- Validation performed through the repository preview parser only
- No live catalogue import executed

## Source coverage

- Volume I: `DSR_Vol_1_Civil 2023.pdf`, pages 100-103 for the `2.0 EARTH WORK` section
- Volume II: `DSR_Vol_2_Civil  2023.pdf`, pages 14-17 for the `13.0 FINISHING` section

## Pilot files

- `.pilot_extraction/pilot_vol1_candidate.csv`
- `.pilot_extraction/pilot_vol2_candidate.csv`
- `.pilot_extraction/pilot_vol1_review.csv`
- `.pilot_extraction/pilot_vol2_review.csv`
- `.pilot_extraction/page_inventory.csv`
- `.pilot_extraction/coverage_report.txt`
- `.pilot_extraction/pilot_exceptions.csv`
- `.pilot_extraction/source_summary.txt`

## Validation status

The repository preview parser accepted both candidate files with zero errors:

- `pilot_vol1_candidate.csv`: 12 rows, 0 errors
- `pilot_vol2_candidate.csv`: 14 rows, 0 errors

These outputs are intentionally not imported into the main catalogue tables. They serve as a pilot extraction set for review and refinement before any production run.

## Rule compliance

- Heading rows are permitted without units or rates when `is_heading = true`.
- Priced rows still require rate and normal unit fields.
- Source document names, PDF pages, and section notes are preserved for traceability.

## Notes

This is a limited Step 4 pilot only. It is designed to confirm that the repository can process valid candidate rows while keeping the working outputs out of Git and away from the live database.
