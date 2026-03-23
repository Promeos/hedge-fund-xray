"""Cross-source reconciliation, alignment, and hypothesis testing for Hedge Fund Autopsy."""

import os
import warnings

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.stattools import adfuller, coint, grangercausalitytests

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
PROCESSED = os.path.join(DATA_DIR, "processed")
RAW = os.path.join(DATA_DIR, "raw")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "outputs", "reports")


# ---------------------------------------------------------------------------
# 1. Data loading
# ---------------------------------------------------------------------------


def load_all_sources():
    """Load all available processed CSVs into a dict of DataFrames.

    Returns dict with keys like 'z1', 'form_pf_gav', 'swaps_weekly',
    'swaps_quarterly', 'fcm', 'fcm_concentration', 'vix', 'cot',
    'form_pf_notional', 'form_pf_liquidity', 'form_pf_concentration',
    'dtcc'.  Missing files are silently skipped.
    """
    sources = {}

    file_map = {
        "z1": (PROCESSED, "hedge_fund_analysis.csv"),
        "form_pf_gav": (PROCESSED, "form_pf_gav_nav.csv"),
        "form_pf_concentration": (PROCESSED, "form_pf_concentration.csv"),
        "form_pf_leverage_dist": (PROCESSED, "form_pf_leverage_dist.csv"),
        "form_pf_notional": (PROCESSED, "form_pf_notional.csv"),
        "form_pf_liquidity": (PROCESSED, "form_pf_liquidity.csv"),
        "form_pf_strategy": (PROCESSED, "form_pf_strategy.csv"),
        "swaps_weekly": (PROCESSED, "swaps_weekly.csv"),
        "swaps_quarterly": (PROCESSED, "swaps_quarterly.csv"),
        "fcm": (PROCESSED, "fcm_quarterly.csv"),
        "fcm_monthly": (PROCESSED, "fcm_monthly_industry.csv"),
        "fcm_concentration": (PROCESSED, "fcm_concentration.csv"),
        "vix": (RAW, "vix_quarterly.csv"),
        "cot": (RAW, "cftc_cot.csv"),
        "dtcc": (PROCESSED, "dtcc_daily_summary.csv"),
    }

    for key, (directory, filename) in file_map.items():
        path = os.path.join(directory, filename)
        if os.path.exists(path):
            try:
                sources[key] = pd.read_csv(path)
            except Exception as exc:
                warnings.warn(f"Failed to load {filename}: {exc}")
        # silently skip missing files

    # Parse dates for sources that have straightforward date columns
    if "z1" in sources:
        sources["z1"]["Date"] = pd.to_datetime(sources["z1"]["Date"])
    if "vix" in sources:
        sources["vix"]["Date"] = pd.to_datetime(sources["vix"]["Date"])
    if "cot" in sources:
        sources["cot"]["date"] = pd.to_datetime(sources["cot"]["date"])
    if "swaps_weekly" in sources:
        sources["swaps_weekly"]["date"] = pd.to_datetime(sources["swaps_weekly"]["date"], errors="coerce")
    if "fcm" in sources:
        sources["fcm"]["as_of_date"] = pd.to_datetime(sources["fcm"]["as_of_date"])
    if "fcm_monthly" in sources:
        sources["fcm_monthly"]["as_of_date"] = pd.to_datetime(sources["fcm_monthly"]["as_of_date"])
    if "fcm_concentration" in sources:
        sources["fcm_concentration"]["as_of_date"] = pd.to_datetime(sources["fcm_concentration"]["as_of_date"])
    if "dtcc" in sources:
        sources["dtcc"]["date"] = pd.to_datetime(sources["dtcc"]["date"], errors="coerce")

    print(f"Loaded {len(sources)} data sources: {list(sources.keys())}")
    return sources


# ---------------------------------------------------------------------------
# Helper: quarter string -> quarter-end Timestamp
# ---------------------------------------------------------------------------


def _quarter_str_to_timestamp(series):
    """Convert a Series of '2013Q1'-style strings to quarter-end Timestamps."""
    return pd.PeriodIndex(series, freq="Q").to_timestamp("Q")


def _dtcc_rates_cleared_column(columns):
    """Return the like-for-like DTCC rates cleared-notional column if present."""
    preferred = "dtcc_rates_cleared_notional_pct"
    if preferred in columns:
        return preferred
    fallbacks = [
        "dtcc_rates_cleared_pct",
        "dtcc_cleared_notional_pct",
        "dtcc_cleared_pct",
    ]
    for col in fallbacks:
        if col in columns:
            return col
    return None


# ---------------------------------------------------------------------------
# 2. Quarterly alignment
# ---------------------------------------------------------------------------


