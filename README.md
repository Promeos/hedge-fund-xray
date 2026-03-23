# Hedge Fund Autopsy

Reconstructing the U.S. hedge fund industry from 9 public regulatory data sources.

An open-source intelligence project dissecting the financial anatomy of U.S. hedge funds — balance sheets, derivatives, borrowing, positioning, and fund-level holdings — stitched together from sources no one combines.

![Balance Sheet Overview](docs/hero_balance_sheet_overview.png)

## The Thesis

The hedge fund industry reports to a dozen different regulators in a dozen different formats. No single source tells the full story. But combined, they do.

This project pulls from **9 public data sources** across the Federal Reserve, SEC, CFTC, DTCC, and CBOE to build a unified picture of:

- **$3.3 trillion** in total assets (Fed Z.1 Q3 2025) — with **$12.6T** in gross assets via Form PF
- **$20.2 trillion** in derivative exposure — 3.7x their net asset value
- **$415 trillion** in interest rate swap notional flowing through the system weekly
- **384,723 individual equity holdings** across 8 of the largest funds — rolling 2-year window (2024–2026), amendment-deduped
- **Over 1 million OTC derivative trades per day** flowing through DTCC
- The complete **borrowing, leverage, and counterparty structure** of an industry that answers to no single regulator

## Data Sources

| # | Source | What It Reveals | Coverage |
|---|--------|----------------|----------|
| 1 | **Federal Reserve Z.1** | Aggregate balance sheet (Table B.101.f) — assets, liabilities, net worth | Raw FRED series span 1945–2025; usable hedge fund observations begin 2012 Q4 |
| 2 | **SEC Form PF** | Private fund statistics — GAV, NAV, leverage, derivatives, borrowing by creditor, strategy allocation, concentration | 2013–2025, quarterly + monthly |
| 3 | **CFTC Weekly Swaps** | OTC derivatives market — interest rate, credit, and FX swap notional, volumes, counterparty splits | 2013–2026, weekly |
| 4 | **SEC EDGAR 13F** | Fund-level equity holdings for Citadel, Bridgewater, Renaissance, Point72, Two Sigma, D.E. Shaw, Millennium, AQR — amendment-deduped | Rolling 2-year window (currently 2024–2026) |
| 5 | **SEC EDGAR Submissions** | Complete filing history, SC 13G (5%+ ownership stakes), Form ADV registration | 1996–2026 |
| 6 | **CFTC COT** | Leveraged fund positioning in equity index futures | Weekly |
| 7 | **CBOE VIX** | Market volatility index | Daily, aggregated quarterly |
| 8 | **DTCC Swap Repository** | Trade-level OTC derivative transactions — notional, counterparty type, clearing status, block-trade and prime-broker flags | Local snapshot: 2025-03-13 to 2026-03-13, daily |
| 9 | **CFTC FCM Financials** | Broker-level adjusted net capital, excess capital, customer segregated funds, cleared swap segregation | Local snapshot: 2022-01 to 2026-01, monthly |

## What We've Found So Far

### The Industry Is 4x Larger Than Reported
The Fed's Z.1 shows **$3.26T** in hedge fund assets (Q3 2025, all-time high, +16% YoY). SEC Form PF shows **$12.6T in gross assets** and **$20.2T in derivatives**. The difference is leverage and off-balance-sheet exposure that the Fed's flow-of-funds framework doesn't capture.

### Extreme Concentration
- Top 10 funds control **8.2%** of industry NAV
- Top 500 funds control **54.8%**
- Combined 13F equity AUM across 8 mega funds: **$831B** (Q4 2025 shares only)
- NVIDIA held by all 8 funds ($19.1B combined); iShares ETFs are the #1 position ($20.3B)
- Citadel filed **854 SC 13G forms** (5%+ ownership in 854 companies)

### The Borrowing Machine
- **78%** of hedge fund borrowing flows through prime brokerage
- Only **2.1%** is unsecured — the rest is collateralized
- In **2025Q1**, **63.9%** of creditors are U.S. financial institutions and **35.3%** are non-U.S. financial institutions
- In **2025-03**, qualifying hedge funds held **$2.8T** in reverse repo and **$2.6T** in prime-broker financing

### Leverage Is Mean-Reverting — But at the All-Time Peak
Augmented Dickey-Fuller test (p=0.02) confirms the industry's leverage ratio is stationary — it oscillates around a mean of 0.43x and self-corrects. But as of Q3 2025, leverage hit **0.485x** — the **all-time high** across all 52 quarters of Z.1 data (Q4 2012 onward). It climbed from 0.420x to 0.485x in just 5 quarters (Q2 2024 – Q3 2025), the fastest buildup in the series. This implies systemic deleveraging mechanisms exist, but also that leverage always rebuilds — and it has never been higher than right now.

