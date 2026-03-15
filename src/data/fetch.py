"""Data fetching functions for all external sources."""

import os
import time
import json
import requests
import xml.etree.ElementTree as ET
from io import StringIO

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from fredapi import Fred


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# FRED series ID mapping for B.101.f (Balance Sheet of Domestic Hedge Funds)
HEDGE_FUND_SERIES = {
    # Assets
    "Total assets": "BOGZ1FL624090005Q",
    "Foreign currency; asset": "BOGZ1FL623091003Q",
    "Deposits; asset": "BOGZ1FL623039003Q",
    "Other cash and cash equivalents; asset": "BOGZ1FL623039013Q",
    "Money market fund shares; asset": "BOGZ1FL623034003Q",
    "Security repurchase agreements; asset": "BOGZ1FL622051003Q",
    "Total debt securities; asset": "BOGZ1FL624022005Q",
    "Treasury securities; asset": "BOGZ1FL623061103Q",
    "Corporate and foreign bonds; asset": "BOGZ1FL623063003Q",
    "Total loans; asset": "BOGZ1FL623069005Q",
    "Leveraged loans; asset": "BOGZ1FL623069503Q",
    "Other loans; asset": "BOGZ1FL623069003Q",
    "Corporate equities; asset": "BOGZ1FL623064103Q",
    "Miscellaneous assets; asset": "BOGZ1FL623093005Q",
    # Liabilities
    "Total liabilities": "BOGZ1FL624190005Q",
    "Total security repurchase agreements; liability": "BOGZ1FL622151005Q",
    "Security repurchase agreements with domestic institutions; liability": "BOGZ1FL622151013Q",
    "Security repurchase agreements with foreign institutions; liability": "BOGZ1FL622151063Q",
    "Total loans; liability": "BOGZ1FL624123005Q",
    "Loans, total secured borrowing via prime brokerage; liability": "BOGZ1FL624123035Q",
    "Loans, secured borrowing via domestic prime brokerages; liability": "BOGZ1FL623167003Q",
    "Loans, secured borrowing via foreign prime brokerages; liability": "BOGZ1FL623169533Q",
    "Loans, total other secured borrowing; liability": "BOGZ1FL624123015Q",
    "Loans, other secured borrowing from domestic institutions; liability": "BOGZ1FL623168013Q",
    "Loans, other secured borrowing from foreign institutions; liability": "BOGZ1FL623169513Q",
    "Loans, total unsecured borrowing; liability": "BOGZ1FL623168023Q",
    "Miscellaneous liabilities; liability": "BOGZ1FL623193005Q",
    # Net assets and memo items
    "Total net assets": "BOGZ1FL622000003Q",
    "Derivatives (long value)": "BOGZ1FL623098003Q",
}

SEC_HEADERS = {
    "User-Agent": "HedgeFundIndustryAnalysis admin@financialresearch.dev",
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov",
}

HEDGE_FUND_CIKS = {
    "Citadel Advisors": "0001423053",
    "Bridgewater Associates": "0001350694",
    "Renaissance Technologies": "0001037389",
    "Point72 Asset Management": "0001603466",
    "Two Sigma Investments": "0001179392",
    "D.E. Shaw": "0001009207",
    "Millennium Management": "0001273087",
    "AQR Capital Management": "0001167557",
}


# ---------------------------------------------------------------------------
# FRED — Hedge Fund Balance Sheet
# ---------------------------------------------------------------------------

def fetch_hedge_fund_data(fred_client, series_map, cache_path=None):
    """Fetch all hedge fund balance sheet series from FRED and combine into a DataFrame."""
    if cache_path and os.path.exists(cache_path):
        print(f"Loading cached data from {cache_path}")
        df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        print(f"  Loaded {len(df)} quarters, {df.index.min().date()} to {df.index.max().date()}")
        return df

    print(f"Fetching {len(series_map)} series from FRED...")
    data = {}
    failed = []
    for name, series_id in series_map.items():
        try:
            s = fred_client.get_series(series_id)
            data[name] = s
            print(f"  OK: {name} ({series_id}) — {len(s)} observations")
        except Exception as e:
            print(f"  FAILED: {name} ({series_id}) — {e}")
            failed.append(name)
        time.sleep(0.2)

    df = pd.DataFrame(data)
    df.index.name = "Date"

    # Convert to billions (FRED returns millions for Z.1 data)
    df = df / 1000.0

    if cache_path:
        df.to_csv(cache_path)
        print(f"\nSaved to {cache_path}")

    if failed:
        print(f"\nWARNING: {len(failed)} series failed: {failed}")

    print(f"Fetched {len(df)} quarters, {df.index.min().date()} to {df.index.max().date()}")
    return df


