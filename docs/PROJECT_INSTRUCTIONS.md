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
- A separate materials abstract, rate import, taxes, contingencies, and report export are intentionally deferred to later steps.

This application does not contain CPWD rates or correction slips. Step 2's synthetic rates are test data only and are never presented as verified CPWD data.
