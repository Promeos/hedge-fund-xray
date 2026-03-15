"""End-to-end pipeline: fetch data, parse all sources, compute metrics, run analysis.

Usage:
    python -m src.pipeline              # run everything
    python -m src.pipeline --fetch      # fetch only
    python -m src.pipeline --parse      # parse only
    python -m src.pipeline --analyze    # analyze only
"""

import argparse
import os
import sys
import time

import pandas as pd
from dotenv import load_dotenv


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(ROOT_DIR, "data", "processed")


def step_fetch():
    """Fetch raw data from all external sources."""
    from fredapi import Fred
    from src.data.fetch import (
        HEDGE_FUND_CIKS,
        HEDGE_FUND_SERIES,
        fetch_all_fund_profiles,
        fetch_cftc_data,
        fetch_hedge_fund_data,
        fetch_vix_data,
        fetch_13f_holdings,
    )
    from src.data.fetch_swaps import fetch_all_swaps_reports
    from src.data.fetch_dtcc import fetch_all_dtcc_reports
    from src.data.fetch_fcm import fetch_all_fcm_reports

    load_dotenv()
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        print("ERROR: FRED_API_KEY not found in .env")
        sys.exit(1)

    fred = Fred(api_key=api_key)
    os.makedirs(RAW_DIR, exist_ok=True)

    print("[1/7] FRED — Hedge Fund Balance Sheet")
    fetch_hedge_fund_data(fred, HEDGE_FUND_SERIES,
                          cache_path=os.path.join(RAW_DIR, "hedge_fund_balance_sheet_fred.csv"))

    print("\n[2/7] FRED — VIX")
    fetch_vix_data(fred, cache_path=os.path.join(RAW_DIR, "vix_quarterly.csv"))

    print("\n[3/7] SEC EDGAR — 13F Holdings")
    holdings = []
    for fund_name, cik in HEDGE_FUND_CIKS.items():
        df = fetch_13f_holdings(cik, fund_name, cache_dir=RAW_DIR)
        if not df.empty and "value_thousands" in df.columns:
            holdings.append(df)
        time.sleep(0.2)
    if holdings:
        pd.concat(holdings, ignore_index=True).to_csv(
            os.path.join(RAW_DIR, "13f_all_holdings.csv"), index=False)

    print("\n[4/7] CFTC — Commitments of Traders")
    fetch_cftc_data(cache_path=os.path.join(RAW_DIR, "cftc_cot.csv"))

    print("\n[5/7] SEC EDGAR — Fund Profiles")
    fetch_all_fund_profiles(cache_dir=RAW_DIR)

    print("\n[6/7] CFTC — Weekly Swaps Reports")
    fetch_all_swaps_reports()

    print("\n[7/7] DTCC + FCM Reports")
    fetch_all_dtcc_reports()
    fetch_all_fcm_reports()


def step_parse():
    """Parse all raw data into processed CSVs."""
    from src.data.parse_form_pf import parse_all_form_pf
    from src.data.parse_fcm import parse_all_fcm
    from src.data.parse_dtcc import parse_all_dtcc
    from src.data.parse_swaps import parse_all_swaps

    os.makedirs(PROCESSED_DIR, exist_ok=True)

    parsers = [
        ("Form PF", parse_all_form_pf),
        ("FCM", parse_all_fcm),
        ("DTCC", parse_all_dtcc),
        ("Swaps", parse_all_swaps),
    ]
    for i, (name, fn) in enumerate(parsers, 1):
        print(f"[{i}/{len(parsers)}] Parsing {name}")
        try:
            fn()
        except Exception as e:
            print(f"  WARNING: {name} parsing failed — {e}")


def step_analyze():
    """Compute derived metrics and run cross-source analysis."""
    from src.analysis.metrics import compute_derived_metrics
    from src.analysis.cross_source import run_full_analysis

    balance_sheet_path = os.path.join(RAW_DIR, "hedge_fund_balance_sheet_fred.csv")
    if os.path.exists(balance_sheet_path):
        print("[1/2] Computing derived metrics")
        df = pd.read_csv(balance_sheet_path, index_col=0, parse_dates=True)
        df = compute_derived_metrics(df)
        df.to_csv(os.path.join(PROCESSED_DIR, "hedge_fund_metrics.csv"))
        print(f"  Saved {len(df)} quarters to data/processed/hedge_fund_metrics.csv")
    else:
        print("[1/2] Skipped metrics — no balance sheet data found. Run --fetch first.")

    print("\n[2/2] Cross-source analysis")
    try:
        run_full_analysis(save=True)
    except Exception as e:
        print(f"  WARNING: Cross-source analysis failed — {e}")


def main():
    parser = argparse.ArgumentParser(description="Hedge Fund X-Ray pipeline")
    parser.add_argument("--fetch", action="store_true", help="Fetch raw data only")
    parser.add_argument("--parse", action="store_true", help="Parse raw data only")
    parser.add_argument("--analyze", action="store_true", help="Run analysis only")
    args = parser.parse_args()

    # If no flags, run everything
    run_all = not (args.fetch or args.parse or args.analyze)

    print("=" * 60)
    print("HEDGE FUND X-RAY PIPELINE")
    print("=" * 60)

    if run_all or args.fetch:
        print("\n>>> FETCH\n")
        step_fetch()

    if run_all or args.parse:
        print("\n>>> PARSE\n")
        step_parse()

    if run_all or args.analyze:
        print("\n>>> ANALYZE\n")
        step_analyze()

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
