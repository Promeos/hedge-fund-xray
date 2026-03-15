"""
CFTC FCM Financial Reports Parser

Parses monthly Futures Commission Merchant financial data from Excel files.
Produces industry-level time series and per-broker breakdowns of capital
adequacy, customer segregation, and cleared swap segregation.

Data: 49 monthly files (January 2022 – January 2026), ~100-135 FCMs per month.
"""

import os
import pandas as pd
import numpy as np
import openpyxl

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'raw', 'fcm')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'processed')

# Standardized column names (FCM files have verbose headers)
COLUMN_MAP = {
    0: 'row_num',
    1: 'fcm_name',
    2: 'registered_as',
    3: 'dsro',
    4: 'as_of_date',
    5: 'adj_net_capital',
    6: 'net_capital_requirement',
    7: 'excess_net_capital',
    8: 'customer_assets_seg',
    9: 'customer_seg_required',
    10: 'excess_funds_seg',
    11: 'target_residual_seg',
    12: 'funds_section_30_7',
    13: 'customer_pt30_required',
    14: 'excess_funds_30_7',
    15: 'target_residual_30_7',
    16: 'cleared_swap_seg',
    17: 'cleared_swap_required',
    18: 'excess_cleared_swap',
    19: 'target_residual_swap',
    20: 'retail_forex_obligation',
}


def parse_single_fcm_file(filepath):
    """Parse one monthly FCM Excel file into a DataFrame."""
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    # Find the data start row (after headers — look for first numeric row_num)
    data_start = None
    for i, row in enumerate(rows):
        if row[0] is not None and isinstance(row[0], (int, float)) and row[0] >= 1:
            data_start = i
            break

    if data_start is None:
        return pd.DataFrame()

    # Extract data rows (stop at empty rows)
    data = []
    for row in rows[data_start:]:
        if row[0] is None or row[1] is None:
            continue
        # Skip if first col isn't a number (summary rows, etc.)
        try:
            int(row[0])
        except (ValueError, TypeError):
            continue
        data.append(list(row))

    if not data:
        return pd.DataFrame()

    # Build DataFrame with standardized columns
    max_cols = max(len(r) for r in data)
    col_names = [COLUMN_MAP.get(i, f'col_{i}') for i in range(max_cols)]
    df = pd.DataFrame(data, columns=col_names[:max_cols] if max_cols <= len(col_names) else col_names + [f'col_{i}' for i in range(len(col_names), max_cols)])

    # Clean up
    df = df.drop(columns=['row_num'], errors='ignore')

    # Convert monetary columns to numeric
    money_cols = [c for c in df.columns if c not in ['fcm_name', 'registered_as', 'dsro', 'as_of_date']]
    for col in money_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Parse date
    if 'as_of_date' in df.columns:
        df['as_of_date'] = pd.to_datetime(df['as_of_date'], errors='coerce')

    return df


