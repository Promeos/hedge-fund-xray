Parse all Form PF supporting data and produce processed CSVs with derived metrics.

## Steps

1. Run `python3 -m src.data.parse_form_pf`
2. This parses the latest Excel file in `data/raw/form_pf/` (contains full history 2013Q1–2025Q1)
3. Produces 14 data CSVs + 5 derived metric CSVs in `data/processed/`
4. Print summary: latest HF GAV, NAV, GAV/NAV ratio, top-10 concentration

## Output Files

**Data CSVs:**
- `form_pf_gav_nav.csv` — GAV, NAV, leverage ratio by fund type
- `form_pf_fund_counts.csv` — Fund counts by type
- `form_pf_borrowing_pct.csv` — Borrowing as % of GAV
- `form_pf_borrowing_detail.csv` — Monthly: Reverse Repo, Prime Broker, Other, Unsecured
- `form_pf_borrowing_creditor.csv` — Monthly: creditor type breakdown
- `form_pf_derivatives.csv` — Derivative value and % of NAV
- `form_pf_concentration.csv` — Top-N fund shares
- `form_pf_strategy.csv` — GAV, NAV, borrowing by strategy
- `form_pf_leverage_dist.csv` — Monthly leverage bucket distributions
- `form_pf_notional.csv` — Monthly long/short notional by 35 investment types
- `form_pf_liquidity.csv` — Investor, portfolio, financing liquidity
- `form_pf_fair_value.csv` — Level 1/2/3 fair value hierarchy
- `form_pf_geography.csv` — Regional exposure
- `form_pf_sector.csv` — Industry/sector allocation

**Derived Metric CSVs:**
- `form_pf_metric_hf_gav_nav.csv` — HF leverage time series
- `form_pf_metric_concentration_top10.csv` — Concentration trend
- `form_pf_metric_latest_notional.csv` — Latest directional exposures
- `form_pf_metric_strategy_hhi.csv` — Strategy diversification index
- `form_pf_metric_liquidity_mismatch.csv` — Redemption and funding risk

## Validation
- HF GAV should be ~$12.6T (2025Q1)
- GAV/NAV ratio should be ~2.3x
- Top-10 NAV share should be ~8.2%
- All values in billions USD