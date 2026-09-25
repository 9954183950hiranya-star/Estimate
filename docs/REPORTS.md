# Estimate reports

Save the project and BOQ changes before opening Reports. Enter optional local-body,
constituency, financial-year, budget and prepared-by details. Set deduction and
contingency percentages explicitly; both default to zero. Settings are saved per
project. Contingency applies after the contractor-profit deduction.

Preview and export use saved BOQ snapshots. Detailed estimate and cost abstract
share the same rounded amounts; quantity is rounded to three places before rate
multiplication. Adjustments are rounded to two places. No automatic budget fitting
or arbitrary "Say" amount is applied. Material consumption is not inferred.

All exports are drafts. A rate-source appendix retains unverified/manual/review
statuses. This release does not implement formal approval or immutable estimate
revision history. Reports are value snapshots, not recalculating Excel templates.
Use the app to edit measurements and regenerate the report. Weight calculations
can currently be entered as direct quantities with the working recorded in remarks.

Excel export requires XlsxWriter. PDF uses Qt's PDF printer. The specimen guides
headings, measurement details, cost grouping and signature blocks; pagination is
adapted for landscape A4 rather than copying the specimen's fixed cell addresses.
