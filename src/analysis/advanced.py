"""Advanced statistical analysis for Hedge Fund Autopsy.

Granger causality matrix, Johansen cointegration, VAR impulse response,
structural break detection, Monte Carlo stress testing, and deep-dive
analyses on Form PF liquidity, strategy rotation, and FCM concentration.
"""

import os
import warnings

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.api import VAR
from statsmodels.tsa.stattools import grangercausalitytests
from statsmodels.tsa.vector_ar.vecm import coint_johansen

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
PROCESSED = os.path.join(DATA_DIR, "processed")
RAW = os.path.join(DATA_DIR, "raw")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "outputs", "reports")
FIGURES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "outputs", "figures")


def _quarter_str_to_timestamp(series):
    return pd.PeriodIndex(series, freq="Q").to_timestamp("Q")


# ---------------------------------------------------------------------------
# 1. Granger Causality Matrix
# ---------------------------------------------------------------------------


def granger_causality_matrix(aligned, variables=None, maxlag=4):
    """Pairwise Granger causality tests across multiple variables.

    Returns DataFrame of p-values (row causes column).
    """
    if variables is None:
        variables = [
            "vix_mean",
            "z1_leverage_ratio",
            "pf_gav_nav_ratio",
            "cot_lev_net",
            "swap_ir_total",
            "fcm_excess_net_capital",
        ]

    available = [v for v in variables if v in aligned.columns]
    if len(available) < 2:
        print(f"Granger matrix: only {len(available)} variables available, need >= 2")
        return pd.DataFrame()

    n = len(available)
    p_matrix = pd.DataFrame(np.nan, index=available, columns=available)
    f_matrix = pd.DataFrame(np.nan, index=available, columns=available)

    for i, cause in enumerate(available):
        for j, effect in enumerate(available):
            if i == j:
                continue
            data = aligned[[effect, cause]].dropna()
            if len(data) < maxlag + 5:
                continue
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    result = grangercausalitytests(data, maxlag=maxlag, verbose=False)
                min_p = min(result[lag][0]["ssr_ftest"][1] for lag in result)
                best_lag = min(result, key=lambda lag_k: result[lag_k][0]["ssr_ftest"][1])
                f_stat = result[best_lag][0]["ssr_ftest"][0]
                p_matrix.loc[cause, effect] = min_p
                f_matrix.loc[cause, effect] = f_stat
            except Exception:
                pass

    significant = (p_matrix < 0.05).sum().sum()
    total = n * (n - 1)
    print(f"\nGRANGER CAUSALITY MATRIX ({n} variables, maxlag={maxlag})")
    print(f"  {significant}/{total} significant pairs (p < 0.05)")
    for cause in available:
        for effect in available:
            p = p_matrix.loc[cause, effect]
            if not np.isnan(p) and p < 0.05:
                f = f_matrix.loc[cause, effect]
                print(f"  {cause} -> {effect}: p={p:.4f}, F={f:.2f}")

    return p_matrix


# ---------------------------------------------------------------------------
# 2. Johansen Cointegration
# ---------------------------------------------------------------------------


def johansen_cointegration(aligned, variables=None, det_order=0, k_ar_diff=2):
    """Johansen cointegration test for multiple time series.

    Returns dict with test statistics, critical values, and number of
    cointegrating relationships.
    """
    if variables is None:
        variables = ["z1_Total assets", "pf_gav", "pf_nav"]

    available = [v for v in variables if v in aligned.columns]
    if len(available) < 2:
        print(f"Johansen: only {len(available)} variables available, need >= 2")
        return {}

    data = aligned[available].dropna()
    if len(data) < 20:
        print(f"Johansen: only {len(data)} obs, need >= 20")
        return {}

    result = coint_johansen(data, det_order=det_order, k_ar_diff=k_ar_diff)

    # Trace test
    trace_stats = result.lr1
    trace_crit = result.cvt  # 90%, 95%, 99% columns
    max_eigen_stats = result.lr2
    max_eigen_crit = result.cvm

    n_coint_trace = sum(1 for i in range(len(trace_stats)) if trace_stats[i] > trace_crit[i, 1])  # 95% column
    n_coint_eigen = sum(1 for i in range(len(max_eigen_stats)) if max_eigen_stats[i] > max_eigen_crit[i, 1])

    print("\nJOHANSEN COINTEGRATION TEST")
    print(f"  Variables: {available}")
    print(f"  Observations: {len(data)}")
    print(f"  Trace test: {n_coint_trace} cointegrating relationship(s)")
    print(f"  Max eigenvalue test: {n_coint_eigen} cointegrating relationship(s)")
    for i in range(len(trace_stats)):
        sig = "*" if trace_stats[i] > trace_crit[i, 1] else ""
        print(f"    r<={i}: trace={trace_stats[i]:.2f}, 95% crit={trace_crit[i, 1]:.2f} {sig}")

    return {
        "variables": available,
        "n_obs": len(data),
        "n_coint_trace": n_coint_trace,
        "n_coint_eigen": n_coint_eigen,
        "trace_stats": trace_stats.tolist(),
        "trace_crit_95": trace_crit[:, 1].tolist(),
        "max_eigen_stats": max_eigen_stats.tolist(),
        "max_eigen_crit_95": max_eigen_crit[:, 1].tolist(),
        "eigenvectors": result.evec.tolist(),
    }