def align_quarterly(sources):
    """Align all sources to a common quarterly DatetimeIndex (2013Q1+).

    Parameters
    ----------
    sources : dict
        Output of load_all_sources().

    Returns
    -------
    pd.DataFrame
        Unified quarterly DataFrame with a DatetimeIndex named 'date'.
    """
    frames = {}

    # --- Z.1 ---
    if "z1" in sources:
        z1 = sources["z1"].copy()
        z1 = z1[z1["Date"] >= "2012-01-01"].copy()
        # Normalize to quarter-end so joins match other sources
        z1["Date"] = z1["Date"].dt.to_period("Q").dt.to_timestamp("Q")
        z1 = z1.set_index("Date")
        z1.index.name = "date"
        # Prefix to avoid column collisions
        keep_cols = [
            "Total assets",
            "Total liabilities",
            "Total net assets",
            "Derivatives (long value)",
            "leverage_ratio",
            "leverage_change",
            "total_assets_qoq",
            "total_assets_yoy",
        ]
        available = [c for c in keep_cols if c in z1.columns]
        z1_aligned = z1[available].copy()
        z1_aligned.columns = ["z1_" + c for c in z1_aligned.columns]
        frames["z1"] = z1_aligned

    # --- Form PF GAV/NAV ---
    if "form_pf_gav" in sources:
        fpf = sources["form_pf_gav"].copy()
        fpf = fpf[fpf["fund_type"] == "Hedge Fund"].copy()
        fpf["date"] = _quarter_str_to_timestamp(fpf["quarter"])
        fpf = fpf.set_index("date")[["gav", "nav", "gav_nav_ratio"]]
        fpf.columns = ["pf_gav", "pf_nav", "pf_gav_nav_ratio"]
        frames["form_pf"] = fpf

    # --- Swaps quarterly ---
    if "swaps_quarterly" in sources:
        sq = sources["swaps_quarterly"].copy()
        sq["date"] = _quarter_str_to_timestamp(sq["quarter"])
        sq = sq.set_index("date")
        swap_cols = [
            "ir_total",
            "ir_cleared",
            "ir_uncleared",
            "credit_total",
            "credit_cleared",
            "credit_uncleared",
            "fx_total",
            "fx_cleared",
            "fx_uncleared",
            "ir_cleared_pct",
            "credit_cleared_pct",
            "fx_cleared_pct",
        ]
        available = [c for c in swap_cols if c in sq.columns]
        sq_aligned = sq[available].copy()
        sq_aligned.columns = ["swap_" + c for c in sq_aligned.columns]
        frames["swaps"] = sq_aligned

    # --- FCM quarterly ---
    if "fcm" in sources:
        fcm = sources["fcm"].copy()
        # Normalize to quarter-end
        fcm["as_of_date"] = fcm["as_of_date"].dt.to_period("Q").dt.to_timestamp("Q")
        fcm = fcm.set_index("as_of_date")
        fcm.index.name = "date"
        fcm_cols = [
            "adj_net_capital",
            "excess_net_capital",
            "customer_assets_seg",
            "cleared_swap_seg",
            "fcm_count",
            "capital_adequacy_ratio",
            "excess_capital_pct",
            "swap_seg_share",
        ]
        available = [c for c in fcm_cols if c in fcm.columns]
        fcm_aligned = fcm[available].copy()
        # Convert from raw USD to billions
        usd_cols = [
            "adj_net_capital",
            "excess_net_capital",
            "customer_assets_seg",
            "cleared_swap_seg",
        ]
        for c in usd_cols:
            if c in fcm_aligned.columns:
                fcm_aligned[c] = fcm_aligned[c] / 1e9
        fcm_aligned.columns = ["fcm_" + c for c in fcm_aligned.columns]
        frames["fcm"] = fcm_aligned

    # --- FCM concentration ---
    if "fcm_concentration" in sources:
        fcc = sources["fcm_concentration"].copy()
        fcc = fcc.set_index("as_of_date")
        fcc.index.name = "date"
        # Resample to quarter-end (take last month of each quarter)
        fcc_q = fcc.resample("QE").last().dropna(how="all")
        fcc_q.columns = ["fcm_hhi", "fcm_top5_share"]
        frames["fcm_conc"] = fcc_q

    # --- VIX ---
    if "vix" in sources:
        vix = sources["vix"].copy()
        # Normalize to quarter-end
        vix["Date"] = vix["Date"].dt.to_period("Q").dt.to_timestamp("Q")
        vix = vix.set_index("Date")
        vix.index.name = "date"
        vix.columns = ["vix_mean", "vix_max", "vix_min", "vix_end", "vix_std"]
        frames["vix"] = vix

    # --- CFTC COT ---
    if "cot" in sources:
        cot = sources["cot"].copy()
        # Aggregate to quarterly: sum net positions across all markets
        cot["quarter"] = cot["date"].dt.to_period("Q")
        cot_q = cot.groupby("quarter").agg(
            cot_lev_net=("lev_fund_net", "sum"),
            cot_lev_long=("lev_fund_long", "sum"),
            cot_lev_short=("lev_fund_short", "sum"),
        )
        cot_q.index = cot_q.index.to_timestamp("Q")
        cot_q.index.name = "date"
        frames["cot"] = cot_q

    # --- DTCC (if available) ---
    if "dtcc" in sources:
        dtcc = sources["dtcc"].copy()
        dtcc = dtcc.dropna(subset=["date", "asset_class"]).copy()
        dtcc = dtcc.sort_values(["date", "asset_class"])
        dtcc = dtcc.drop_duplicates(subset=["date", "asset_class"], keep="last")
        if "cleared_notional_pct" not in dtcc.columns and {"cleared_notional_bn", "total_notional_bn"}.issubset(
            dtcc.columns
        ):
            dtcc["cleared_notional_pct"] = dtcc["cleared_notional_bn"] / dtcc["total_notional_bn"]

        dtcc["quarter"] = dtcc["date"].dt.to_period("Q")
        dtcc_last = dtcc.groupby(["quarter", "asset_class"], as_index=False).last()
        dtcc_last["date"] = dtcc_last["quarter"].dt.to_timestamp("Q")
        pivot_cols = [
            "trade_count",
            "total_notional_bn",
            "usd_notional_bn",
            "cleared_count",
            "cleared_notional_bn",
            "uncleared_notional_bn",
            "cleared_pct",
            "cleared_notional_pct",
            "pb_pct",
            "block_pct",
        ]
        available = [c for c in pivot_cols if c in dtcc_last.columns]
        dtcc_frames = []
        for col in available:
            pivot = dtcc_last.pivot(index="date", columns="asset_class", values=col)
            pivot.columns = [f"dtcc_{str(asset).lower()}_{col}" for asset in pivot.columns]
            dtcc_frames.append(pivot)
        if dtcc_frames:
            dtcc_aligned = dtcc_frames[0]
            for frame in dtcc_frames[1:]:
                dtcc_aligned = dtcc_aligned.join(frame, how="outer")
            dtcc_aligned.index.name = "date"
            frames["dtcc"] = dtcc_aligned

    if not frames:
        raise ValueError("No data sources could be loaded or aligned.")

    # Outer join all frames on quarterly date index
    aligned = frames[list(frames.keys())[0]]
    for key in list(frames.keys())[1:]:
        aligned = aligned.join(frames[key], how="outer")

    # Filter to 2013Q1+
    aligned = aligned[aligned.index >= "2013-01-01"].copy()
    aligned = aligned.sort_index()

    print(
        f"Aligned quarterly dataset: {aligned.shape[0]} quarters, "
        f"{aligned.shape[1]} columns, "
        f"{aligned.index.min().date()} to {aligned.index.max().date()}"
    )
    return aligned


