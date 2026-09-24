# Project Instructions

- CPWD DSR Civil 2023 is the base rate reference for this application.
- Apply only verified correction slips dated on or before the project's correction-slip cutoff date.
- Never invent rates or label sample data as verified CPWD data.
- Use `Decimal` arithmetic for calculations. Monetary values currently use documented two-decimal `ROUND_HALF_UP` rounding in `estimate_app/calculation/decimal_policy.py`.
- Preserve the rate and source used in each estimate revision. The revision and rate-source schema will be added with the estimating workflow.
- Detailed measurements and a separate materials abstract are intentionally deferred to later steps.

This foundation does not contain CPWD rates, correction slips, or estimate quantities.