# ---------------------------------------------------------------------------
# 3. VAR Model + Impulse Response
# ---------------------------------------------------------------------------


def var_impulse_response(aligned, variables=None, maxlags=4, irf_periods=8):
    """Fit VAR model and compute impulse response functions.

    Returns dict with model summary, IRF data, and forecast error
    variance decomposition.
    """
    if variables is None:
        variables = ["z1_leverage_ratio", "pf_gav_nav_ratio", "vix_mean", "cot_lev_net"]

    available = [v for v in variables if v in aligned.columns]
    if len(available) < 2:
        print(f"VAR: only {len(available)} variables available, need >= 2")
        return {}

    data = aligned[available].dropna()
    if len(data) < 20:
        print(f"VAR: only {len(data)} obs, need >= 20")
        return {}

    # Standardize for comparable IRFs
    means = data.mean()
    stds = data.std()
    data_std = (data - means) / stds

    model = VAR(data_std)

    # Select lag order via AIC
    try:
        lag_order = model.select_order(maxlags=maxlags)
        best_lag = lag_order.aic
        if best_lag == 0:
            best_lag = 1
    except Exception:
        best_lag = min(2, maxlags)

    results = model.fit(best_lag)
    irf = results.irf(irf_periods)
    fevd = results.fevd(irf_periods)

    # Extract IRF data into a DataFrame
    irf_data = {}
    for i, shock_var in enumerate(available):
        for j, response_var in enumerate(available):
            key = f"{shock_var} -> {response_var}"
            irf_data[key] = irf.irfs[:, j, i]

    irf_df = pd.DataFrame(irf_data, index=range(irf_periods + 1))

    # Extract FEVD
    fevd_data = {}
    for i, var in enumerate(available):
        decomp = fevd.decomp[i]  # (periods, n_vars)
        for j, source in enumerate(available):
            fevd_data[f"{var} <- {source}"] = decomp[:, j]

    fevd_len = len(list(fevd_data.values())[0])
    fevd_df = pd.DataFrame(fevd_data, index=range(fevd_len))

    print(f"\nVAR MODEL (lag={best_lag})")
    print(f"  Variables: {available}")
    print(f"  Observations: {len(data)}")
    print(f"  AIC: {results.aic:.2f}, BIC: {results.bic:.2f}")
    print(f"\n  Impulse Response (1 std dev shock, {irf_periods} quarters):")
    for shock in available:
        responses = []
        for resp in available:
            if shock != resp:
                key = f"{shock} -> {resp}"
                peak = irf_df[key].abs().max()
                peak_q = irf_df[key].abs().idxmax()
                responses.append(f"{resp}(peak={peak:.3f} at Q{peak_q})")
        if responses:
            print(f"    Shock to {shock}: {', '.join(responses)}")

    print(f"\n  Forecast Error Variance Decomposition at Q{irf_periods}:")
    for var in available:
        parts = []
        for source in available:
            key = f"{var} <- {source}"
            pct = fevd_df[key].iloc[-1] * 100
            if pct > 5:
                parts.append(f"{source}={pct:.1f}%")
        print(f"    {var}: {', '.join(parts)}")

    return {
        "variables": available,
        "lag_order": best_lag,
        "n_obs": len(data),
        "aic": results.aic,
        "bic": results.bic,
        "irf_df": irf_df,
        "fevd_df": fevd_df,
        "means": means.to_dict(),
        "stds": stds.to_dict(),
    }


# ---------------------------------------------------------------------------
# 4. Structural Break Detection
# ---------------------------------------------------------------------------


