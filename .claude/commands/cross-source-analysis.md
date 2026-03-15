Run cross-source reconciliation and hypothesis tests across all 9 data sources.

## Steps

1. Load all processed CSVs from `data/processed/`
2. Align all sources to quarterly frequency (quarter-end dates)
3. Run reconciliation checks:
   - Z.1 total assets vs Form PF HF GAV (compute ratio, check stability)
   - CFTC Swaps cleared % vs DTCC cleared % (directional consistency)
   - Form PF creditor type vs Z.1 borrowing breakdown
4. Run hypothesis tests (see cross-source-analyst agent for full list)
5. Generate cross-source correlation matrix
6. Save aligned dataset to `data/processed/cross_source_aligned.csv`
7. Save test results to `outputs/reports/hypothesis_tests.csv`
8. Print structured results summary

## Prerequisites
Run these parsers first:
- `python3 -m src.data.parse_form_pf`
- `python3 -m src.data.parse_fcm`
- `python3 -m src.data.parse_dtcc`
- `python3 -m src.data.parse_swaps`
- `python3 -m src.data.fetch` (FRED, 13F, COT, VIX)

## Output Files
- `data/processed/cross_source_aligned.csv` — Unified quarterly dataset
- `outputs/reports/hypothesis_tests.csv` — Test results with p-values
- `outputs/reports/reconciliation.txt` — Source comparison report