# ---------------------------------------------------------------------------
# 3. Reconciliation: Z.1 vs Form PF
# ---------------------------------------------------------------------------


def reconcile_z1_formpf(aligned):
    """Compare Z.1 total assets vs Form PF GAV.

    Returns dict with ratio statistics and leverage comparison.
    """
    result = {"source": "Z.1 vs Form PF", "tests": []}

    cols_needed = ["z1_Total assets", "pf_gav"]
    if not all(c in aligned.columns for c in cols_needed):
        result["error"] = "Missing z1_Total assets or pf_gav columns"
        return result

    overlap = aligned[cols_needed].dropna()
    if overlap.empty:
        result["error"] = "No overlapping observations"
        return result

    ratio = overlap["pf_gav"] / overlap["z1_Total assets"]
    result["asset_ratio"] = {
        "description": "Form PF GAV / Z.1 Total Assets",
        "mean": float(ratio.mean()),
        "std": float(ratio.std()),
        "min": float(ratio.min()),
        "max": float(ratio.max()),
        "n_obs": int(len(ratio)),
    }

    # Trend in ratio (simple OLS slope)
    x = np.arange(len(ratio))
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, ratio.values)
    result["asset_ratio"]["trend_slope"] = float(slope)
    result["asset_ratio"]["trend_p_value"] = float(p_value)
    result["asset_ratio"]["trend_r_squared"] = float(r_value**2)

    # Leverage comparison
    lev_cols = ["z1_leverage_ratio", "pf_gav_nav_ratio"]
    if all(c in aligned.columns for c in lev_cols):
        lev_overlap = aligned[lev_cols].dropna()
        if not lev_overlap.empty:
            corr, corr_p = stats.pearsonr(
                lev_overlap["z1_leverage_ratio"],
                lev_overlap["pf_gav_nav_ratio"],
            )
            result["leverage_comparison"] = {
                "description": "Z.1 leverage ratio vs Form PF GAV/NAV ratio",
                "correlation": float(corr),
                "correlation_p_value": float(corr_p),
                "z1_leverage_mean": float(lev_overlap["z1_leverage_ratio"].mean()),
                "pf_gav_nav_mean": float(lev_overlap["pf_gav_nav_ratio"].mean()),
                "n_obs": int(len(lev_overlap)),
            }

    print(
        f"Z.1 vs Form PF reconciliation: ratio mean={result['asset_ratio']['mean']:.3f}, "
        f"std={result['asset_ratio']['std']:.3f}"
    )
    return result


# ---------------------------------------------------------------------------
# 4. Reconciliation: CFTC vs DTCC
# ---------------------------------------------------------------------------


