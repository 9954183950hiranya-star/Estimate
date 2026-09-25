# Step 4B Chapter Extraction

Step 4B extracts the chapters not covered by the bounded Step 4 pilot from the uploaded CPWD DSR 2023 Volume I and Volume II PDFs.

## Controls

- Source pages are rendered from the PDFs and OCR is used only to recover scanned-page text.
- The extractor writes page-level OCR, source images, page/chapter inventory, chapter CSVs, ambiguity records, and resumable checkpoints under `.chapter_extraction/`.
- Rows already present in `.pilot_extraction/` are excluded from Step 4B candidates; the pilot is preserved unchanged.
- A row is emitted only when its item code, description, unit, and rate are structurally recoverable. Unclear rows are recorded in `ambiguities.csv` with a source page and no guessed values.
- Parent descriptions and child rows are retained as separate source records. Each chapter is imported with the pilot into a disposable SQLite database and checked for unresolved parents and inherited wording.
- All imported records remain `Unverified`. No live catalogue import or correction-slip processing occurs.

## Outputs

The review package is `.chapter_extraction/step4b_chapter_review.zip`. It contains the remaining candidate CSVs, per-chapter CSVs, complete page/chapter inventory, counts, ambiguity and parent-integrity reports, checkpoints, source images, test output, and this document. The source PDFs are excluded.
