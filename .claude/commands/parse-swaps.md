Parse all CFTC weekly swap reports and build time series CSVs.

## Steps

1. Run `python3 -m src.data.parse_swaps`
2. Parses Sheet 1 (overview) from each Excel file in `data/raw/swaps/`
3. Extracts IR, Credit, FX notional (total/cleared/uncleared) per week
4. Deduplicates overlapping weekly dates across files
5. Converts millions → billions USD

## Output Files
- `swaps_weekly.csv` — Wide format: IR/Credit/FX notional + cleared % per week
- `swaps_weekly_long.csv` — Long format: metric, date, value
- `swaps_quarterly.csv` — Quarter-end snapshots for cross-source alignment

## Validation
- IR notional ~$400-415T (in billions column)
- Credit notional ~$6T
- FX notional ~$75-80T (post-Oct 2018 only)
- IR cleared % ~86%
- Credit cleared % ~67%
- FX cleared % ~4%

## Notes
- FX data only available from Oct 2018 onward
- Government shutdown gap: Dec 22 2018 – Jan 26 2019
- Equity/commodity swaps reporting discontinued Oct 2015