def reconcile_cftc_dtcc(aligned):
    """Compare CFTC and DTCC cleared percentages if both are available."""
    result = {"source": "CFTC vs DTCC"}

    dtcc_cleared_col = _dtcc_rates_cleared_column(aligned.columns)
    cftc_col = "swap_ir_cleared_pct" if "swap_ir_cleared_pct" in aligned.columns else None

    if dtcc_cleared_col is None or cftc_col is None:
        result["error"] = "Insufficient data: need DTCC rates cleared-notional and CFTC IR cleared percentage columns"
        return result

    overlap = aligned[[cftc_col, dtcc_cleared_col]].dropna()
    if overlap.empty:
        result["error"] = "No overlapping observations"
        return result

    diff = overlap[cftc_col] - overlap[dtcc_cleared_col]
    result["cleared_pct_diff"] = {
        "description": f"{cftc_col} minus {dtcc_cleared_col}",
        "mean_diff": float(diff.mean()),
        "std_diff": float(diff.std()),
        "n_obs": int(len(diff)),
    }
    corr, corr_p = stats.pearsonr(overlap[cftc_col], overlap[dtcc_cleared_col])
    result["correlation"] = float(corr)
    result["correlation_p_value"] = float(corr_p)

    print(f"CFTC vs DTCC reconciliation: mean diff={diff.mean():.4f}, corr={corr:.3f}")
    return result


# ---------------------------------------------------------------------------
# 5. Cross-source derived metrics
# ---------------------------------------------------------------------------


def compute_cross_metrics(aligned):
    """Compute cross-source derived metrics and append to aligned DataFrame.

    Returns a copy of aligned with additional columns.
    """
    df = aligned.copy()

    # Off-balance-sheet ratio: Form PF GAV / Z.1 total assets
    if "pf_gav" in df.columns and "z1_Total assets" in df.columns:
        df["off_balance_sheet_ratio"] = df["pf_gav"] / df["z1_Total assets"]

    # Implied leverage gap: Form PF GAV/NAV minus Z.1 leverage ratio
    if "pf_gav_nav_ratio" in df.columns and "z1_leverage_ratio" in df.columns:
        df["implied_leverage_gap"] = df["pf_gav_nav_ratio"] - df["z1_leverage_ratio"]

    # Clearing consistency: DTCC cleared % vs swap IR cleared %
    dtcc_cleared_col = _dtcc_rates_cleared_column(df.columns)
    if dtcc_cleared_col and "swap_ir_cleared_pct" in df.columns:
        df["clearing_consistency"] = df[dtcc_cleared_col] - df["swap_ir_cleared_pct"]

    new_cols = [c for c in df.columns if c not in aligned.columns]
    print(f"Computed {len(new_cols)} cross-source metrics: {new_cols}")
    return df


# ---------------------------------------------------------------------------
# 6. Hypothesis tests
# ---------------------------------------------------------------------------


def _make_result(test_id, description, statistic=np.nan, p_value=np.nan, interpretation="", alpha=0.05):
    """Build a standardised test-result dict."""
    if np.isnan(p_value):
        result_str = "N/A"
    else:
        result_str = "PASS" if p_value < alpha else "FAIL"
    return {
        "test_id": test_id,
        "description": description,
        "statistic": float(statistic) if not np.isnan(statistic) else np.nan,
        "p_value": float(p_value) if not np.isnan(p_value) else np.nan,
        "result": result_str,
        "interpretation": interpretation,
    }


def test_adf_stationarity(series, name="series"):
    """Generic ADF stationarity test wrapper.

    Returns dict with test_name, statistic, p_value, interpretation.
    """
    try:
        clean = series.dropna()
        if len(clean) < 8:
            return _make_result(
                "ADF",
                f"ADF stationarity: {name}",
                interpretation="Insufficient data (< 8 obs)",
            )
        result = adfuller(clean, autolag="AIC")
        adf_stat, p_val = result[0], result[1]
        interp = f"Stationary at 5% (ADF={adf_stat:.3f})" if p_val < 0.05 else f"Non-stationary (ADF={adf_stat:.3f})"
        return _make_result(
            "ADF", f"ADF stationarity: {name}", statistic=adf_stat, p_value=p_val, interpretation=interp
        )
    except Exception as exc:
        return _make_result("ADF", f"ADF stationarity: {name}", interpretation=f"Error: {exc}")


def test_mann_kendall(series, name="series"):
    """Mann-Kendall trend test using scipy.stats.kendalltau.

    Correlates the series values against their integer index.
    """
    try:
        clean = series.dropna()
        if len(clean) < 8:
            return _make_result(
                "MK",
                f"Mann-Kendall trend: {name}",
                interpretation="Insufficient data (< 8 obs)",
            )
        x = np.arange(len(clean))
        tau, p_val = stats.kendalltau(x, clean.values)
        if p_val < 0.05:
            direction = "increasing" if tau > 0 else "decreasing"
            interp = f"Significant {direction} trend (tau={tau:.3f})"
        else:
            interp = f"No significant trend (tau={tau:.3f})"
        return _make_result("MK", f"Mann-Kendall trend: {name}", statistic=tau, p_value=p_val, interpretation=interp)
    except Exception as exc:
        return _make_result("MK", f"Mann-Kendall trend: {name}", interpretation=f"Error: {exc}")


