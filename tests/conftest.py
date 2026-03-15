"""Shared test fixtures — tiny sample data that mirrors FRED Z.1 structure."""

import numpy as np
import pandas as pd
import pytest


# Column names matching FRED Z.1 series used throughout the pipeline
BALANCE_SHEET_COLS = [
    "Total assets",
    "Total liabilities",
    "Total net assets",
    "Deposits; asset",
    "Other cash and cash equivalents; asset",
    "Money market fund shares; asset",
    "Corporate equities; asset",
    "Total debt securities; asset",
    "Total loans; asset",
    "Derivatives (long value)",
    "Total loans; liability",
    "Loans, total secured borrowing via prime brokerage; liability",
    "Loans, total other secured borrowing; liability",
    "Loans, total unsecured borrowing; liability",
    "Security repurchase agreements with domestic institutions; liability",
    "Loans, secured borrowing via domestic prime brokerages; liability",
    "Loans, other secured borrowing from domestic institutions; liability",
    "Security repurchase agreements with foreign institutions; liability",
    "Loans, secured borrowing via foreign prime brokerages; liability",
    "Loans, other secured borrowing from foreign institutions; liability",
]


@pytest.fixture
def sample_balance_sheet():
    """5 quarters of synthetic hedge fund balance sheet data (billions USD)."""
    dates = pd.date_range("2020-03-31", periods=5, freq="QE")
    data = {
        "Total assets":       [10.0, 11.0, 12.0, 11.5, 13.0],
        "Total liabilities":  [ 7.0,  8.0,  9.0,  8.5, 10.0],
        "Total net assets":   [ 3.0,  3.0,  3.0,  3.0,  3.0],
        # Cash components
        "Deposits; asset":                            [0.5, 0.6, 0.7, 0.5, 0.8],
        "Other cash and cash equivalents; asset":     [0.3, 0.2, 0.4, 0.3, 0.5],
        "Money market fund shares; asset":            [0.2, 0.2, 0.1, 0.2, 0.2],
        # Asset breakdown
        "Corporate equities; asset":                  [4.0, 4.5, 5.0, 4.8, 5.5],
        "Total debt securities; asset":               [2.0, 2.5, 2.8, 2.7, 3.0],
        "Total loans; asset":                         [1.5, 1.5, 1.5, 1.5, 1.5],
        "Derivatives (long value)":                   [1.0, 1.0, 1.2, 1.0, 1.0],
        # Borrowing totals
        "Total loans; liability":                     [5.0, 5.5, 6.0, 5.5, 7.0],
        "Loans, total secured borrowing via prime brokerage; liability": [2.0, 2.5, 3.0, 2.5, 3.5],
        "Loans, total other secured borrowing; liability":              [2.0, 2.0, 2.0, 2.0, 2.5],
        "Loans, total unsecured borrowing; liability":                  [1.0, 1.0, 1.0, 1.0, 1.0],
        # Domestic borrowing components
        "Security repurchase agreements with domestic institutions; liability": [1.0, 1.0, 1.0, 1.0, 1.0],
        "Loans, secured borrowing via domestic prime brokerages; liability":    [1.5, 1.5, 2.0, 1.5, 2.0],
        "Loans, other secured borrowing from domestic institutions; liability": [0.5, 0.5, 0.5, 0.5, 0.5],
        # Foreign borrowing components
        "Security repurchase agreements with foreign institutions; liability":  [0.5, 0.5, 0.5, 0.5, 0.5],
        "Loans, secured borrowing via foreign prime brokerages; liability":     [0.5, 1.0, 1.0, 1.0, 1.5],
        "Loans, other secured borrowing from foreign institutions; liability":  [0.5, 0.5, 0.5, 0.5, 1.0],
    }
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def sample_balance_sheet_with_nans(sample_balance_sheet):
    """Same data but with NaN in selected cells to test missing-data handling."""
    df = sample_balance_sheet.copy()
    # Q2 2020: missing total assets (should make ratios NaN)
    df.loc["2020-06-30", "Total assets"] = np.nan
    # Q3 2020: missing one foreign borrowing component (partial sum should still work)
    df.loc["2020-09-30", "Loans, secured borrowing via foreign prime brokerages; liability"] = np.nan
    return df