def detect_structural_breaks(series, name="series", max_breaks=3, min_segment=8):
    """Detect structural breaks using a CUSUM-based approach with
    iterative Chow-like splitting.

    Returns list of break dates and segment statistics.
    """
    clean = series.dropna()
    if len(clean) < 2 * min_segment:
        print(f"Structural breaks ({name}): insufficient data ({len(clean)} obs)")
        return {"name": name, "breaks": [], "segments": []}

    def find_best_break(s):
        """Find the single best break point in a series using max F-stat."""
        n = len(s)
        best_f = 0
        best_idx = None
        values = s.values

        for i in range(min_segment, n - min_segment):
            seg1 = values[:i]
            seg2 = values[i:]
            ssr_full = np.sum((values - values.mean()) ** 2)
            ssr_parts = np.sum((seg1 - seg1.mean()) ** 2) + np.sum((seg2 - seg2.mean()) ** 2)
            if ssr_parts == 0:
                continue
            f_stat = ((ssr_full - ssr_parts) / 1) / (ssr_parts / (n - 2))
            if f_stat > best_f:
                best_f = f_stat
                best_idx = i

        # Approximate p-value using F distribution
        if best_idx is not None:
            p_value = 1 - stats.f.cdf(best_f, 1, n - 2)
        else:
            p_value = 1.0

        return best_idx, best_f, p_value

    breaks = []
    segments = [(0, len(clean))]

    for _ in range(max_breaks):
        best_break = None
        best_f = 0
        best_seg_idx = None

        for seg_idx, (start, end) in enumerate(segments):
            seg = clean.iloc[start:end]
            if len(seg) < 2 * min_segment:
                continue
            idx, f_stat, p_val = find_best_break(seg)
            if idx is not None and f_stat > best_f and p_val < 0.05:
                best_break = start + idx
                best_f = f_stat
                best_seg_idx = seg_idx

        if best_break is None:
            break

        breaks.append(
            {
                "index": best_break,
                "date": str(clean.index[best_break].date())
                if hasattr(clean.index[best_break], "date")
                else str(clean.index[best_break]),
                "f_stat": best_f,
            }
        )

        old_seg = segments.pop(best_seg_idx)
        segments.insert(best_seg_idx, (old_seg[0], best_break))
        segments.insert(best_seg_idx + 1, (best_break, old_seg[1]))

    # Compute segment statistics
    seg_stats = []
    for start, end in sorted(segments):
        seg = clean.iloc[start:end]
        seg_stats.append(
            {
                "start": str(seg.index[0].date()) if hasattr(seg.index[0], "date") else str(seg.index[0]),
                "end": str(seg.index[-1].date()) if hasattr(seg.index[-1], "date") else str(seg.index[-1]),
                "n_obs": len(seg),
                "mean": float(seg.mean()),
                "std": float(seg.std()),
                "min": float(seg.min()),
                "max": float(seg.max()),
            }
        )

    print(f"\nSTRUCTURAL BREAKS: {name}")
    print(f"  Found {len(breaks)} significant break(s):")
    for b in breaks:
        print(f"    {b['date']} (F={b['f_stat']:.2f})")
    for seg in seg_stats:
        print(
            f"  Segment {seg['start']} to {seg['end']}: mean={seg['mean']:.4f}, std={seg['std']:.4f}, n={seg['n_obs']}"
        )

    return {"name": name, "breaks": breaks, "segments": seg_stats}


# ---------------------------------------------------------------------------
# 5. Monte Carlo Stress Testing
# ---------------------------------------------------------------------------


