"""Project-wide settings: where data comes from and which period we care about."""

import os
from datetime import date, time
from pathlib import Path

ELEXON_BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"

# Purchase decisions are made in January 2026, one day before delivery.
# So delivery days run from 2 Jan to 1 Feb 2026.
DECISION_START = date(2026, 1, 1)
DECISION_END = date(2026, 1, 31)
DELIVERY_START = date(2026, 1, 2)
DELIVERY_END = date(2026, 2, 1)

# Day-ahead orders must be in by this UK local time on the day before delivery.
# The forecast used for a delivery day is the latest one published before it.
MARKET_TZ = "Europe/London"
DECISION_DEADLINE_LOCAL = time(9, 0)

# Forecasts reach ~3 days ahead, so start fetching a few days before the
# first delivery day to capture every forecast made for it.
FORECAST_LOOKBACK_DAYS = 4

# Websites allowed to call the API from a browser (comma-separated).
# Locally the React dev server runs on :5173; in production set this to the deployed frontend URL.
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ACTUALS_CSV = DATA_DIR / "actuals.csv"
FORECASTS_CSV = DATA_DIR / "forecasts.csv"
