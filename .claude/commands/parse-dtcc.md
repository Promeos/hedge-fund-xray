Parse all DTCC swap repository ZIP files and build daily/quarterly summaries.

## Steps

1. Run `python3 -m src.data.parse_dtcc`
2. Parses all ZIP files in `data/raw/dtcc/` (each contains ~30K trade CSV)
3. Extracts: trade count, notional, cleared %, PB %, block % per asset class per day
4. Aggregates to quarterly for cross-source alignment

## Output Files
- `dtcc_daily_summary.csv` — Daily aggregates by asset class
- `dtcc_product_daily.csv` — Daily breakdown by underlying product
- `dtcc_quarterly.csv` — Quarterly aggregates

## Note
This parser processes hundreds of large ZIP files and may take 10-30 minutes.
Each file contains 110 columns; only key columns are extracted for efficiency.

## Validation
- RATES should dominate by trade count and notional
- Cleared % should be >50% for RATES (Dodd-Frank mandate)
- ~31K trades/day for RATES is typical