def monte_carlo_stress_test(aligned, n_simulations=10000, n_quarters=8, variables=None):
    """Monte Carlo simulation of multi-variable paths using bootstrapped
    historical quarterly changes.

    Returns dict with simulated paths, VaR/CVaR at multiple confidence levels,
    and probability of exceeding historical extremes.
    """
    if variables is None:
        variables = ["z1_Total assets", "z1_Total liabilities", "z1_Total net assets"]

    available = [v for v in variables if v in aligned.columns]
    if not available:
        print("Monte Carlo: no variables available")
        return {}

    data = aligned[available].dropna()
    if len(data) < 10:
        print(f"Monte Carlo: insufficient data ({len(data)} obs)")
        return {}

    # Compute quarterly returns
    returns = data.pct_change().dropna()
    returns = returns.replace([np.inf, -np.inf], np.nan).dropna()

    current_values = data.iloc[-1]

    # Bootstrap: sample with replacement from historical returns
    rng = np.random.default_rng(42)
    sim_indices = rng.choice(len(returns), size=(n_simulations, n_quarters))

    results = {}
    for i, var in enumerate(available):
        var_returns = returns[var].values
        sim_returns = var_returns[sim_indices]
        paths = current_values[var] * np.cumprod(1 + sim_returns, axis=1)
        # Prepend current value
        paths = np.column_stack([np.full(n_simulations, current_values[var]), paths])

        final_values = paths[:, -1]
        final_returns = (final_values / current_values[var]) - 1

        var_95 = np.percentile(final_returns, 5)
        var_99 = np.percentile(final_returns, 1)
        cvar_95 = final_returns[final_returns <= var_95].mean()
        cvar_99 = final_returns[final_returns <= var_99].mean()

        # Historical worst
        hist_worst = returns[var].min()
        prob_worse_than_hist = (final_returns < hist_worst * n_quarters).mean()

        results[var] = {
            "current_value": float(current_values[var]),
            "paths": paths,
            "final_returns": final_returns,
            "var_95": float(var_95),
            "var_99": float(var_99),
            "cvar_95": float(cvar_95),
            "cvar_99": float(cvar_99),
            "median_return": float(np.median(final_returns)),
            "mean_return": float(np.mean(final_returns)),
            "prob_negative": float((final_returns < 0).mean()),
            "prob_worse_than_hist_worst": float(prob_worse_than_hist),
            "percentiles": {p: float(np.percentile(final_values, p)) for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]},
        }

    print(f"\nMONTE CARLO STRESS TEST ({n_simulations:,} simulations, {n_quarters}Q horizon)")
    for var, r in results.items():
        print(f"\n  {var}:")
        print(f"    Current: ${r['current_value']:.1f}B")
        print(f"    Median outcome: {r['median_return']:+.1%}")
        print(f"    VaR 95%: {r['var_95']:+.1%} (${r['current_value'] * (1 + r['var_95']):.1f}B)")
        print(f"    CVaR 95%: {r['cvar_95']:+.1%} (${r['current_value'] * (1 + r['cvar_95']):.1f}B)")
        print(f"    VaR 99%: {r['var_99']:+.1%}")
        print(f"    P(negative): {r['prob_negative']:.1%}")

    return results


# ---------------------------------------------------------------------------
# 6. Form PF Liquidity Deep-Dive
# ---------------------------------------------------------------------------


def liquidity_deep_dive(sources):
    """Analyze Form PF liquidity mismatch dynamics across time horizons.

    Flags quarters with dangerous mismatches (investor can redeem faster
    than portfolio can liquidate).
    """
    if "form_pf_liquidity" not in sources:
        print("Liquidity deep-dive: missing form_pf_liquidity data")
        return {}

    liq = sources["form_pf_liquidity"].copy()

    periods = ["At most 30 days", "At most 90 days", "At most 180 days"]
    types_needed = ["investor_liquidity", "portfolio_liquidity"]

    results = {}
    for period in periods:
        mismatches = []
        for ltype in types_needed:
            subset = liq[(liq["liquidity_type"] == ltype) & (liq["period"] == period)].copy()
            if subset.empty:
                continue
            subset["date"] = _quarter_str_to_timestamp(subset["quarter"])
            subset = subset.set_index("date").sort_index()
            results[f"{ltype}_{period}"] = subset["cumulative_pct"]
            mismatches.append(subset[["cumulative_pct"]].rename(columns={"cumulative_pct": ltype}))

        if len(mismatches) == 2:
            merged = mismatches[0].join(mismatches[1], how="inner")
            merged["mismatch"] = merged["investor_liquidity"] - merged["portfolio_liquidity"]
            results[f"mismatch_{period}"] = merged

    # Flag dangerous quarters (mismatch > 20%)
    print("\nFORM PF LIQUIDITY DEEP-DIVE")
    for period in periods:
        key = f"mismatch_{period}"
        if key in results:
            mm = results[key]
            dangerous = mm[mm["mismatch"] > 0.20]
            print(f"\n  {period}:")
            print(f"    Mean mismatch: {mm['mismatch'].mean():.1%}")
            print(
                f"    Max mismatch: {mm['mismatch'].max():.1%} "
                f"({mm['mismatch'].idxmax().date() if hasattr(mm['mismatch'].idxmax(), 'date') else mm['mismatch'].idxmax()})"
            )
            print(f"    Dangerous quarters (>20%): {len(dangerous)}")
            if not dangerous.empty:
                for date, row in dangerous.iterrows():
                    d = date.date() if hasattr(date, "date") else date
                    print(
                        f"      {d}: investor={row['investor_liquidity']:.1%}, "
                        f"portfolio={row['portfolio_liquidity']:.1%}, "
                        f"gap={row['mismatch']:.1%}"
                    )

    return results


