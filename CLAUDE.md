# Hedge Fund X-Ray

Open-source intelligence project reconstructing the U.S. hedge fund industry from 9 public regulatory data sources — balance sheets, derivatives, borrowing, positioning, fund-level holdings, trade-level swap data, and broker financials.

## Directory Structure

```
financial_data/
├── CLAUDE.md                    # This file — project guide
├── LICENSE                      # CC BY-SA 4.0
├── .claude/
│   ├── settings.local.json      # Claude Code permissions
│   ├── agents/                  # 13 specialized agent definitions
│   │   ├── data-engineer.md     # Data pipeline agent (9 sources)
│   │   ├── analyst.md           # Financial analysis agent
│   │   ├── visualizer.md        # Charting agent (18 chart functions)
│   │   ├── report-writer.md     # Report generation agent
│   │   ├── data-quality.md      # Data validation agent (9 sources)
│   │   ├── statistician.md      # Statistical analysis + hypothesis tests
│   │   ├── regulatory-expert.md # SEC/CFTC/DTCC regulatory context
│   │   ├── scenario-analyst.md  # 10 stress test scenarios
│   │   ├── form-pf-analyst.md   # SEC Form PF specialist (141 sheets)
│   │   ├── swaps-analyst.md     # CFTC Weekly Swaps specialist
│   │   ├── dtcc-analyst.md      # DTCC trade-level data specialist
│   │   ├── fcm-analyst.md       # FCM broker financials specialist
│   │   └── cross-source-analyst.md  # Cross-source reconciliation
│   └── commands/                # 10 slash commands
│       ├── refresh-data.md      # /refresh-data
│       ├── run-analysis.md      # /run-analysis
│       ├── validate-data.md     # /validate-data
│       ├── generate-report.md   # /generate-report
│       ├── stress-test.md       # /stress-test
│       ├── parse-form-pf.md     # /parse-form-pf
│       ├── parse-swaps.md       # /parse-swaps
│       ├── parse-dtcc.md        # /parse-dtcc
│       ├── parse-fcm.md         # /parse-fcm
│       ├── cross-source-analysis.md  # /cross-source-analysis
│       └── full-pipeline.md     # /full-pipeline
├── .env                         # API keys (never commit)
├── requirements.txt             # Python dependencies
├── data/
│   ├── raw/                     # Original data (cached)
│   │   ├── swaps/               # ~600 CFTC weekly swap reports
│   │   ├── dtcc/                # ~1,825 daily DTCC cumulative reports
│   │   ├── fcm/                 # 49 monthly FCM financial reports
│   │   ├── form_pf/             # SEC Form PF statistics (xlsx + pdf)
│   │   ├── form_adv/            # Fund profiles from EDGAR API
│   │   ├── 13f_*.csv            # Fund-level equity holdings
│   │   ├── cftc_cot.csv         # Futures positioning
│   │   └── vix_quarterly.csv    # Volatility index
│   ├── processed/               # 30+ parsed CSVs
│   └── .gitignore
├── notebooks/
│   └── hedge_fund_analysis.ipynb
├── src/
│   ├── __init__.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── fetch.py             # FRED, SEC EDGAR, CFTC, VIX fetchers
│   │   ├── fetch_swaps.py       # CFTC weekly swap downloader
│   │   ├── fetch_dtcc.py        # DTCC cumulative report downloader
│   │   ├── fetch_fcm.py         # CFTC FCM report downloader
│   │   ├── parse_form_pf.py     # Form PF Excel parser (141 sheets → 19 CSVs)
│   │   ├── parse_swaps.py       # CFTC swaps parser (Sheet 1 → weekly time series)
│   │   ├── parse_dtcc.py        # DTCC ZIP parser (110-col CSV → daily summaries)
│   │   ├── parse_fcm.py         # FCM Excel parser (monthly → industry + broker CSVs)
│   │   └── prepare.py           # Data cleaning and transformation
│   ├── analysis/
│   │   ├── __init__.py
│   │   └── metrics.py           # Derived metrics and statistical computations
│   └── visualization/
│       ├── __init__.py
│       └── plots.py             # matplotlib/seaborn chart functions
├── tests/
└── outputs/
    ├── figures/                 # Generated charts
    └── reports/                 # Reports, hypothesis tests, stress tests
```

## Tech Stack

- **Python 3.10+**
- Core: `pandas`, `numpy`, `openpyxl`
- Statistics: `statsmodels`, `scipy`, `scikit-learn`
- Visualization: `matplotlib`, `seaborn`
- Data access: `requests`, `fredapi`
- Configuration: `python-dotenv`

## Data Sources (9)

| # | Source | Fetcher | Parser | Coverage |
|---|--------|---------|--------|----------|
| 1 | **Federal Reserve Z.1** | `fetch.py` | `prepare.py` | 1945–2025, quarterly |
| 2 | **SEC Form PF** | Manual | `parse_form_pf.py` | 2013–2025, quarterly + monthly |
| 3 | **CFTC Weekly Swaps** | `fetch_swaps.py` | `parse_swaps.py` | 2013–2026, weekly |
| 4 | **SEC EDGAR 13F** | `fetch.py` | `fetch.py` | Per filing |
| 5 | **SEC EDGAR Submissions** | `fetch.py` | `fetch.py` | 1996–2026 |
| 6 | **CFTC COT** | `fetch.py` | `fetch.py` | Weekly |
| 7 | **CBOE VIX** | `fetch.py` | `fetch.py` | Daily → quarterly |
| 8 | **DTCC Swap Repository** | `fetch_dtcc.py` | `parse_dtcc.py` | 2025–2026, daily |
| 9 | **CFTC FCM Financials** | `fetch_fcm.py` | `parse_fcm.py` | 2022–2026, monthly |

