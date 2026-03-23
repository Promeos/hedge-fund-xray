# Contributing

Thank you for your interest in contributing to Hedge Fund Autopsy.

## Reporting Issues

Open a [GitHub Issue](https://github.com/Promeos/hedge-fund-autopsy/issues) for:

- Bugs or data parsing errors
- Broken links or unclear documentation
- Suggestions for additional data sources or analyses
- Questions about methodology or findings

## Pull Requests

1. Fork the repo and create a branch from `master`
2. Make your changes
3. Run `ruff check .` and `ruff format --check .` to verify code style
4. Run `pytest` and confirm all tests pass
5. Open a PR with a clear description of what changed and why

## Code Style

This project uses [ruff](https://docs.astral.sh/ruff/) for linting and formatting. Configuration is in `pyproject.toml`:

- **Line length:** 120
- **Rules:** E, F, W, I (pycodestyle, pyflakes, warnings, isort)
- **Target:** Python 3.10+

## Data Access

Most data sources are publicly available and fetched automatically. You will need:

- A free [FRED API key](https://fred.stlouisfed.org/docs/api/api_key.html) set as `FRED_API_KEY` in a `.env` file
- The SEC Form PF Excel file (manually downloaded from [SEC.gov](https://www.sec.gov/divisions/investment/private-fund-statistics))

All other sources (CFTC weekly swaps, DTCC swap repository, FCM financials, SEC EDGAR, CBOE VIX) are fetched automatically by the pipeline scripts.

## Monetary Conventions

- All monetary values are in **billions USD**
- Cross-source alignment uses **quarterly frequency** (quarter-end dates)
- See `CLAUDE.md` for the full derived metrics reference

## License

By contributing, you agree that your contributions will be licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