# ---------------------------------------------------------------------------
# 7. Strategy Rotation Analysis
# ---------------------------------------------------------------------------


def strategy_rotation_analysis(sources):
    """Analyze Form PF strategy allocation changes and compute HHI over time."""
    if "form_pf_strategy" not in sources:
        print("Strategy rotation: missing form_pf_strategy data")
        return {}

    strat = sources["form_pf_strategy"].copy()
    if "quarter" not in strat.columns or "nav" not in strat.columns:
        print("Strategy rotation: missing required columns")
        return {}

    strat["date"] = _quarter_str_to_timestamp(strat["quarter"])

    # Compute HHI per quarter
    hhi_rows = []
    for quarter, grp in strat.groupby("quarter"):
        total_nav = grp["nav"].sum()
        if total_nav > 0:
            shares = grp["nav"] / total_nav
            hhi = (shares**2).sum()
            top_strategy = grp.loc[grp["nav"].idxmax(), "strategy"]
            top_share = grp["nav"].max() / total_nav
            hhi_rows.append(
                {
                    "quarter": quarter,
                    "date": _quarter_str_to_timestamp(pd.Series([quarter])).values[0],
                    "hhi": hhi,
                    "n_strategies": len(grp),
                    "top_strategy": top_strategy,
                    "top_share": top_share,
                    "total_nav": total_nav,
                }
            )

    if not hhi_rows:
        return {}

    hhi_df = pd.DataFrame(hhi_rows).sort_values("date")

    # Trend test on HHI
    tau, p_val = stats.kendalltau(np.arange(len(hhi_df)), hhi_df["hhi"].values)

    # Biggest quarter-over-quarter shifts
    hhi_df["hhi_change"] = hhi_df["hhi"].diff()
    biggest_shifts = hhi_df.nlargest(5, "hhi_change", keep="first")

    print("\nSTRATEGY ROTATION ANALYSIS")
    print(f"  Quarters: {len(hhi_df)}")
    print(f"  HHI range: {hhi_df['hhi'].min():.4f} to {hhi_df['hhi'].max():.4f}")
    print(f"  HHI trend: tau={tau:.3f}, p={p_val:.4f} ({'diversifying' if tau < 0 else 'concentrating'})")
    print(f"  Current top strategy: {hhi_df.iloc[-1]['top_strategy']} ({hhi_df.iloc[-1]['top_share']:.1%} of NAV)")
    print("\n  Biggest concentration shifts:")
    for _, row in biggest_shifts.iterrows():
        print(
            f"    {row['quarter']}: HHI change={row['hhi_change']:+.4f}, "
            f"top={row['top_strategy']} ({row['top_share']:.1%})"
        )

    return {
        "hhi_df": hhi_df,
        "trend_tau": tau,
        "trend_p": p_val,
    }


# ---------------------------------------------------------------------------
# 8. FCM Concentration Trend Analysis
# ---------------------------------------------------------------------------


def fcm_concentration_analysis(sources):
    """Analyze FCM market concentration trends — HHI, top-5 share, Gini."""
    if "fcm_concentration" not in sources:
        print("FCM concentration: missing data")
        return {}

    conc = sources["fcm_concentration"].copy()
    if "as_of_date" in conc.columns:
        conc["date"] = pd.to_datetime(conc["as_of_date"])
    elif "date" in conc.columns:
        conc["date"] = pd.to_datetime(conc["date"])
    else:
        print("FCM concentration: no date column found")
        return {}

    conc = conc.sort_values("date")

    # Trend tests
    tau_hhi, p_hhi = stats.kendalltau(np.arange(len(conc)), conc["hhi"].values)
    tau_top5, p_top5 = stats.kendalltau(np.arange(len(conc)), conc["top5_share"].values)

    # Structural break in HHI
    breaks = detect_structural_breaks(conc.set_index("date")["hhi"], name="FCM HHI", min_segment=6)

    print("\nFCM CONCENTRATION TRENDS")
    print(f"  Months: {len(conc)} ({conc['date'].min().date()} to {conc['date'].max().date()})")
    print(f"  HHI: {conc['hhi'].iloc[0]:.4f} -> {conc['hhi'].iloc[-1]:.4f} (trend tau={tau_hhi:.3f}, p={p_hhi:.4f})")
    print(
        f"  Top-5 share: {conc['top5_share'].iloc[0]:.1%} -> {conc['top5_share'].iloc[-1]:.1%} "
        f"(trend tau={tau_top5:.3f}, p={p_top5:.4f})"
    )

    return {
        "data": conc,
        "hhi_trend": {"tau": tau_hhi, "p": p_hhi},
        "top5_trend": {"tau": tau_top5, "p": p_top5},
        "breaks": breaks,
    }


