"""Print a quick health report of the downloaded data.

Run from the backend folder (after download_data):
    python -m scripts.explore_data
"""

import pandas as pd

from app.config import ACTUALS_CSV, FORECASTS_CSV


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    actuals = pd.read_csv(ACTUALS_CSV, parse_dates=["start_time"])
    forecasts = pd.read_csv(FORECASTS_CSV, parse_dates=["start_time", "publish_time"])
    return actuals, forecasts


def report_actuals(actuals: pd.DataFrame) -> None:
    print("=== ACTUALS (FUELHH, WIND) ===")
    print(f"Rows: {len(actuals)}")
    print(f"Range: {actuals['start_time'].min()} -> {actuals['start_time'].max()}")

    expected = pd.date_range(actuals["start_time"].min(), actuals["start_time"].max(), freq="30min")
    missing = expected.difference(actuals["start_time"])
    print(f"Missing half-hours: {len(missing)}")

    gen = actuals["generation_mw"]
    print(f"Generation MW: min {gen.min():,.0f} | mean {gen.mean():,.0f} | max {gen.max():,.0f}")
    print()


def report_forecasts(forecasts: pd.DataFrame) -> None:
    print("=== FORECASTS (WINDFOR) ===")
    print(f"Rows: {len(forecasts)}")
    print(f"Target hours covered: {forecasts['start_time'].nunique()}")
    print(f"Distinct publish times: {forecasts['publish_time'].nunique()}")

    minutes = forecasts["start_time"].dt.minute.value_counts().to_dict()
    print(f"Target-time minutes (shows resolution): {minutes}")

    publishes_per_day = forecasts.groupby(forecasts["publish_time"].dt.date)["publish_time"].nunique()
    print(f"Publishes per day: typically {publishes_per_day.median():.0f}")

    horizon_h = (forecasts["start_time"] - forecasts["publish_time"]).dt.total_seconds() / 3600
    print(f"Forecast horizon (hours ahead): min {horizon_h.min():.1f} | max {horizon_h.max():.1f}")

    per_target = forecasts.groupby("start_time").size()
    print(f"Forecast versions per target hour: min {per_target.min()} | median {per_target.median():.0f} | max {per_target.max()}")
    print()


def show_example(forecasts: pd.DataFrame, actuals: pd.DataFrame) -> None:
    """Show how the forecast for one hour changed with each publish, vs what really happened."""
    target = pd.Timestamp("2026-01-15 18:00", tz="UTC")
    print(f"=== EXAMPLE: every forecast for {target} ===")
    versions = forecasts[forecasts["start_time"] == target][["publish_time", "generation_mw"]]
    print(versions.to_string(index=False))
    actual = actuals.loc[actuals["start_time"] == target, "generation_mw"]
    if not actual.empty:
        print(f"Actual: {actual.iloc[0]:,.0f} MW")


def main() -> None:
    actuals, forecasts = load()
    report_actuals(actuals)
    report_forecasts(forecasts)
    show_example(forecasts, actuals)


if __name__ == "__main__":
    main()
