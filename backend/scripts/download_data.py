"""Download January 2026 wind actuals and forecasts from Elexon and save them as CSV.

Run from the backend folder:
    python -m scripts.download_data

We save the data once instead of calling Elexon on every page load: it is
faster, works offline, and avoids Elexon's rate limit (HTTP 429).
"""

from datetime import timedelta

import pandas as pd

from app.config import (
    ACTUALS_CSV,
    DATA_DIR,
    DELIVERY_END,
    DELIVERY_START,
    FORECAST_LOOKBACK_DAYS,
    FORECASTS_CSV,
)
from app.elexon_client import fetch_wind_actuals, fetch_wind_forecasts


def build_actuals() -> pd.DataFrame:
    print(f"Fetching actuals for {DELIVERY_START} .. {DELIVERY_END}")
    raw = pd.DataFrame(fetch_wind_actuals(DELIVERY_START, DELIVERY_END))

    df = raw[["startTime", "generation"]].rename(
        columns={"startTime": "start_time", "generation": "generation_mw"}
    )
    df["start_time"] = pd.to_datetime(df["start_time"], utc=True)
    # Elexon can re-publish a half-hour; keep one row per half-hour.
    df = df.drop_duplicates("start_time", keep="last")
    return df.sort_values("start_time").reset_index(drop=True)


def build_forecasts() -> pd.DataFrame:
    publish_start = DELIVERY_START - timedelta(days=FORECAST_LOOKBACK_DAYS)
    print(f"Fetching forecasts published {publish_start} .. {DELIVERY_END}")
    raw = pd.DataFrame(fetch_wind_forecasts(publish_start, DELIVERY_END))

    df = raw[["startTime", "publishTime", "generation"]].rename(
        columns={
            "startTime": "start_time",
            "publishTime": "publish_time",
            "generation": "generation_mw",
        }
    )
    df["start_time"] = pd.to_datetime(df["start_time"], utc=True)
    df["publish_time"] = pd.to_datetime(df["publish_time"], utc=True)

    # Keep only real forecasts (made before the hour they predict) ...
    df = df[df["publish_time"] < df["start_time"]]
    # ... and only for hours inside our delivery window.
    window_start = pd.Timestamp(DELIVERY_START, tz="UTC")
    window_end = pd.Timestamp(DELIVERY_END + timedelta(days=1), tz="UTC")
    df = df[(df["start_time"] >= window_start) & (df["start_time"] < window_end)]

    df = df.drop_duplicates(["start_time", "publish_time"], keep="last")
    return df.sort_values(["start_time", "publish_time"]).reset_index(drop=True)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    actuals = build_actuals()
    actuals.to_csv(ACTUALS_CSV, index=False)
    print(f"Saved {len(actuals)} actual rows -> {ACTUALS_CSV}")

    forecasts = build_forecasts()
    forecasts.to_csv(FORECASTS_CSV, index=False)
    print(f"Saved {len(forecasts)} forecast rows -> {FORECASTS_CSV}")


if __name__ == "__main__":
    main()