# ---------------------------------------------------------------------------
# 9. 13F Holdings Concentration
# ---------------------------------------------------------------------------


def thirteenf_concentration(sources):
    """Analyze 13F equity holdings concentration across top funds."""
    path_13f = os.path.join(RAW, "13f_all_holdings.csv")
    if not os.path.exists(path_13f):
        print("13F concentration: file not found")
        return {}

    holdings = pd.read_csv(path_13f)
    if "value_thousands" not in holdings.columns:
        print("13F concentration: missing value_thousands column")
        return {}

    holdings["value"] = holdings["value_thousands"] * 1000  # to USD

    # Per-fund concentration (HHI of issuers within each fund)
    fund_hhi = []
    for (fund, date), grp in holdings.groupby(["fund", "filing_date"]):
        total = grp["value"].sum()
        if total > 0:
            shares = grp["value"] / total
            hhi = (shares**2).sum()
            top_holding = grp.loc[grp["value"].idxmax(), "issuer"]
            top_pct = grp["value"].max() / total
            fund_hhi.append(
                {
                    "fund": fund,
                    "filing_date": date,
                    "hhi": hhi,
                    "n_positions": len(grp),
                    "top_holding": top_holding,
                    "top_pct": top_pct,
                    "total_value": total,
                }
            )

    if not fund_hhi:
        return {}

    hhi_df = pd.DataFrame(fund_hhi)
    hhi_df["filing_date"] = pd.to_datetime(hhi_df["filing_date"])

    # Cross-fund overlap: which issuers appear in the most portfolios?
    latest_date = hhi_df["filing_date"].max()
    latest = holdings[holdings["filing_date"] == str(latest_date.date())].copy()
    if latest.empty:
        latest = holdings[holdings["filing_date"] == holdings["filing_date"].max()]

    issuer_counts = (
        latest.groupby("issuer")
        .agg(
            n_funds=("fund", "nunique"),
            total_value=("value", "sum"),
        )
        .sort_values("n_funds", ascending=False)
    )

    overlap = issuer_counts[issuer_counts["n_funds"] > 1].head(20)

    print("\n13F HOLDINGS CONCENTRATION")
    print(f"  Funds: {hhi_df['fund'].nunique()}")
    print(f"  Filings: {len(hhi_df)}")

    # Per-fund summary at latest date
    latest_hhi = hhi_df[hhi_df["filing_date"] == hhi_df["filing_date"].max()]
    for _, row in latest_hhi.iterrows():
        print(
            f"  {row['fund']}: HHI={row['hhi']:.4f}, "
            f"{row['n_positions']} positions, "
            f"top={row['top_holding'][:30]} ({row['top_pct']:.1%})"
        )

    if not overlap.empty:
        print(f"\n  Most commonly held (across {latest['fund'].nunique()} funds):")
        for issuer, row in overlap.head(10).iterrows():
            print(f"    {issuer[:40]}: {row['n_funds']} funds, ${row['total_value'] / 1e6:.0f}M")

    return {
        "fund_hhi": hhi_df,
        "overlap": overlap,
    }


# ---------------------------------------------------------------------------
# Master orchestrator
# ---------------------------------------------------------------------------