# ---------------------------------------------------------------------------
# FRED — VIX Volatility Index
# ---------------------------------------------------------------------------

def fetch_vix_data(fred_client, cache_path=None):
    """Fetch VIX daily data from FRED, aggregate to quarterly."""
    if cache_path and os.path.exists(cache_path):
        print(f"Loading cached VIX data from {cache_path}")
        df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        return df

    print("Fetching VIX data from FRED (VIXCLS)...")
    vix = fred_client.get_series('VIXCLS')
    vix = vix.dropna()

    df = vix.resample('QE').agg(
        VIX_mean='mean',
        VIX_max='max',
        VIX_min='min',
        VIX_end='last',
        VIX_std='std'
    ).rename_axis("Date")

    if cache_path:
        df.to_csv(cache_path)
        print(f"Saved to {cache_path}")

    print(f"VIX data: {len(df)} quarters, {df.index.min().date()} to {df.index.max().date()}")
    return df


# ---------------------------------------------------------------------------
# SEC EDGAR — 13F Holdings
# ---------------------------------------------------------------------------

def fetch_13f_holdings(cik, fund_name, cache_dir="data/raw",
                       start_date="2020-10-01", end_date="2021-06-30"):
    """Fetch 13F-HR filing data from SEC EDGAR for a given fund.

    Args:
        start_date: Earliest filing date to fetch holdings for (inclusive).
        end_date: Latest filing date to fetch holdings for (inclusive).
    """
    cache_path = os.path.join(cache_dir, f"13f_{fund_name.replace(' ', '_').lower()}.csv")
    if os.path.exists(cache_path):
        print(f"  Cached: {fund_name}")
        return pd.read_csv(cache_path)

    submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"

    try:
        resp = requests.get(submissions_url, headers=SEC_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        filings = data.get("filings", {}).get("recent", {})
        forms = filings.get("form", [])
        dates = filings.get("filingDate", [])
        accessions = filings.get("accessionNumber", [])
        primary_docs = filings.get("primaryDocument", [])

        records = []
        for i, form in enumerate(forms):
            if form in ("13F-HR", "13F-HR/A"):
                records.append({
                    "fund": fund_name,
                    "form": form,
                    "filing_date": dates[i],
                    "accession": accessions[i],
                    "primary_doc": primary_docs[i] if i < len(primary_docs) else None,
                })

        if not records:
            print(f"  No 13F filings found for {fund_name}")
            return pd.DataFrame()

        df_filings = pd.DataFrame(records)
        print(f"  Found {len(df_filings)} 13F filings for {fund_name} (latest: {df_filings['filing_date'].iloc[0]})")

        window = df_filings[
            (df_filings['filing_date'] >= start_date) &
            (df_filings['filing_date'] <= end_date)
        ]

        all_holdings = []
        for _, filing in window.iterrows():
            acc_no = filing['accession'].replace('-', '')
            acc_dash = filing['accession']
            cik_stripped = cik.lstrip('0')
            base_url = f"https://www.sec.gov/Archives/edgar/data/{cik_stripped}/{acc_no}/"

            try:
                # Try index.json first, fall back to HTML scraping
                info_file = None
                try:
                    idx_resp = requests.get(
                        f"https://data.sec.gov/Archives/edgar/data/{cik_stripped}/{acc_no}/index.json",
                        headers=SEC_HEADERS, timeout=15)
                    idx_resp.raise_for_status()
                    idx_data = idx_resp.json()
                    for item in idx_data.get("directory", {}).get("item", []):
                        name = item.get("name", "").lower()
                        if "infotable" in name or "information" in name:
                            info_file = item["name"]
                            break
                        # Broader: any XML that's not primary_doc.xml
                        if name.endswith('.xml') and name != 'primary_doc.xml' and info_file is None:
                            info_file = item["name"]
                except Exception:
                    pass

                # Fallback: scrape HTML index for INFORMATION TABLE typed files
                if not info_file:
                    import re
                    idx_url = f"{base_url}{acc_dash}-index.htm"
                    idx_resp = requests.get(idx_url, headers=SEC_HEADERS, timeout=15)
                    if idx_resp.status_code == 200:
                        matches = re.findall(
                            r'href="[^"]*?/([^/"]+\.xml)"[^<]*</a>\s*</td>\s*<td[^>]*>\s*INFORMATION TABLE',
                            idx_resp.text, re.IGNORECASE)
                        if matches:
                            info_file = matches[0]
                        else:
                            # Any non-primary XML
                            xml_files = re.findall(r'href="[^"]*?/([^/"]+\.xml)"', idx_resp.text)
                            xml_files = [f for f in xml_files if f != 'primary_doc.xml']
                            if xml_files:
                                info_file = xml_files[0]
                    info_url = base_url

                if info_file:
                    xml_url = base_url + info_file
                    xml_resp = requests.get(xml_url, headers=SEC_HEADERS, timeout=15)
                    xml_resp.raise_for_status()

                    root = ET.fromstring(xml_resp.content)
                    ns = ""
                    if root.tag.startswith("{"):
                        ns = root.tag.split("}")[0] + "}"

                    for entry in root.findall(f".//{ns}infoTable"):
                        name_of_issuer = entry.findtext(f"{ns}nameOfIssuer", "")
                        title = entry.findtext(f"{ns}titleOfClass", "")
                        cusip = entry.findtext(f"{ns}cusip", "")
                        value = entry.findtext(f"{ns}value", "0")
                        shares_node = entry.find(f"{ns}shrsOrPrnAmt")
                        shares = shares_node.findtext(f"{ns}sshPrnamt", "0") if shares_node else "0"
                        share_type = shares_node.findtext(f"{ns}sshPrnamtType", "") if shares_node else ""
                        put_call = entry.findtext(f"{ns}putCall", "")

                        all_holdings.append({
                            "fund": fund_name,
                            "filing_date": filing["filing_date"],
                            "report_period": filing["filing_date"][:7],
                            "issuer": name_of_issuer,
                            "title": title,
                            "cusip": cusip,
                            "value_thousands": int(value) if value else 0,
                            "shares": int(shares) if shares else 0,
                            "share_type": share_type,
                            "put_call": put_call,
                        })

                time.sleep(0.15)
            except Exception as e:
                print(f"    Could not parse holdings for {filing['filing_date']}: {e}")
                continue

        if all_holdings:
            df_h = pd.DataFrame(all_holdings)
            df_h.to_csv(cache_path, index=False)
            print(f"  Saved {len(df_h)} holdings to {cache_path}")
            return df_h
        else:
            df_filings.to_csv(cache_path, index=False)
            return df_filings

    except Exception as e:
        print(f"  Error fetching {fund_name}: {e}")
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# CFTC — Commitments of Traders
# ---------------------------------------------------------------------------

def fetch_cftc_data(cache_path=None):
    """Fetch CFTC Traders in Financial Futures report for equity index futures."""
    if cache_path and os.path.exists(cache_path):
        print(f"Loading cached CFTC data from {cache_path}")
        return pd.read_csv(cache_path, parse_dates=['date'])

    print("Fetching CFTC Commitments of Traders data...")
    cftc_url = "https://www.cftc.gov/dea/newcot/FinFutL.txt"

    try:
        resp = requests.get(cftc_url, timeout=30)
        resp.raise_for_status()

        df = pd.read_csv(StringIO(resp.text))

        equity_keywords = ['S&P 500', 'E-MINI S&P', 'DJIA', 'DOW JONES', 'NASDAQ', 'RUSSELL']
        mask = df['Market_and_Exchange_Names'].str.upper().apply(
            lambda x: any(k in x.upper() for k in equity_keywords) if pd.notna(x) else False
        )
        df_equity = df[mask].copy()

        if df_equity.empty:
            print("  No equity index futures found, keeping all data")
            df_equity = df.copy()

        result = pd.DataFrame({
            'date': pd.to_datetime(df_equity['Report_Date_as_YYYY-MM-DD']),
            'market': df_equity['Market_and_Exchange_Names'],
            'lev_fund_long': pd.to_numeric(df_equity.get('Lev_Money_Positions_Long_All', 0), errors='coerce'),
            'lev_fund_short': pd.to_numeric(df_equity.get('Lev_Money_Positions_Short_All', 0), errors='coerce'),
            'lev_fund_spreading': pd.to_numeric(df_equity.get('Lev_Money_Positions_Spread_All', 0), errors='coerce'),
        })
        result['lev_fund_net'] = result['lev_fund_long'] - result['lev_fund_short']
        result = result.sort_values('date').reset_index(drop=True)

        if cache_path:
            result.to_csv(cache_path, index=False)
            print(f"Saved {len(result)} records to {cache_path}")

        print(f"CFTC data: {len(result)} records, {result['date'].min().date()} to {result['date'].max().date()}")
        return result

    except Exception as e:
        print(f"Error fetching CFTC data: {e}")
        print("Trying alternative CFTC source...")

        try:
            alt_url = "https://www.cftc.gov/dea/newcot/FinComAll.txt"
            resp = requests.get(alt_url, timeout=30)
            resp.raise_for_status()
            df = pd.read_csv(StringIO(resp.text))
            print(f"  Loaded alternative CFTC data: {len(df)} records")
            if cache_path:
                df.to_csv(cache_path, index=False)
            return df
        except Exception as e2:
            print(f"  Alternative also failed: {e2}")
            return pd.DataFrame()


# ---------------------------------------------------------------------------
# SEC EDGAR — Form ADV (Investment Adviser Registration)
# ---------------------------------------------------------------------------

def fetch_form_adv(cik, fund_name, cache_dir="data/raw"):
    """Fetch Form ADV data from SEC EDGAR for a given fund.

    Form ADV contains: AUM, employee count, types of clients,
    fee structures, disciplinary history, and office locations.
    """
    cache_path = os.path.join(cache_dir, "form_adv", f"adv_{fund_name.replace(' ', '_').lower()}.json")
    if os.path.exists(cache_path):
        print(f"  Cached: {fund_name} ADV")
        with open(cache_path) as f:
            return json.load(f)

    # Use the submissions API to find ADV filings
    submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    adv_headers = {
        "User-Agent": SEC_HEADERS["User-Agent"],
        "Accept-Encoding": "gzip, deflate",
    }

    try:
        resp = requests.get(submissions_url, headers=adv_headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        # Extract company info
        company_info = {
            "name": data.get("name"),
            "cik": cik,
            "sic": data.get("sic"),
            "sicDescription": data.get("sicDescription"),
            "stateOfIncorporation": data.get("stateOfIncorporation"),
            "addresses": data.get("addresses"),
        }

        # Find all filing types and dates
        filings = data.get("filings", {}).get("recent", {})
        forms = filings.get("form", [])
        dates = filings.get("filingDate", [])
        accessions = filings.get("accessionNumber", [])
        primary_docs = filings.get("primaryDocument", [])

        # Collect all filings (not just 13F)
        filing_records = []
        for i, form in enumerate(forms):
            filing_records.append({
                "form": form,
                "filing_date": dates[i],
                "accession": accessions[i],
                "primary_doc": primary_docs[i] if i < len(primary_docs) else None,
            })

        # Summary by filing type
        from collections import Counter
        form_counts = Counter(forms)

        result = {
            "company_info": company_info,
            "filing_type_counts": dict(form_counts),
            "total_filings": len(filing_records),
            "filing_date_range": {
                "earliest": dates[-1] if dates else None,
                "latest": dates[0] if dates else None,
            },
            "all_filings": filing_records,
        }

        # Look for ADV filings specifically
        adv_filings = [f for f in filing_records if 'ADV' in f['form']]
        result["adv_filings"] = adv_filings
        result["adv_count"] = len(adv_filings)

        # Try to get IAPD (Investment Adviser Public Disclosure) data
        # CIK and IAPD numbers are different — IAPD uses SEC file numbers
        iapd_numbers = []
        for i, form in enumerate(forms):
            if 'ADV' in form:
                iapd_numbers.append(accessions[i])
        result["iapd_accessions"] = iapd_numbers[:10]  # Keep recent ones

        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"  Saved {fund_name} ADV data ({len(filing_records)} total filings, {len(adv_filings)} ADV)")

        return result

    except Exception as e:
        print(f"  Error fetching ADV for {fund_name}: {e}")
        return {}


def fetch_all_fund_profiles(cache_dir="data/raw"):
    """Fetch submission profiles for all tracked hedge funds."""
    print("Fetching fund profiles from SEC EDGAR Submissions API...")
    profiles = {}
    for fund_name, cik in HEDGE_FUND_CIKS.items():
        profile = fetch_form_adv(cik, fund_name, cache_dir=cache_dir)
        if profile:
            profiles[fund_name] = profile
            info = profile.get("company_info", {})
            counts = profile.get("filing_type_counts", {})
            adv_count = profile.get("adv_count", 0)
            total = profile.get("total_filings", 0)
            date_range = profile.get("filing_date_range", {})
            print(f"    {fund_name}: {total} filings ({date_range.get('earliest')} to {date_range.get('latest')})")
            print(f"      ADV: {adv_count}, 13F: {counts.get('13F-HR', 0)}, "
                  f"SC 13G: {counts.get('SC 13G', 0) + counts.get('SC 13G/A', 0)}")
        time.sleep(0.15)
    return profiles


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    load_dotenv()
    FRED_API_KEY = os.getenv("FRED_API_KEY")

    if not FRED_API_KEY:
        print("ERROR: FRED_API_KEY not found in .env")
        exit(1)

    fred = Fred(api_key=FRED_API_KEY)
    raw_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'raw')
    os.makedirs(raw_dir, exist_ok=True)

    print("=" * 60)
    print("FETCHING ALL DATA SOURCES")
    print("=" * 60)

    # 1. FRED hedge fund balance sheet
    print("\n[1/4] FRED — Hedge Fund Balance Sheet")
    fetch_hedge_fund_data(fred, HEDGE_FUND_SERIES,
                          cache_path=os.path.join(raw_dir, 'hedge_fund_balance_sheet_fred.csv'))

    # 2. VIX
    print("\n[2/4] FRED — VIX Volatility Index")
    fetch_vix_data(fred, cache_path=os.path.join(raw_dir, 'vix_quarterly.csv'))

    # 3. SEC 13F
    print("\n[3/4] SEC EDGAR — 13F Holdings")
    holdings_list = []
    for fund_name, cik in HEDGE_FUND_CIKS.items():
        df_fund = fetch_13f_holdings(cik, fund_name, cache_dir=raw_dir)
        if not df_fund.empty and 'value_thousands' in df_fund.columns:
            holdings_list.append(df_fund)
        time.sleep(0.2)

    if holdings_list:
        df_13f = pd.concat(holdings_list, ignore_index=True)
        df_13f.to_csv(os.path.join(raw_dir, '13f_all_holdings.csv'), index=False)
        print(f"Total 13F holdings: {len(df_13f)} records across {df_13f['fund'].nunique()} funds")

    # 4. CFTC
    print("\n[4/5] CFTC — Commitments of Traders")
    fetch_cftc_data(cache_path=os.path.join(raw_dir, 'cftc_cot.csv'))

    # 5. Fund profiles (Form ADV + submission history)
    print("\n[5/5] SEC EDGAR — Fund Profiles (Submissions API)")
    fetch_all_fund_profiles(cache_dir=raw_dir)

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)