def test_h1_cointegration(aligned):
    """H1: Engle-Granger cointegration of Z.1 total assets and Form PF GAV."""
    test_id = "H1"
    desc = "Cointegration: Z.1 total assets ~ Form PF GAV"
    try:
        cols = ["z1_Total assets", "pf_gav"]
        if not all(c in aligned.columns for c in cols):
            return _make_result(test_id, desc, interpretation="Missing columns")
        overlap = aligned[cols].dropna()
        if len(overlap) < 10:
            return _make_result(test_id, desc, interpretation="Insufficient data (< 10 obs)")
        coint_stat, p_val, crit_values = coint(
            overlap["z1_Total assets"],
            overlap["pf_gav"],
        )
        interp = "Cointegrated at 5%" if p_val < 0.05 else "Not cointegrated at 5%"
        return _make_result(test_id, desc, statistic=coint_stat, p_value=p_val, interpretation=interp)
    except Exception as exc:
        return _make_result(test_id, desc, interpretation=f"Error: {exc}")


def test_h2_ratio_stability(aligned):
    """H2: Is the Z.1/Form PF GAV ratio stationary? (ADF test)."""
    test_id = "H2"
    desc = "Ratio stability: Z.1 total assets / Form PF GAV"
    try:
        cols = ["z1_Total assets", "pf_gav"]
        if not all(c in aligned.columns for c in cols):
            return _make_result(test_id, desc, interpretation="Missing columns")
        overlap = aligned[cols].dropna()
        if len(overlap) < 10:
            return _make_result(test_id, desc, interpretation="Insufficient data")
        ratio = overlap["z1_Total assets"] / overlap["pf_gav"]
        adf_result = adfuller(ratio, autolag="AIC")
        adf_stat, p_val = adf_result[0], adf_result[1]
        interp = (
            "Ratio is stationary (stable relationship)"
            if p_val < 0.05
            else "Ratio is non-stationary (relationship drifts)"
        )
        r = _make_result(test_id, desc, statistic=adf_stat, p_value=p_val, interpretation=interp)
        r["ratio_mean"] = float(ratio.mean())
        r["ratio_std"] = float(ratio.std())
        return r
    except Exception as exc:
        return _make_result(test_id, desc, interpretation=f"Error: {exc}")


def test_h3_cleared_pct_equivalence(aligned):
    """H3: TOST equivalence test — CFTC and DTCC cleared % within 10pp."""
    test_id = "H3"
    desc = "Equivalence: CFTC vs DTCC cleared % (10pp margin)"
    try:
        dtcc_col = _dtcc_rates_cleared_column(aligned.columns)
        swap_col = "swap_ir_cleared_pct"
        if dtcc_col is None or swap_col not in aligned.columns:
            return _make_result(test_id, desc, interpretation="Missing DTCC or swap cleared pct data")
        overlap = aligned[[swap_col, dtcc_col]].dropna()
        if len(overlap) < 5:
            return _make_result(test_id, desc, interpretation="Insufficient data")

        diff = overlap[swap_col] - overlap[dtcc_col]
        margin = 0.10  # 10 percentage points
        mean_diff = diff.mean()
        se = diff.std() / np.sqrt(len(diff))
        n = len(diff)

        # Two one-sided t-tests (TOST)
        t_upper = (mean_diff - margin) / se
        t_lower = (mean_diff + margin) / se
        p_upper = stats.t.cdf(t_upper, df=n - 1)
        p_lower = 1 - stats.t.cdf(t_lower, df=n - 1)
        p_tost = max(p_upper, p_lower)

        interp = "Equivalent within 10pp" if p_tost < 0.05 else "Cannot confirm equivalence within 10pp"
        r = _make_result(test_id, desc, statistic=mean_diff, p_value=p_tost, interpretation=interp)
        r["mean_diff"] = float(mean_diff)
        r["margin"] = margin
        return r
    except Exception as exc:
        return _make_result(test_id, desc, interpretation=f"Error: {exc}")


def test_h4_leverage_granger(aligned):
    """H4: Granger causality — Form PF GAV/NAV ratio -> Z.1 leverage."""
    test_id = "H4"
    desc = "Granger causality: Form PF GAV/NAV -> Z.1 leverage"
    try:
        cols = ["z1_leverage_ratio", "pf_gav_nav_ratio"]
        if not all(c in aligned.columns for c in cols):
            return _make_result(test_id, desc, interpretation="Missing columns")
        overlap = aligned[cols].dropna()
        if len(overlap) < 12:
            return _make_result(test_id, desc, interpretation="Insufficient data (< 12 obs)")

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            gc_results = grangercausalitytests(
                overlap[["z1_leverage_ratio", "pf_gav_nav_ratio"]],
                maxlag=4,
                verbose=False,
            )

        # Extract minimum p-value across lags
        min_p = 1.0
        best_lag = 1
        for lag, result in gc_results.items():
            p = result[0]["ssr_ftest"][1]
            if p < min_p:
                min_p = p
                best_lag = lag

        f_stat = gc_results[best_lag][0]["ssr_ftest"][0]
        interp = (
            f"Granger-causal at lag {best_lag} (F={f_stat:.2f})"
            if min_p < 0.05
            else f"No Granger causality (best lag={best_lag})"
        )
        return _make_result(test_id, desc, statistic=f_stat, p_value=min_p, interpretation=interp)
    except Exception as exc:
        return _make_result(test_id, desc, interpretation=f"Error: {exc}")