def run_all_advanced(save=True):
    """Run all advanced analyses and save results."""
    from src.analysis.cross_source import align_quarterly, load_all_sources

    print("=" * 80)
    print("ADVANCED STATISTICAL ANALYSIS")
    print("=" * 80)

    # Load and align
    sources = load_all_sources()
    aligned = align_quarterly(sources)

    all_results = {}

    # 1. Granger causality matrix
    print("\n" + "=" * 80)
    granger_p = granger_causality_matrix(aligned)
    all_results["granger"] = granger_p

    # 2. Johansen cointegration
    print("\n" + "=" * 80)
    johansen = johansen_cointegration(aligned)
    all_results["johansen"] = johansen

    # Also test Form PF GAV vs CFTC swap notional
    johansen_swaps = johansen_cointegration(
        aligned,
        variables=["pf_gav", "swap_ir_total", "swap_credit_total"],
    )
    all_results["johansen_swaps"] = johansen_swaps

    # 3. VAR impulse response
    print("\n" + "=" * 80)
    var_result = var_impulse_response(aligned)
    all_results["var"] = var_result

    # 4. Structural breaks
    print("\n" + "=" * 80)
    break_series = {
        "z1_leverage_ratio": "Z.1 Leverage Ratio",
        "pf_gav_nav_ratio": "Form PF GAV/NAV",
        "swap_ir_cleared_pct": "IR Swap Clearing Rate",
        "vix_mean": "VIX Mean",
    }
    all_breaks = {}
    for col, name in break_series.items():
        if col in aligned.columns:
            all_breaks[col] = detect_structural_breaks(aligned[col], name=name)
    all_results["structural_breaks"] = all_breaks

    # 5. Monte Carlo
    print("\n" + "=" * 80)
    mc = monte_carlo_stress_test(aligned)
    all_results["monte_carlo"] = mc

    # 6. Form PF liquidity deep-dive
    print("\n" + "=" * 80)
    liquidity = liquidity_deep_dive(sources)
    all_results["liquidity"] = liquidity

    # 7. Strategy rotation
    print("\n" + "=" * 80)
    strategy = strategy_rotation_analysis(sources)
    all_results["strategy_rotation"] = strategy

    # 8. FCM concentration
    print("\n" + "=" * 80)
    fcm_conc = fcm_concentration_analysis(sources)
    all_results["fcm_concentration"] = fcm_conc

    # 9. 13F concentration
    print("\n" + "=" * 80)
    thirteenf = thirteenf_concentration(sources)
    all_results["thirteenf"] = thirteenf

    # Save results
    if save:
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # Granger matrix
        if not granger_p.empty:
            granger_p.to_csv(os.path.join(OUTPUT_DIR, "granger_causality_matrix.csv"))

        # VAR IRF
        if "irf_df" in var_result:
            var_result["irf_df"].to_csv(os.path.join(OUTPUT_DIR, "var_impulse_response.csv"))
            var_result["fevd_df"].to_csv(os.path.join(OUTPUT_DIR, "var_fevd.csv"))

        # Strategy HHI
        if "hhi_df" in strategy:
            strategy["hhi_df"].to_csv(os.path.join(OUTPUT_DIR, "strategy_rotation_hhi.csv"), index=False)

        # Monte Carlo summary
        if mc:
            mc_summary = []
            for var, r in mc.items():
                mc_summary.append(
                    {
                        "variable": var,
                        "current": r["current_value"],
                        "var_95": r["var_95"],
                        "cvar_95": r["cvar_95"],
                        "var_99": r["var_99"],
                        "cvar_99": r["cvar_99"],
                        "median_return": r["median_return"],
                        "prob_negative": r["prob_negative"],
                    }
                )
            pd.DataFrame(mc_summary).to_csv(os.path.join(OUTPUT_DIR, "monte_carlo_summary.csv"), index=False)

        print(f"\nResults saved to {OUTPUT_DIR}")

    # Generate report
    _write_report(all_results)

    return all_results


