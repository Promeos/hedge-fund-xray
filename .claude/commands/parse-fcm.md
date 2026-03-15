Parse all CFTC FCM monthly financial reports and produce processed CSVs.

## Steps

1. Run `python3 -m src.data.parse_fcm`
2. Parses all 49 Excel files in `data/raw/fcm/`
3. Produces 5 CSVs in `data/processed/`

## Output Files
- `fcm_monthly_all.csv` — All FCMs, all months (~3,000 rows)
- `fcm_monthly_industry.csv` — Industry totals + derived metrics (49 rows)
- `fcm_top_brokers.csv` — Top 10 FCMs by customer segregated funds (490 rows)
- `fcm_quarterly.csv` — Quarter-end snapshots (17 rows)
- `fcm_concentration.csv` — HHI and top-5 share (49 rows)

## Validation
- Total adj net capital ~$174B (Jan 2026)
- Total customer seg ~$368B
- Capital adequacy ratio ~3.6x
- ~69 active FCMs