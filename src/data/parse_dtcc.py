"""
DTCC Swap Data Repository Parser

Parses daily cumulative swap reports from DTCC's Public Price Dissemination API.
Each ZIP contains a CSV with ~30K+ individual OTC derivative transactions and 110 columns.
Produces daily and quarterly summaries by asset class, clearing status, and product type.

Data: ~1,825 daily files across 5 asset classes (2025-03-13 onward).
"""

import os
import zipfile
import io
import pandas as pd
import numpy as np
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'raw', 'dtcc')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'processed')

# Columns we extract from each 110-column CSV
KEEP_COLS = [
    'Dissemination Identifier',
    'Action type',
    'Asset Class',
    'Cleared',
    'Notional amount-Leg 1',
    'Notional amount-Leg 2',
    'Notional currency-Leg 1',
    'Prime brokerage transaction indicator',
    'Block trade election indicator',
    'Platform identifier',
    'Effective Date',
    'Expiration Date',
    'Underlying Asset Name',
]


def _parse_notional(val):
    """Parse notional amount strings like '110,000,000' to float."""
    if val is None or val == '':
        return np.nan
    if isinstance(val, (int, float)):
        return float(val)
    return pd.to_numeric(str(val).replace(',', ''), errors='coerce')


def _extract_date_from_filename(filename):
    """Extract date from CFTC_CUMULATIVE_{CLASS}_{YYYY}_{MM}_{DD}.zip"""
    parts = filename.replace('.zip', '').split('_')
    try:
        year, month, day = int(parts[-3]), int(parts[-2]), int(parts[-1])
        return datetime(year, month, day)
    except (ValueError, IndexError):
        return None


def _extract_asset_class(filename):
    """Extract asset class from filename."""
    parts = filename.replace('.zip', '').split('_')
    # CFTC_CUMULATIVE_{CLASS}_{Y}_{M}_{D}
    return parts[2] if len(parts) >= 6 else 'UNKNOWN'


def parse_single_zip(filepath):
    """Parse one DTCC cumulative ZIP file and return aggregated summary."""
    filename = os.path.basename(filepath)
    date = _extract_date_from_filename(filename)
    asset_class = _extract_asset_class(filename)

    if date is None:
        return None

    try:
        with zipfile.ZipFile(filepath, 'r') as zf:
            csv_names = [n for n in zf.namelist() if n.endswith('.csv')]
            if not csv_names:
                return None

            with zf.open(csv_names[0]) as csv_file:
                # Read only the columns we need
                try:
                    df = pd.read_csv(csv_file, usecols=lambda c: c in KEEP_COLS,
                                     dtype=str, low_memory=False)
                except Exception:
                    return None

        if df.empty:
            return None

        # Parse notional amounts
        for col in ['Notional amount-Leg 1', 'Notional amount-Leg 2']:
            if col in df.columns:
                df[col] = df[col].apply(_parse_notional)

        trade_count = len(df)

        # Total notional (use Leg 1 as primary)
        notional_col = 'Notional amount-Leg 1' if 'Notional amount-Leg 1' in df.columns else None
        total_notional = df[notional_col].sum() if notional_col else 0

        # Cleared vs uncleared
        cleared_count = 0
        cleared_notional = 0
        if 'Cleared' in df.columns and notional_col:
            cleared_mask = df['Cleared'].str.upper().isin(['Y', 'I', 'TRUE'])
            cleared_count = cleared_mask.sum()
            cleared_notional = df.loc[cleared_mask, notional_col].sum()

        # Prime brokerage
        pb_count = 0
        if 'Prime brokerage transaction indicator' in df.columns:
            pb_count = df['Prime brokerage transaction indicator'].str.upper().isin(
                ['TRUE', 'Y']).sum()

        # Block trades
        block_count = 0
        if 'Block trade election indicator' in df.columns:
            block_count = df['Block trade election indicator'].str.upper().isin(
                ['TRUE', 'Y']).sum()

        # USD notional (filter to USD only for comparability)
        usd_notional = 0
        if 'Notional currency-Leg 1' in df.columns and notional_col:
            usd_mask = df['Notional currency-Leg 1'] == 'USD'
            usd_notional = df.loc[usd_mask, notional_col].sum()

        # Product breakdown (top products by notional)
        product_data = []
        if 'Underlying Asset Name' in df.columns and notional_col:
            product_groups = df.groupby('Underlying Asset Name').agg(
                trade_count=('Dissemination Identifier', 'count'),
                total_notional=(notional_col, 'sum')
            ).reset_index()
            product_groups['date'] = date
            product_groups['asset_class'] = asset_class
            product_data = product_groups

        summary = {
            'date': date,
            'asset_class': asset_class,
            'trade_count': trade_count,
            'total_notional': total_notional,
            'usd_notional': usd_notional,
            'cleared_count': cleared_count,
            'cleared_notional': cleared_notional,
            'uncleared_notional': total_notional - cleared_notional,
            'cleared_pct': cleared_count / trade_count if trade_count > 0 else 0,
            'pb_count': pb_count,
            'pb_pct': pb_count / trade_count if trade_count > 0 else 0,
            'block_count': block_count,
            'block_pct': block_count / trade_count if trade_count > 0 else 0,
        }

        return summary, product_data

    except (zipfile.BadZipFile, Exception):
        return None