def _write_report(results):
    """Write a comprehensive text report of all advanced analysis results."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    report_path = os.path.join(OUTPUT_DIR, "advanced_analysis.txt")

    lines = []
    lines.append("=" * 80)
    lines.append("ADVANCED STATISTICAL ANALYSIS REPORT")
    lines.append(f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 80)

    # Granger
    granger = results.get("granger")
    if granger is not None and not granger.empty:
        lines.append("\n\n1. GRANGER CAUSALITY MATRIX")
        lines.append("-" * 40)
        lines.append("Significant causal relationships (p < 0.05):")
        for cause in granger.index:
            for effect in granger.columns:
                p = granger.loc[cause, effect]
                if not np.isnan(p) and p < 0.05:
                    lines.append(f"  {cause} -> {effect}: p={p:.4f}")

    # Johansen
    johansen = results.get("johansen", {})
    if johansen:
        lines.append("\n\n2. JOHANSEN COINTEGRATION")
        lines.append("-" * 40)
        lines.append(f"Variables: {johansen.get('variables', [])}")
        lines.append(f"Cointegrating relationships (trace): {johansen.get('n_coint_trace', 0)}")
        lines.append(f"Cointegrating relationships (max eigenvalue): {johansen.get('n_coint_eigen', 0)}")

    # VAR
    var = results.get("var", {})
    if var:
        lines.append("\n\n3. VAR MODEL & IMPULSE RESPONSE")
        lines.append("-" * 40)
        lines.append(f"Variables: {var.get('variables', [])}")
        lines.append(f"Lag order: {var.get('lag_order', 'N/A')}")
        lines.append(f"AIC: {var.get('aic', 'N/A'):.2f}")

    # Structural breaks
    breaks = results.get("structural_breaks", {})
    if breaks:
        lines.append("\n\n4. STRUCTURAL BREAKS")
        lines.append("-" * 40)
        for col, b in breaks.items():
            lines.append(f"\n  {b['name']}:")
            if b["breaks"]:
                for br in b["breaks"]:
                    lines.append(f"    Break at {br['date']} (F={br['f_stat']:.2f})")
            else:
                lines.append("    No significant breaks detected")
            for seg in b["segments"]:
                lines.append(
                    f"    Segment {seg['start']} to {seg['end']}: mean={seg['mean']:.4f}, std={seg['std']:.4f}"
                )

    # Monte Carlo
    mc = results.get("monte_carlo", {})
    if mc:
        lines.append("\n\n5. MONTE CARLO STRESS TEST (10,000 simulations, 8Q horizon)")
        lines.append("-" * 40)
        for var_name, r in mc.items():
            lines.append(f"\n  {var_name}:")
            lines.append(f"    Current: ${r['current_value']:.1f}B")
            lines.append(f"    VaR 95%: {r['var_95']:+.1%}")
            lines.append(f"    CVaR 95%: {r['cvar_95']:+.1%}")
            lines.append(f"    VaR 99%: {r['var_99']:+.1%}")
            lines.append(f"    P(negative): {r['prob_negative']:.1%}")
            lines.append("    Percentiles of final value ($B):")
            for p, v in r["percentiles"].items():
                lines.append(f"      {p}th: ${v:.1f}B")

    # Liquidity
    liq = results.get("liquidity", {})
    if liq:
        lines.append("\n\n6. FORM PF LIQUIDITY MISMATCH")
        lines.append("-" * 40)
        for key, val in liq.items():
            if key.startswith("mismatch_") and isinstance(val, pd.DataFrame):
                period = key.replace("mismatch_", "")
                lines.append(f"\n  {period}:")
                lines.append(f"    Mean mismatch: {val['mismatch'].mean():.1%}")
                lines.append(f"    Max mismatch: {val['mismatch'].max():.1%}")
                dangerous = val[val["mismatch"] > 0.20]
                lines.append(f"    Dangerous quarters (>20%): {len(dangerous)}")

    # Strategy rotation
    strat = results.get("strategy_rotation", {})
    if strat and "hhi_df" in strat:
        lines.append("\n\n7. STRATEGY ROTATION")
        lines.append("-" * 40)
        hhi_df = strat["hhi_df"]
        lines.append(f"  HHI trend: tau={strat['trend_tau']:.3f}, p={strat['trend_p']:.4f}")
        lines.append(f"  HHI range: {hhi_df['hhi'].min():.4f} to {hhi_df['hhi'].max():.4f}")

    # FCM concentration
    fcm = results.get("fcm_concentration", {})
    if fcm and "hhi_trend" in fcm:
        lines.append("\n\n8. FCM CONCENTRATION")
        lines.append("-" * 40)
        lines.append(f"  HHI trend: tau={fcm['hhi_trend']['tau']:.3f}, p={fcm['hhi_trend']['p']:.4f}")
        lines.append(f"  Top-5 trend: tau={fcm['top5_trend']['tau']:.3f}, p={fcm['top5_trend']['p']:.4f}")

    # 13F
    thirteenf = results.get("thirteenf", {})
    if thirteenf and "fund_hhi" in thirteenf:
        lines.append("\n\n9. 13F HOLDINGS CONCENTRATION")
        lines.append("-" * 40)
        hhi_df = thirteenf["fund_hhi"]
        lines.append(f"  Funds tracked: {hhi_df['fund'].nunique()}")
        lines.append(f"  Total filings: {len(hhi_df)}")

    lines.append("\n\n" + "=" * 80)
    lines.append("END OF REPORT")
    lines.append("=" * 80)

    report = "\n".join(lines)
    with open(report_path, "w") as f:
        f.write(report)
    print(f"\nReport saved to {report_path}")


if __name__ == "__main__":
    run_all_advanced(save=True)
