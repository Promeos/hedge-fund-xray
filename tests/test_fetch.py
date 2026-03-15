"""Tests for src.data.fetch — constants and offline-testable logic (no API calls)."""

import pandas as pd

from src.data.fetch import HEDGE_FUND_CIKS, HEDGE_FUND_SERIES, SEC_HEADERS


class TestConstants:

    def test_all_fred_series_ids_start_with_bogz1(self):
        """All Z.1 series IDs should follow the BOGZ1FL62* pattern."""
        for name, sid in HEDGE_FUND_SERIES.items():
            assert sid.startswith("BOGZ1FL62"), f"{name}: {sid} does not match expected prefix"

    def test_all_fred_series_are_quarterly(self):
        """Z.1 series IDs should end with 'Q' for quarterly frequency."""
        for name, sid in HEDGE_FUND_SERIES.items():
            assert sid.endswith("Q"), f"{name}: {sid} is not quarterly"

    def test_series_count(self):
        """Balance sheet should have assets + liabilities + net/memo items."""
        assert len(HEDGE_FUND_SERIES) >= 25

    def test_cik_format(self):
        """CIKs should be 10-digit zero-padded strings."""
        for fund, cik in HEDGE_FUND_CIKS.items():
            assert len(cik) == 10, f"{fund} CIK {cik} is not 10 digits"
            assert cik.isdigit(), f"{fund} CIK {cik} contains non-digits"

    def test_sec_headers_has_user_agent(self):
        assert "User-Agent" in SEC_HEADERS

    def test_expected_funds_present(self):
        expected = {"Citadel Advisors", "Bridgewater Associates", "Renaissance Technologies"}
        assert expected.issubset(set(HEDGE_FUND_CIKS.keys()))


class TestFetchHedgeFundDataCache:

    def test_loads_from_cache(self, tmp_path):
        """When cache file exists, fetch_hedge_fund_data should read it without calling FRED."""
        from src.data.fetch import fetch_hedge_fund_data

        cache_file = tmp_path / "cached.csv"
        dates = pd.date_range("2020-03-31", periods=3, freq="QE")
        df = pd.DataFrame({"Total assets": [10, 11, 12]}, index=dates)
        df.index.name = "Date"
        df.to_csv(cache_file)

        # No fred_client needed — cache should short-circuit
        result = fetch_hedge_fund_data(fred_client=None, series_map={}, cache_path=str(cache_file))
        assert len(result) == 3
        assert "Total assets" in result.columns