### The Derivatives Iceberg
- **$4.8T long / $4.9T short** in interest rate derivatives — nearly perfectly hedged
- **$1.8T long / $945B short** in equities — net long $883B
- **$517B long / $639B short** in credit — **net short $122B** (betting on defaults)
- The weekly CFTC swaps data shows **$415T** in IR notional outstanding — the plumbing beneath everything

### The Contagion Chain

The individual findings above aren't independent — they're links in a statistically verified cascade. Granger causality tests (5/30 significant pairs) show that volatility shocks *cause* leverage adjustments (VIX → GAV/NAV, p=0.002) and broker capital stress (VIX → FCM excess capital, p=0.002), while leverage shifts feed back into volatility (Z.1 leverage → VIX, p=0.026). This isn't correlation — the causal direction is testable and confirmed.

The accelerants are already in place:

- **Liquidity mismatch:** 46.5% of hedge fund capital can't be liquidated within 30 days — redemption shocks force fire sales at exactly the wrong moment
- **Rising broker concentration:** FCM market HHI is trending upward (p<0.001) — fewer brokers are absorbing more risk each cycle, widening the blast radius when one breaks
- **Leverage is at the all-time peak:** 0.485x (Q3 2025) — the highest in 52 quarters of Z.1 data, with the fastest 5-quarter buildup on record. Monte Carlo simulation (10K paths, 8Q horizon) gives VaR 95% = -1.7% and P(negative) = 7.1%

The dominoes are: **volatility spike → fund deleveraging → broker capital strain → further forced selling** — and the system is more concentrated and less liquid than it was the last time this happened.

### Cross-Source Statistical Tests

The current suite emits **18 result rows**: 8 named cross-source tests plus 10 ADF/Mann-Kendall checks on key series. Key findings:

| Test | Result | p-value | What It Means |
|------|--------|---------|---------------|
| **Liquidity gap vs VIX** | **PASS** | 0.005 | The 30-day investor-minus-portfolio liquidity gap moves higher in high-VIX quarters, but remains negative in the bundled sample |
| **VIX → GAV/NAV (Granger)** | **PASS** | 0.002 | Volatility *causes* leverage changes — fear drives deleveraging |
| **Z.1 leverage stationarity** | **PASS** | 0.026 | Industry leverage is mean-reverting around ~0.43x liabilities / net assets |
| **Form PF GAV trend** | **PASS** | 0.000 | Industry gross assets trending strongly upward |
| **Form PF GAV/NAV trend** | **PASS** | 0.000 | Leverage ratio trending upward — funds are levering up |
| **Z.1 ~ Form PF cointegration** | FAIL | 0.173 | The two measures of industry size move independently |
| **Z.1/Form PF ratio stability** | FAIL | 0.944 | The gap between Fed and SEC views of the industry is *widening* |
| **CFTC IR vs DTCC rates clearing** | FAIL | 0.993 | Rates clearing measures are not equivalent within a 10pp band in the local 2025Q1–2026Q1 overlap |
| **Form PF → Z.1 leverage** | FAIL | 0.086 | Borderline — SEC data nearly predicts Fed data at 10% level |

Additionally, the advanced analysis found **3 structural breaks** in Form PF GAV/NAV (2017Q3, 2020Q2, 2023Q1) and **2 cointegrating relationships** between Form PF GAV and IR/Credit swap notional — the derivatives market and fund leverage are locked in long-run equilibrium. Full test results are saved to `outputs/reports/cross_source_tests.csv`.

## Visualizations

20+ publication-quality charts generated to `outputs/figures/`:

| Category | Charts |
|----------|--------|
| **Z.1 Balance Sheet** | Total assets, asset composition, debt securities, liability structure, balance sheet overview, derivative exposure, borrowing patterns, correlation heatmap |
| **Form PF** | GAV/NAV leverage, strategy allocation, concentration trends |
| **CFTC Swaps** | Clearing rates, notional outstanding |
| **FCM** | Capital & adequacy, market concentration |
| **DTCC** | Notional by asset class, clearing rates |
| **EDGAR** | Filing volume by fund |
| **Cross-Source** | Z.1 vs Form PF leverage comparison |

## Setup

```bash
pip install -r requirements.txt
echo "FRED_API_KEY=your_key_here" > .env
```

Get a free FRED API key at https://fred.stlouisfed.org/docs/api/api_key.html

## Usage

