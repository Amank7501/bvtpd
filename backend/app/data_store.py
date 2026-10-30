"""Load the saved CSVs once and reuse them (the data never changes at runtime)."""

from functools import lru_cache

import pandas as pd

from app.config import ACTUALS_CSV, FORECASTS_CSV


@lru_cache(maxsize=1)
def load_actuals() -> pd.DataFrame:
    """Columns: start_time (UTC), generation_mw. One row per half-hour."""
    return pd.read_csv(ACTUALS_CSV, parse_dates=["start_time"])


@lru_cache(maxsize=1)
def load_forecasts() -> pd.DataFrame:
    """Columns: start_time (UTC), publish_time (UTC), generation_mw. Many versions per hour."""
    return pd.read_csv(FORECASTS_CSV, parse_dates=["start_time", "publish_time"])