def parse_all_fcm(data_dir=None, output_dir=None):
    """Parse all FCM monthly files and produce processed CSVs."""
    if data_dir is None:
        data_dir = DATA_DIR
    if output_dir is None:
        output_dir = OUTPUT_DIR

    os.makedirs(output_dir, exist_ok=True)

    files = sorted([f for f in os.listdir(data_dir) if f.endswith('.xlsx')])
    print(f"Parsing {len(files)} FCM monthly reports...")

    all_dfs = []
    for f in files:
        filepath = os.path.join(data_dir, f)
        df = parse_single_fcm_file(filepath)
        if not df.empty:
            all_dfs.append(df)

    if not all_dfs:
        print("No FCM data parsed!")
        return

    # --- All FCMs, all months ---
    fcm_all = pd.concat(all_dfs, ignore_index=True)
    fcm_all = fcm_all.sort_values(['as_of_date', 'fcm_name'])
    fcm_all.to_csv(os.path.join(output_dir, 'fcm_monthly_all.csv'), index=False)
    print(f"  Saved fcm_monthly_all.csv ({len(fcm_all)} rows)")

    # --- Industry totals per month ---
    money_cols = ['adj_net_capital', 'net_capital_requirement', 'excess_net_capital',
                  'customer_assets_seg', 'customer_seg_required', 'excess_funds_seg',
                  'funds_section_30_7', 'customer_pt30_required',
                  'cleared_swap_seg', 'cleared_swap_required', 'excess_cleared_swap',
                  'retail_forex_obligation']
    money_cols = [c for c in money_cols if c in fcm_all.columns]

    industry = fcm_all.groupby('as_of_date')[money_cols].sum().reset_index()
    industry['fcm_count'] = fcm_all.groupby('as_of_date')['fcm_name'].count().values

    # Derived metrics
    industry['capital_adequacy_ratio'] = industry['adj_net_capital'] / industry['net_capital_requirement']
    industry['excess_capital_pct'] = industry['excess_net_capital'] / industry['adj_net_capital']
    if 'cleared_swap_seg' in industry.columns and 'customer_assets_seg' in industry.columns:
        industry['swap_seg_share'] = industry['cleared_swap_seg'] / (
            industry['customer_assets_seg'] + industry['cleared_swap_seg'].fillna(0))

    industry.to_csv(os.path.join(output_dir, 'fcm_monthly_industry.csv'), index=False)
    print(f"  Saved fcm_monthly_industry.csv ({len(industry)} rows)")

    # --- Top brokers by customer segregated funds ---
    if 'customer_assets_seg' in fcm_all.columns:
        top_brokers = []
        for date, group in fcm_all.groupby('as_of_date'):
            total_seg = group['customer_assets_seg'].sum()
            group = group.copy()
            group['market_share_seg'] = group['customer_assets_seg'] / total_seg if total_seg > 0 else 0
            top = group.nlargest(10, 'customer_assets_seg')
            top_brokers.append(top[['as_of_date', 'fcm_name', 'adj_net_capital',
                                    'customer_assets_seg', 'market_share_seg']])

        if top_brokers:
            top_df = pd.concat(top_brokers, ignore_index=True)
            top_df.to_csv(os.path.join(output_dir, 'fcm_top_brokers.csv'), index=False)
            print(f"  Saved fcm_top_brokers.csv ({len(top_df)} rows)")

    # --- Quarterly aggregation ---
    industry['quarter'] = industry['as_of_date'].dt.to_period('Q').astype(str)
    quarterly = industry.groupby('quarter').last().reset_index()
    quarterly.to_csv(os.path.join(output_dir, 'fcm_quarterly.csv'), index=False)
    print(f"  Saved fcm_quarterly.csv ({len(quarterly)} rows)")

    # --- HHI concentration ---
    hhi_rows = []
    for date, group in fcm_all.groupby('as_of_date'):
        total_seg = group['customer_assets_seg'].sum()
        if total_seg > 0:
            shares = group['customer_assets_seg'] / total_seg
            hhi = (shares ** 2).sum()
            top5_share = group.nlargest(5, 'customer_assets_seg')['customer_assets_seg'].sum() / total_seg
            hhi_rows.append({'as_of_date': date, 'hhi': hhi, 'top5_share': top5_share})

    if hhi_rows:
        hhi_df = pd.DataFrame(hhi_rows)
        hhi_df.to_csv(os.path.join(output_dir, 'fcm_concentration.csv'), index=False)
        print(f"  Saved fcm_concentration.csv ({len(hhi_df)} rows)")

    # --- Summary ---
    latest = industry.iloc[-1]
    print(f"\nDone! {len(files)} files parsed.")
    print(f"  Latest date: {latest['as_of_date']}")
    print(f"  FCM count: {int(latest['fcm_count'])}")
    print(f"  Total adj net capital: ${latest['adj_net_capital']/1e9:.1f}B")
    print(f"  Total customer seg: ${latest['customer_assets_seg']/1e9:.1f}B")
    print(f"  Capital adequacy: {latest['capital_adequacy_ratio']:.1f}x")


if __name__ == '__main__':
    parse_all_fcm()