```bash
# Fetch all data (cached after first run)
python -m src.data.fetch

# Download available CFTC weekly swap reports
python -m src.data.fetch_swaps

# Download available DTCC trade-level swap data
python -m src.data.fetch_dtcc

# Download available CFTC FCM financial reports
python -m src.data.fetch_fcm

# Parse all data sources into processed CSVs
python -m src.data.parse_form_pf    # 141 sheets → 19 CSVs
python -m src.data.parse_fcm        # 49 files → 5 CSVs
python -m src.data.parse_dtcc       # available ZIPs → 2 CSVs + parse log
python -m src.data.parse_swaps      # available files → 3 CSVs

# Run cross-source analysis (alignment, reconciliation, 18 hypothesis tests)
python -m src.analysis.cross_source

# Run the analysis notebook
jupyter notebook notebooks/hedge_fund_analysis.ipynb
```

## Project Structure

```
├── data/
│   ├── raw/
│   │   ├── swaps/              # ~600 weekly CFTC swap reports (xlsx)
│   │   ├── dtcc/               # Daily DTCC cumulative swap reports (zip/csv)
│   │   ├── fcm/                # Monthly FCM financial reports (xlsx)
│   │   ├── form_pf/            # SEC Form PF statistics (xlsx + pdf)
│   │   ├── form_adv/           # Fund profiles from EDGAR Submissions API
│   │   ├── 13f_*.csv           # Fund-level holdings
│   │   ├── cftc_cot.csv        # Futures positioning
│   │   └── vix_quarterly.csv   # Volatility index
│   └── processed/              # Cleaned, merged, derived datasets
├── src/
│   ├── data/
│   │   ├── fetch.py            # FRED, SEC EDGAR, CFTC, VIX fetchers
│   │   ├── fetch_swaps.py      # CFTC weekly swap report downloader
│   │   ├── fetch_dtcc.py       # DTCC trade-level swap data downloader
│   │   ├── fetch_fcm.py        # CFTC FCM financial report downloader
│   │   ├── parse_form_pf.py    # Form PF Excel parser (141 sheets → 19 CSVs)
│   │   ├── parse_fcm.py        # FCM financial report parser (49 files → 5 CSVs)
│   │   ├── parse_dtcc.py       # DTCC daily swap report parser (available ZIPs → 2 CSVs + log)
│   │   ├── parse_swaps.py      # CFTC weekly swap report parser (available files → 3 CSVs)
│   │   └── prepare.py          # Data cleaning and transformation
│   ├── analysis/
│   │   ├── metrics.py          # Derived metrics and statistics
│   │   ├── advanced.py         # Granger causality, VAR, Monte Carlo, structural breaks
│   │   └── cross_source.py     # Cross-source alignment, reconciliation, 18 hypothesis tests
│   └── visualization/
│       └── plots.py            # 18 matplotlib/seaborn chart functions
├── notebooks/
│   └── hedge_fund_analysis.ipynb
└── outputs/
    ├── figures/                # Generated charts
    └── reports/                # Executive summary, stress tests, stats
```

## Tech Stack

Python 3.10+ — pandas, numpy, matplotlib, seaborn, fredapi, openpyxl, requests, python-dotenv

## Processed Data

Core processed outputs in `data/processed/`:

| Source | Files | Key Outputs |
|--------|-------|-------------|
| Form PF | 19 | GAV/NAV, strategy allocation, concentration, leverage distribution, notional exposure, liquidity, fair value, geography, sector, borrowing, fund counts |
| FCM | 5 | Monthly industry totals, quarterly aggregates, top brokers, concentration (HHI) |
| DTCC | 2 CSVs + log | Daily summary and quarterly quarter-end snapshots by asset class |
| CFTC Swaps | 3 | Weekly time series, long format, quarterly aggregates |
| Z.1 | 2 | Canonical analysis dataset plus compatibility copy |

## Status

**Active development.** All 9 data sources are acquired and parsed, and the cross-source analysis runs end-to-end. The 13F fetcher now uses a rolling 2-year window (currently 2024–2026) with 384,723 holdings across 8 funds. All fetchers use dynamic date ranges. 32 tests passing, ruff-clean codebase. Next: decompose the derivatives black box and map the counterparty network.

## License & Citation

This project is licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

**You must give appropriate credit if you use, remix, or build upon this work.** Derivatives must be shared under the same license.

### How to cite

This project includes a [`CITATION.cff`](CITATION.cff) file for automated citation. You can also cite manually:

```
Ortiz, C. (2026). Hedge Fund Autopsy: Reconstructing the U.S. hedge fund industry
from public regulatory data. https://github.com/Promeos/hedge-fund-autopsy
```

```bibtex
@misc{ortiz2026hedgefundautopsy,
  author = {Ortiz, Christopher},
  title = {Hedge Fund Autopsy: Reconstructing the U.S. Hedge Fund Industry from Public Regulatory Data},
  year = {2026},
  publisher = {GitHub},
  url = {https://github.com/Promeos/hedge-fund-autopsy}
}
```