def parse_all_dtcc(data_dir=None, output_dir=None):
    """Parse all DTCC cumulative ZIP files and produce processed CSVs."""
    if data_dir is None:
        data_dir = DATA_DIR
    if output_dir is None:
        output_dir = OUTPUT_DIR

    os.makedirs(output_dir, exist_ok=True)

    files = sorted([f for f in os.listdir(data_dir) if f.endswith('.zip')])
    print(f"Parsing {len(files)} DTCC cumulative reports...")

    summaries = []
    all_products = []
    failed = 0

    for i, f in enumerate(files):
        filepath = os.path.join(data_dir, f)
        result = parse_single_zip(filepath)

        if result is None:
            failed += 1
            continue

        summary, product_data = result
        summaries.append(summary)
        if isinstance(product_data, pd.DataFrame) and not product_data.empty:
            all_products.append(product_data)

        if (i + 1) % 100 == 0:
            print(f"  [{i+1}/{len(files)}] processed...")

    if not summaries:
        print("No DTCC data parsed!")
        return

    # --- Daily summary ---
    daily = pd.DataFrame(summaries)
    daily = daily.sort_values(['date', 'asset_class'])
    daily.to_csv(os.path.join(output_dir, 'dtcc_daily_summary.csv'), index=False)
    print(f"  Saved dtcc_daily_summary.csv ({len(daily)} rows)")

    # --- Product breakdown ---
    if all_products:
        products = pd.concat(all_products, ignore_index=True)
        products = products.sort_values(['date', 'asset_class', 'total_notional'], ascending=[True, True, False])
        products.to_csv(os.path.join(output_dir, 'dtcc_product_daily.csv'), index=False)
        print(f"  Saved dtcc_product_daily.csv ({len(products)} rows)")

    # --- Quarterly aggregation ---
    daily['quarter'] = pd.to_datetime(daily['date']).dt.to_period('Q').astype(str)
    quarterly = daily.groupby(['quarter', 'asset_class']).agg(
        trading_days=('date', 'count'),
        total_trades=('trade_count', 'sum'),
        avg_daily_trades=('trade_count', 'mean'),
        total_notional=('total_notional', 'sum'),
        avg_daily_notional=('total_notional', 'mean'),
        avg_cleared_pct=('cleared_pct', 'mean'),
        avg_pb_pct=('pb_pct', 'mean'),
        avg_block_pct=('block_pct', 'mean'),
    ).reset_index()
    quarterly.to_csv(os.path.join(output_dir, 'dtcc_quarterly.csv'), index=False)
    print(f"  Saved dtcc_quarterly.csv ({len(quarterly)} rows)")

    # --- Summary ---
    print(f"\nDone! {len(files)} files parsed, {failed} failed.")
    for ac in daily['asset_class'].unique():
        ac_data = daily[daily['asset_class'] == ac]
        print(f"  {ac}: {len(ac_data)} days, {ac_data['trade_count'].sum():,.0f} total trades, "
              f"avg cleared {ac_data['cleared_pct'].mean():.1%}")


if __name__ == '__main__':
    parse_all_dtcc()