def test_h5_fcm_leads_cot(aligned):
    """H5: Cross-correlation of FCM customer seg growth vs COT net positioning growth."""
    test_id = "H5"
    desc = "Cross-corr: FCM customer seg growth vs COT net growth"
    try:
        fcm_col = "fcm_customer_assets_seg"
        cot_col = "cot_lev_net"
        if fcm_col not in aligned.columns or cot_col not in aligned.columns:
            return _make_result(test_id, desc, interpretation="Missing FCM or COT columns")
        overlap = aligned[[fcm_col, cot_col]].dropna()
        if len(overlap) < 8:
            return _make_result(test_id, desc, interpretation="Insufficient data")

        fcm_growth = overlap[fcm_col].pct_change().dropna()
        cot_growth = overlap[cot_col].pct_change().replace([np.inf, -np.inf], np.nan).dropna()

        common_idx = fcm_growth.index.intersection(cot_growth.index)
        if len(common_idx) < 6:
            return _make_result(test_id, desc, interpretation="Insufficient overlapping growth data")

        fcm_g = fcm_growth.loc[common_idx]
        cot_g = cot_growth.loc[common_idx]

        # Cross-correlation at lags -4 to +4
        max_corr = 0.0
        best_lag = 0
        for lag in range(-4, 5):
            if lag > 0:
                a = fcm_g.iloc[lag:]
                b = cot_g.iloc[:-lag] if lag < len(cot_g) else pd.Series(dtype=float)
            elif lag < 0:
                a = fcm_g.iloc[:lag]
                b = cot_g.iloc[-lag:]
            else:
                a = fcm_g
                b = cot_g
            if len(a) < 4 or len(b) < 4 or len(a) != len(b):
                continue
            c, _ = stats.pearsonr(a.values, b.values)
            if abs(c) > abs(max_corr):
                max_corr = c
                best_lag = lag

        # Significance of best-lag correlation
        n = len(common_idx) - abs(best_lag)
        if n > 3:
            t_stat = max_corr * np.sqrt((n - 2) / (1 - max_corr**2 + 1e-10))
            p_val = 2 * stats.t.sf(abs(t_stat), df=n - 2)
        else:
            p_val = np.nan

        direction = "FCM leads COT" if best_lag > 0 else ("COT leads FCM" if best_lag < 0 else "Contemporaneous")
        interp = (
            f"{direction} by {abs(best_lag)}Q (r={max_corr:.3f})"
            if not np.isnan(p_val) and p_val < 0.05
            else f"No significant lead-lag (best lag={best_lag}, r={max_corr:.3f})"
        )
        return _make_result(test_id, desc, statistic=max_corr, p_value=p_val, interpretation=interp)
    except Exception as exc:
        return _make_result(test_id, desc, interpretation=f"Error: {exc}")


def test_h6_liquidity_vix(sources):
    """H6: Does Form PF liquidity mismatch worsen when VIX > 30?

    Uses raw form_pf_liquidity.csv and vix data.
    """
    test_id = "H6"
    desc = "Event study: Form PF liquidity mismatch vs VIX > 30"
    try:
        if "form_pf_liquidity" not in sources or "vix" not in sources:
            return _make_result(test_id, desc, interpretation="Missing liquidity or VIX data")

        liq = sources["form_pf_liquidity"].copy()
        vix = sources["vix"].copy()

        # Compute liquidity mismatch per quarter:
        # investor liquidity at 30d minus portfolio liquidity at 30d
        inv = liq[(liq["liquidity_type"] == "investor_liquidity") & (liq["period"] == "At most 30 days")].copy()
        port = liq[(liq["liquidity_type"] == "portfolio_liquidity") & (liq["period"] == "At most 30 days")].copy()

        if inv.empty or port.empty:
            return _make_result(test_id, desc, interpretation="Could not compute liquidity mismatch")

        inv["date"] = _quarter_str_to_timestamp(inv["quarter"])
        port["date"] = _quarter_str_to_timestamp(port["quarter"])

        inv = inv.set_index("date")["cumulative_pct"]
        port = port.set_index("date")["cumulative_pct"]

        mismatch = inv - port  # positive = investors can redeem faster than portfolio liquidates
        mismatch = mismatch.dropna()
        mismatch.name = "liquidity_mismatch"

        # VIX: identify high-VIX quarters
        if "Date" not in vix.columns:
            vix = vix.reset_index()
        vix = vix.set_index("Date") if "Date" in vix.columns else vix
        if "VIX_max" not in vix.columns:
            vix_col = [c for c in vix.columns if "max" in c.lower()]
            if not vix_col:
                return _make_result(test_id, desc, interpretation="Cannot identify VIX max column")
            vix_max = vix[vix_col[0]]
        else:
            vix_max = vix["VIX_max"] if "VIX_max" in vix.columns else vix["vix_max"]

        high_vix_dates = vix_max[vix_max > 30].index
        low_vix_dates = vix_max[vix_max <= 30].index

        high_mismatch = mismatch[mismatch.index.isin(high_vix_dates)]
        low_mismatch = mismatch[mismatch.index.isin(low_vix_dates)]

        if len(high_mismatch) < 2 or len(low_mismatch) < 2:
            return _make_result(
                test_id,
                desc,
                interpretation=f"Insufficient high-VIX ({len(high_mismatch)}) or "
                f"low-VIX ({len(low_mismatch)}) quarters",
            )

        t_stat, p_val = stats.ttest_ind(high_mismatch, low_mismatch, equal_var=False)
        interp = (
            f"30-day liquidity gap is higher in high-VIX quarters "
            f"(high={high_mismatch.mean():.3f}, low={low_mismatch.mean():.3f})"
            if p_val < 0.05
            else f"No significant difference (high={high_mismatch.mean():.3f}, low={low_mismatch.mean():.3f})"
        )
        return _make_result(test_id, desc, statistic=t_stat, p_value=p_val, interpretation=interp)
    except Exception as exc:
        return _make_result(test_id, desc, interpretation=f"Error: {exc}")


