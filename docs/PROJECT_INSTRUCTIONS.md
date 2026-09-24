# Project Instructions

- CPWD DSR Civil 2023 is the base rate reference for this application.
- Apply only verified correction slips dated on or before the project's correction-slip cutoff date.
- Never invent rates or label sample data as verified CPWD data.
- Use `Decimal` arithmetic for calculations. Monetary values currently use documented two-decimal `ROUND_HALF_UP` rounding in `estimate_app/calculation/decimal_policy.py`.
- Preserve the rate and source used in each estimate revision. BOQ items currently preserve their rate source and verification status; revision history will be added with the estimating workflow.
- BOQ quantities are calculated from detailed measurements. Volume uses repetitions x number x length x breadth x height/depth; area omits height/depth; length omits breadth and height/depth; count uses repetitions x number; direct quantity uses the entered quantity in the item's unit.
- Use metres for dimensional inputs. Deductions are represented by an explicit deduction flag and are subtracted from gross additions.
- Keep full Decimal precision during calculation, display quantities to 3 decimal places, and round monetary amounts to 2 decimal places using `ROUND_HALF_UP`. Amounts use the same rounded quantity shown in the BOQ.
- Reject negative and non-finite inputs. Negative net quantities are flagged and cannot be finalised. Items without measurements show `Measurements required`; missing rates are distinct from an explicit zero rate.
- Changing an item's unit when measurements exist requires explicit resolution and clears those measurements only after confirmation.
- Catalogue imports are UTF-8 CSV only, start as `Unverified`, and require explicit reviewer verification with source information before selection in a BOQ.
- Keep original DSR entries immutable. Correction slips are separate records and only verified slips effective on or before the project's cutoff date may resolve an item. Conflicting corrections are blocked; precedence must never be guessed.
- A selected catalogue rate is copied into the BOQ as a provenance snapshot. Later imports or corrections must not silently change existing estimates. Rate changes require explicit review; unit changes require measurement review.
- Verification can be withdrawn with a reviewer, date, and reason. Withdrawn records are excluded from new selections, while existing BOQ snapshots retain their saved values and are flagged for review.
- Local source PDFs are copied to the per-user `reference_documents` directory outside the repository and tracked by document name and SHA-256 checksum. Missing files must be reported rather than silently ignored.
- A separate materials abstract, taxes, contingencies, and report export are intentionally deferred to later steps.

The actual CPWD DSR PDFs and correction slips have not been supplied to this Codespace. The application does not claim the catalogue is complete or up to date. Synthetic fixtures used by tests are never presented as verified CPWD data.