## Key Commands

```bash
pip install -r requirements.txt

# Fetch data
python -m src.data.fetch           # FRED, 13F, COT, VIX
python -m src.data.fetch_swaps     # ~600 weekly CFTC reports
python -m src.data.fetch_dtcc      # ~1,825 daily DTCC reports
python -m src.data.fetch_fcm       # 49 monthly FCM reports

# Parse data
python -m src.data.parse_form_pf   # → 19 CSVs in data/processed/
python -m src.data.parse_swaps     # → 3 CSVs
python -m src.data.parse_dtcc      # → 3 CSVs
python -m src.data.parse_fcm       # → 5 CSVs

# Analysis
jupyter notebook notebooks/hedge_fund_analysis.ipynb
pytest tests/
```

## Coding Conventions

- All monetary values in **billions USD** (FRED returns millions ÷ 1000; FCM in raw USD ÷ 1e9)
- **Quarterly frequency** for cross-source alignment (quarter-end dates)
- **Cache first**: Check `data/raw/` before API calls
- Rate limits: 0.2s FRED, 0.15s SEC EDGAR, 0.2s DTCC, 0.3s CFTC
- Date parsing: `pd.to_datetime`; numeric: `pd.to_numeric(errors='coerce')`
- Plotting: `seaborn-v0_8-whitegrid`, `(14, 6)`, DPI 100, font 12pt
- Event annotations via `add_event_annotations()`

## Security

- `.env` contains `FRED_API_KEY` — **never commit**
- SEC EDGAR `User-Agent` header needs real contact email for production
- All other data sources are publicly accessible without credentials

## Agents (13)

| Agent | File | Purpose |
|-------|------|---------|
| Data Engineer | `data-engineer.md` | 9-source data pipelines, caching, rate limiting |
| Financial Analyst | `analyst.md` | Leverage trends, allocation analysis, market events |
| Visualizer | `visualizer.md` | 18 chart functions, style guide, event annotations |
| Report Writer | `report-writer.md` | Executive summaries, HTML reports, CSV exports |
| Data Quality | `data-quality.md` | 9-source validation, cross-source reconciliation |
| Statistician | `statistician.md` | ARIMA, Granger causality, regime detection, multi-source tests |
| Regulatory Expert | `regulatory-expert.md` | SEC/CFTC/DTCC filing interpretation, regulatory timeline |
| Scenario Analyst | `scenario-analyst.md` | 10 stress scenarios, VaR/CVaR, Monte Carlo |
| Form PF Analyst | `form-pf-analyst.md` | 141-sheet Excel parser, 8 hypothesis tests, leverage/liquidity |
| Swaps Analyst | `swaps-analyst.md` | CFTC weekly swaps, IR/Credit/FX notional, clearing trends |
| DTCC Analyst | `dtcc-analyst.md` | Trade-level OTC data, 110 columns, clearing/PB analysis |
| FCM Analyst | `fcm-analyst.md` | Broker capital, customer segregation, concentration |
| Cross-Source Analyst | `cross-source-analyst.md` | 9-source reconciliation, 9 hypothesis tests |

## Slash Commands (10)

| Command | Purpose |
|---------|---------|
| `/refresh-data` | Fetch latest data from all sources |
| `/run-analysis` | End-to-end: load → metrics → charts → stats |
| `/validate-data` | Full data quality sweep (PASS/WARN/FAIL) |
| `/generate-report` | Executive summary, charts, CSV exports |
| `/stress-test` | 10 stress scenarios + VaR/drawdown |
| `/parse-form-pf` | Parse Form PF → 19 CSVs |
| `/parse-swaps` | Parse CFTC swaps → 3 CSVs |
| `/parse-dtcc` | Parse DTCC trades → 3 CSVs |
| `/parse-fcm` | Parse FCM financials → 5 CSVs |
| `/cross-source-analysis` | Cross-source reconciliation + hypothesis tests |
| `/full-pipeline` | Run everything end-to-end |

## Derived Metrics Reference

### Z.1 Balance Sheet Metrics
| Metric | Formula |
|--------|---------|
| `leverage_ratio` | Total liabilities / Total net assets |
| `cash_to_assets` | (Deposits + Other cash + MMF) / Total assets |
| `equity_pct` | Corporate equities / Total assets |
| `derivative_to_assets` | Derivatives (long) / Total assets |
| `prime_brokerage_pct` | Prime brokerage / Total loans (liability) |
| `foreign_borrowing_share` | Foreign / (Domestic + Foreign) |

### Form PF Metrics
| Metric | Formula |
|--------|---------|
| `gav_nav_ratio` | GAV / NAV (true leverage proxy) |
| `derivative_nav_ratio` | Derivative value / NAV |
| `net_notional_by_type` | Long − Short per investment type |
| `strategy_hhi` | Σ(strategy NAV share²) |
| `liquidity_mismatch_30d` | Portfolio liquid 30d − Investor redeemable 30d |
| `level3_asset_pct` | Level 3 / total assets |

### FCM Metrics
| Metric | Formula |
|--------|---------|
| `capital_adequacy_ratio` | adj_net_capital / requirement |
| `swap_seg_share` | cleared_swap_seg / (customer_seg + swap_seg) |
| `hhi` | Σ(FCM market share²) |

### DTCC Metrics
| Metric | Formula |
|--------|---------|
| `cleared_pct` | Cleared trades / total trades |
| `pb_pct` | Prime brokerage / total trades |
| `avg_trade_size` | Total notional / trade count |