def test_h7_concentration_correlation(sources):
    """H7: Spearman rank correlation between 13F and Form PF concentration."""
    test_id = "H7"
    desc = "Spearman corr: 13F vs Form PF top-fund concentration"
    try:
        if "form_pf_concentration" not in sources:
            return _make_result(test_id, desc, interpretation="Missing Form PF concentration data")

        conc = sources["form_pf_concentration"].copy()

        # Use Top 10 nav_share as the Form PF concentration measure
        top10 = conc[conc["top_n"] == "Top 10"].copy()
        if top10.empty:
            return _make_result(test_id, desc, interpretation="No Top 10 data in Form PF concentration")

        top10["date"] = _quarter_str_to_timestamp(top10["quarter"])
        top10 = top10.set_index("date").sort_index()

        # Check for 13F concentration data
        thirteenf_path = os.path.join(RAW, "13f_all_holdings.csv")
        if not os.path.exists(thirteenf_path):
            # Fall back: test trend in Form PF concentration alone
            tau, p_val = stats.kendalltau(
                np.arange(len(top10)),
                top10["nav_share"].values,
            )
            interp = (
                f"Form PF concentration trend: tau={tau:.3f} (no 13F concentration available for cross-source test)"
            )
            return _make_result(test_id, desc, statistic=tau, p_value=p_val, interpretation=interp)

        # If 13F data exists, compute HHI per quarter from holdings
        holdings = pd.read_csv(thirteenf_path)
        if "value" in holdings.columns:
            holdings["holding_value"] = holdings["value"]
        elif "value_thousands" in holdings.columns:
            holdings["holding_value"] = holdings["value_thousands"] * 1000
        else:
            return _make_result(test_id, desc, interpretation="13F holdings file lacks value columns")

        if "quarter" not in holdings.columns:
            if "report_period" in holdings.columns:
                holdings["quarter"] = holdings["report_period"]
            elif "filing_date" in holdings.columns:
                holdings["quarter"] = pd.to_datetime(holdings["filing_date"]).dt.to_period("Q").astype(str)
            else:
                return _make_result(test_id, desc, interpretation="13F holdings file lacks quarter columns")

        # HHI by quarter from 13F
        hhi_13f = []
        for q, grp in holdings.groupby("quarter"):
            total = grp["holding_value"].sum()
            if total > 0:
                shares = grp["holding_value"] / total
                hhi = (shares**2).sum()
                hhi_13f.append({"quarter": q, "hhi_13f": hhi})

        if not hhi_13f:
            return _make_result(test_id, desc, interpretation="Could not compute 13F HHI")

        hhi_df = pd.DataFrame(hhi_13f)
        hhi_df["date"] = _quarter_str_to_timestamp(hhi_df["quarter"])
        hhi_df = hhi_df.set_index("date")

        merged = top10[["nav_share"]].join(hhi_df[["hhi_13f"]], how="inner")
        if len(merged) < 4:
            return _make_result(test_id, desc, interpretation="Insufficient overlapping quarters")

        rho, p_val = stats.spearmanr(merged["nav_share"], merged["hhi_13f"])
        interp = (
            f"Significant correlation (rho={rho:.3f})"
            if p_val < 0.05
            else f"No significant correlation (rho={rho:.3f})"
        )
        return _make_result(test_id, desc, statistic=rho, p_value=p_val, interpretation=interp)
    except Exception as exc:
        return _make_result(test_id, desc, interpretation=f"Error: {exc}")


