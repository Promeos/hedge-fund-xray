Run the complete end-to-end pipeline: fetch data, parse all sources, run analysis, generate reports.

## Steps

1. **Fetch data** (skip if cached):
   ```
   python3 -m src.data.fetch
   python3 -m src.data.fetch_swaps
   python3 -m src.data.fetch_dtcc
   python3 -m src.data.fetch_fcm
   ```

2. **Parse all sources**:
   ```
   python3 -m src.data.parse_form_pf
   python3 -m src.data.parse_fcm
   python3 -m src.data.parse_dtcc
   python3 -m src.data.parse_swaps
   ```

3. **Run analysis**: `/run-analysis` (FRED metrics + charts)
4. **Cross-source**: `/cross-source-analysis`
5. **Validate**: `/validate-data`
6. **Reports**: `/generate-report`
7. **Stress tests**: `/stress-test`

## Expected Output
- 30+ processed CSVs in `data/processed/`
- Charts in `outputs/figures/`
- Reports in `outputs/reports/`
- Hypothesis test results

## Runtime
Full pipeline: ~30-60 minutes (dominated by DTCC parsing).
With cached data: ~10-15 minutes.