"""Derived metrics and statistical computations for hedge fund balance sheet data."""

import pandas as pd


def compute_derived_metrics(df):
    """Compute all derived metrics from raw hedge fund balance sheet data.

    Expects a DataFrame with FRED Z.1 column names (in billions USD).
    Returns a copy with additional computed columns.
    """
    df = df.copy()

    # Key ratios
    df['leverage_ratio'] = df['Total liabilities'] / df['Total net assets']
    df['cash_to_assets'] = (
        df['Deposits; asset']
        + df['Other cash and cash equivalents; asset']
        + df['Money market fund shares; asset']
    ) / df['Total assets']
    df['equity_pct'] = df['Corporate equities; asset'] / df['Total assets']
    df['debt_securities_pct'] = df['Total debt securities; asset'] / df['Total assets']
    df['derivative_to_assets'] = df['Derivatives (long value)'] / df['Total assets']
    df['loans_to_assets'] = df['Total loans; asset'] / df['Total assets']

    # Borrowing breakdown
    total_borrowing = df['Total loans; liability']
    df['prime_brokerage_pct'] = df['Loans, total secured borrowing via prime brokerage; liability'] / total_borrowing
    df['other_secured_pct'] = df['Loans, total other secured borrowing; liability'] / total_borrowing
    df['unsecured_pct'] = df['Loans, total unsecured borrowing; liability'] / total_borrowing

    # Domestic vs foreign borrowing (fillna per-component so partial sums work)
    df['domestic_borrowing'] = (
        df['Security repurchase agreements with domestic institutions; liability'].fillna(0)
        + df['Loans, secured borrowing via domestic prime brokerages; liability'].fillna(0)
        + df['Loans, other secured borrowing from domestic institutions; liability'].fillna(0)
    )
    df['foreign_borrowing'] = (
        df['Security repurchase agreements with foreign institutions; liability'].fillna(0)
        + df['Loans, secured borrowing via foreign prime brokerages; liability'].fillna(0)
        + df['Loans, other secured borrowing from foreign institutions; liability'].fillna(0)
    )
    df['foreign_borrowing_share'] = df['foreign_borrowing'] / (df['domestic_borrowing'] + df['foreign_borrowing'])

    # Growth rates
    df['total_assets_qoq'] = df['Total assets'].pct_change()
    df['total_assets_yoy'] = df['Total assets'].pct_change(4)
    df['net_assets_qoq'] = df['Total net assets'].pct_change()
    df['liabilities_qoq'] = df['Total liabilities'].pct_change()
    df['leverage_change'] = df['leverage_ratio'].diff()

    return df


def compute_leverage_stats(df):
    """Summary statistics for leverage ratio over time."""
    stats = df['leverage_ratio'].describe()
    stats['peak_date'] = df['leverage_ratio'].idxmax()
    stats['trough_date'] = df['leverage_ratio'].idxmin()
    return stats


def compute_correlation_matrix(df, cols=None):
    """Correlation matrix among balance sheet components."""
    if cols is None:
        cols = [
            'Total assets', 'Total liabilities', 'Total net assets',
            'Corporate equities; asset', 'Total debt securities; asset',
            'Total loans; asset', 'Derivatives (long value)',
            'Security repurchase agreements; asset',
        ]
    available = [c for c in cols if c in df.columns]
    return df[available].corr()
