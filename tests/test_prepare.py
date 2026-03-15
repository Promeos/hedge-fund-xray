"""Tests for src.data.prepare — data cleaning and type coercion."""

import numpy as np
import pandas as pd

from src.data.prepare import prep_financial_report


def test_date_parsing():
    """Date column is parsed to datetime."""
    df = pd.DataFrame({
        "id": [1, 2],
        "date": ["2020-03-31", "2020-06-30"],
        "value": ["100", "200"],
    })
    result = prep_financial_report(df)
    assert pd.api.types.is_datetime64_any_dtype(result["date"])


def test_numeric_coercion():
    """String numbers are coerced to numeric dtype."""
    df = pd.DataFrame({
        "id": [1, 2],
        "date": ["2020-03-31", "2020-06-30"],
        "value_a": ["100.5", "200.3"],
        "value_b": ["50", "60"],
    })
    result = prep_financial_report(df)
    assert pd.api.types.is_float_dtype(result["value_a"])
    assert pd.api.types.is_numeric_dtype(result["value_b"])


def test_non_numeric_becomes_nan():
    """Non-parseable strings become NaN, not raise."""
    df = pd.DataFrame({
        "id": [1, 2],
        "date": ["2020-03-31", "2020-06-30"],
        "value": ["100", "N/A"],
    })
    result = prep_financial_report(df)
    assert pd.isna(result["value"].iloc[1])


def test_nan_preserved():
    """NaN values are NOT filled with zero — critical for financial data."""
    df = pd.DataFrame({
        "id": [1, 2, 3],
        "date": ["2020-03-31", "2020-06-30", "2020-09-30"],
        "value": ["100", np.nan, "300"],
    })
    result = prep_financial_report(df)
    assert pd.isna(result["value"].iloc[1]), "NaN must not be filled with 0"


def test_returns_same_dataframe():
    """Function modifies and returns the same DataFrame (in-place semantics)."""
    df = pd.DataFrame({
        "id": [1],
        "date": ["2020-03-31"],
        "value": ["100"],
    })
    result = prep_financial_report(df)
    assert result is df
