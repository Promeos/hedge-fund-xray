"""Tests for src.analysis.metrics — derived metrics and statistical computations."""

import numpy as np
import pandas as pd
import pytest

from src.analysis.metrics import (
    compute_correlation_matrix,
    compute_derived_metrics,
    compute_leverage_stats,
)


# ---------------------------------------------------------------------------
# compute_derived_metrics
# ---------------------------------------------------------------------------

class TestDerivedMetrics:

    def test_leverage_ratio(self, sample_balance_sheet):
        result = compute_derived_metrics(sample_balance_sheet)
        expected = sample_balance_sheet["Total liabilities"] / sample_balance_sheet["Total net assets"]
        pd.testing.assert_series_equal(result["leverage_ratio"], expected, check_names=False)

    def test_cash_to_assets(self, sample_balance_sheet):
        result = compute_derived_metrics(sample_balance_sheet)
        df = sample_balance_sheet
        cash = df["Deposits; asset"] + df["Other cash and cash equivalents; asset"] + df["Money market fund shares; asset"]
        expected = cash / df["Total assets"]
        pd.testing.assert_series_equal(result["cash_to_assets"], expected, check_names=False)

    def test_equity_pct(self, sample_balance_sheet):
        result = compute_derived_metrics(sample_balance_sheet)
        expected = sample_balance_sheet["Corporate equities; asset"] / sample_balance_sheet["Total assets"]
        pd.testing.assert_series_equal(result["equity_pct"], expected, check_names=False)

    def test_borrowing_pcts_sum_to_one(self, sample_balance_sheet):
        """Prime brokerage + other secured + unsecured should equal 100%."""
        result = compute_derived_metrics(sample_balance_sheet)
        total = result["prime_brokerage_pct"] + result["other_secured_pct"] + result["unsecured_pct"]
        np.testing.assert_allclose(total.values, 1.0, atol=1e-10)

    def test_domestic_borrowing_sum(self, sample_balance_sheet):
        result = compute_derived_metrics(sample_balance_sheet)
        df = sample_balance_sheet
        expected = (
            df["Security repurchase agreements with domestic institutions; liability"]
            + df["Loans, secured borrowing via domestic prime brokerages; liability"]
            + df["Loans, other secured borrowing from domestic institutions; liability"]
        )
        pd.testing.assert_series_equal(result["domestic_borrowing"], expected, check_names=False)

    def test_foreign_borrowing_share_range(self, sample_balance_sheet):
        result = compute_derived_metrics(sample_balance_sheet)
        share = result["foreign_borrowing_share"].dropna()
        assert (share >= 0).all() and (share <= 1).all()

    def test_qoq_growth_first_row_is_nan(self, sample_balance_sheet):
        """First quarter has no prior quarter — growth should be NaN, not 0."""
        result = compute_derived_metrics(sample_balance_sheet)
        assert pd.isna(result["total_assets_qoq"].iloc[0])
        assert pd.isna(result["net_assets_qoq"].iloc[0])
        assert pd.isna(result["liabilities_qoq"].iloc[0])

    def test_yoy_growth_first_four_rows_nan(self, sample_balance_sheet):
        """YoY needs 4 prior quarters — first 4 should be NaN."""
        result = compute_derived_metrics(sample_balance_sheet)
        assert result["total_assets_yoy"].iloc[:4].isna().all()

    def test_leverage_change_first_row_nan(self, sample_balance_sheet):
        result = compute_derived_metrics(sample_balance_sheet)
        assert pd.isna(result["leverage_change"].iloc[0])

    def test_does_not_mutate_input(self, sample_balance_sheet):
        original = sample_balance_sheet.copy()
        compute_derived_metrics(sample_balance_sheet)
        pd.testing.assert_frame_equal(sample_balance_sheet, original)


# ---------------------------------------------------------------------------
# NaN handling (the fillna(0) fix)
# ---------------------------------------------------------------------------

class TestNaNHandling:

    def test_nan_total_assets_propagates_to_ratios(self, sample_balance_sheet_with_nans):
        """When Total assets is NaN, all asset-based ratios must be NaN."""
        result = compute_derived_metrics(sample_balance_sheet_with_nans)
        nan_row = result.loc["2020-06-30"]
        assert pd.isna(nan_row["cash_to_assets"])
        assert pd.isna(nan_row["equity_pct"])
        assert pd.isna(nan_row["debt_securities_pct"])
        assert pd.isna(nan_row["derivative_to_assets"])
        assert pd.isna(nan_row["loans_to_assets"])

    def test_partial_nan_in_borrowing_sum(self, sample_balance_sheet_with_nans):
        """One missing component should not zero out the entire sum."""
        result = compute_derived_metrics(sample_balance_sheet_with_nans)
        # Q3 2020 has NaN in one foreign component but the other two are valid
        foreign = result.loc["2020-09-30", "foreign_borrowing"]
        assert not pd.isna(foreign), "Partial sum should still produce a value"
        assert foreign > 0


# ---------------------------------------------------------------------------
# compute_leverage_stats
# ---------------------------------------------------------------------------

class TestLeverageStats:

    def test_returns_expected_keys(self, sample_balance_sheet):
        df = compute_derived_metrics(sample_balance_sheet)
        stats = compute_leverage_stats(df)
        assert "mean" in stats.index
        assert "peak_date" in stats.index
        assert "trough_date" in stats.index

    def test_peak_date_is_valid(self, sample_balance_sheet):
        df = compute_derived_metrics(sample_balance_sheet)
        stats = compute_leverage_stats(df)
        assert stats["peak_date"] in df.index


# ---------------------------------------------------------------------------
# compute_correlation_matrix
# ---------------------------------------------------------------------------

class TestCorrelationMatrix:

    def test_shape_and_symmetry(self, sample_balance_sheet):
        corr = compute_correlation_matrix(sample_balance_sheet)
        assert corr.shape[0] == corr.shape[1]
        np.testing.assert_array_almost_equal(corr.values, corr.values.T)

    def test_diagonal_is_one(self, sample_balance_sheet):
        corr = compute_correlation_matrix(sample_balance_sheet)
        diag = pd.Series(np.diag(corr.values))
        # Constant columns produce NaN correlation — only check non-NaN entries
        np.testing.assert_allclose(diag.dropna().values, 1.0)

    def test_custom_cols(self, sample_balance_sheet):
        cols = ["Total assets", "Total liabilities"]
        corr = compute_correlation_matrix(sample_balance_sheet, cols=cols)
        assert list(corr.columns) == cols

    def test_missing_cols_ignored(self, sample_balance_sheet):
        cols = ["Total assets", "NONEXISTENT_COLUMN"]
        corr = compute_correlation_matrix(sample_balance_sheet, cols=cols)
        assert list(corr.columns) == ["Total assets"]