def test_h8_vix_granger_leverage(aligned):
    """H8: Granger causality — VIX -> Z.1 leverage change."""
    test_id = "H8"
    desc = "Granger causality: VIX -> Z.1 leverage change"
    try:
        cols = ["z1_leverage_change", "vix_mean"]
        if not all(c in aligned.columns for c in cols):
            # Try alternate column names
            alt = ["z1_leverage_ratio", "vix_mean"]
            if not all(c in aligned.columns for c in alt):
                return _make_result(test_id, desc, interpretation="Missing VIX or leverage columns")
            # Use leverage diff
            test_data = aligned[alt].dropna().copy()
            test_data["z1_leverage_change"] = test_data["z1_leverage_ratio"].diff()
            test_data = test_data[["z1_leverage_change", "vix_mean"]].dropna()
        else:
            test_data = aligned[cols].dropna()

        if len(test_data) < 12:
            return _make_result(test_id, desc, interpretation="Insufficient data (< 12 obs)")

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            gc_results = grangercausalitytests(
                test_data[["z1_leverage_change", "vix_mean"]],
                maxlag=4,
                verbose=False,
            )

        min_p = 1.0
        best_lag = 1
        for lag, result in gc_results.items():
            p = result[0]["ssr_ftest"][1]
            if p < min_p:
                min_p = p
                best_lag = lag

        f_stat = gc_results[best_lag][0]["ssr_ftest"][0]
        interp = (
            f"VIX Granger-causes leverage change at lag {best_lag} (F={f_stat:.2f})"
            if min_p < 0.05
            else f"No Granger causality (best lag={best_lag})"
        )
        return _make_result(test_id, desc, statistic=f_stat, p_value=min_p, interpretation=interp)
    except Exception as exc:
        return _make_result(test_id, desc, interpretation=f"Error: {exc}")


# ---------------------------------------------------------------------------
# 7. Run all tests
# ---------------------------------------------------------------------------


def run_all_tests(aligned, sources):
    """Execute all hypothesis tests and return a summary DataFrame.

    Columns: test_id, description, statistic, p_value, result, interpretation.
    """
    tests = [
        test_h1_cointegration(aligned),
        test_h2_ratio_stability(aligned),
        test_h3_cleared_pct_equivalence(aligned),
        test_h4_leverage_granger(aligned),
        test_h5_fcm_leads_cot(aligned),
        test_h6_liquidity_vix(sources),
        test_h7_concentration_correlation(sources),
        test_h8_vix_granger_leverage(aligned),
    ]

    # Also run ADF and Mann-Kendall on key series
    key_series = {
        "z1_leverage_ratio": "Z.1 leverage ratio",
        "pf_gav": "Form PF GAV",
        "pf_gav_nav_ratio": "Form PF GAV/NAV ratio",
        "vix_mean": "VIX mean",
        "cot_lev_net": "CFTC leveraged fund net",
    }
    for col, label in key_series.items():
        if col in aligned.columns:
            tests.append(test_adf_stationarity(aligned[col], label))
            tests.append(test_mann_kendall(aligned[col], label))

    # Standardise to DataFrame
    summary_cols = ["test_id", "description", "statistic", "p_value", "result", "interpretation"]
    rows = []
    for t in tests:
        rows.append({k: t.get(k, "") for k in summary_cols})

    df = pd.DataFrame(rows)
    print(f"\n{'=' * 80}")
    print("HYPOTHESIS TEST SUMMARY")
    print(f"{'=' * 80}")
    for _, row in df.iterrows():
        p_str = f"p={row['p_value']:.4f}" if not np.isnan(row["p_value"]) else "p=N/A"
        print(f"  [{row['result']:>4s}] {row['test_id']:>4s}: {row['description'][:55]:<55s} {p_str}")
    print(f"{'=' * 80}\n")
    return df


# ---------------------------------------------------------------------------
# 8. Master orchestrator
# ---------------------------------------------------------------------------


def run_full_analysis(save=True):
    """End-to-end cross-source analysis.

    1. Load all sources
    2. Align quarterly
    3. Reconcile Z.1 vs Form PF
    4. Reconcile CFTC vs DTCC
    5. Compute cross-source metrics
    6. Run all hypothesis tests
    7. Optionally save results

    Returns dict with all results.
    """
    print("=" * 80)
    print("CROSS-SOURCE RECONCILIATION & HYPOTHESIS TESTING")
    print("=" * 80)

    # 1. Load
    sources = load_all_sources()

    # 2. Align
    aligned = align_quarterly(sources)

    # 3-4. Reconciliation
    z1_pf_recon = reconcile_z1_formpf(aligned)
    cftc_dtcc_recon = reconcile_cftc_dtcc(aligned)

    # 5. Cross-metrics
    cross_metrics = compute_cross_metrics(aligned)

    # 6. Hypothesis tests
    test_summary = run_all_tests(aligned, sources)

    results = {
        "sources": sources,
        "aligned": aligned,
        "cross_metrics": cross_metrics,
        "reconciliation": {
            "z1_vs_formpf": z1_pf_recon,
            "cftc_vs_dtcc": cftc_dtcc_recon,
        },
        "test_summary": test_summary,
    }

    # 7. Save
    if save:
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        aligned_path = os.path.join(OUTPUT_DIR, "cross_source_aligned.csv")
        aligned.to_csv(aligned_path)
        print(f"Saved aligned data to {aligned_path}")

        cross_path = os.path.join(OUTPUT_DIR, "cross_source_metrics.csv")
        cross_metrics.to_csv(cross_path)
        print(f"Saved cross-metrics to {cross_path}")

        tests_path = os.path.join(OUTPUT_DIR, "cross_source_tests.csv")
        test_summary.to_csv(tests_path, index=False)
        print(f"Saved test summary to {tests_path}")

    return results


if __name__ == "__main__":
    run_full_analysis(save=True)
