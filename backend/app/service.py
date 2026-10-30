"""Glue between the API and the analysis: picks the right data, caches heavy work,
and turns DataFrames into plain JSON-ready dicts.

Cached DataFrames are shared between requests, so callers must not modify them.
"""

import json
from datetime import date, time
from functools import lru_cache

import pandas as pd

from app import analysis
from app.data_store import load_actuals, load_forecasts


def records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> list of dicts with ISO timestamps and NaN as None."""
    return json.loads(df.to_json(orient="records", date_format="iso"))


@lru_cache(maxsize=32)
def day_ahead_comparison(deadline: time) -> pd.DataFrame:
    """Selected day-ahead forecast vs actual for every hour, for one deadline."""
    selected = analysis.select_day_ahead_forecasts(load_forecasts(), deadline)
    return analysis.compare_with_actuals(selected, load_actuals())


@lru_cache(maxsize=1)
def all_versions_comparison() -> pd.DataFrame:
    """Every forecast version vs actual (independent of the deadline)."""
    return analysis.compare_with_actuals(load_forecasts(), load_actuals())


def day_forecast(day: date, deadline: time) -> dict | None:
    compared = day_ahead_comparison(deadline)
    hourly = compared[analysis.local_day(compared["start_time"]) == day]
    if hourly.empty:
        return None

    actuals = load_actuals()
    actuals = actuals[analysis.local_day(actuals["start_time"]) == day]

    return {
        "delivery_day": day,
        "cutoff_utc": analysis.decision_cutoff(day, deadline),
        "hourly": records(
            hourly[["start_time", "publish_time", "horizon_h", "forecast_mw", "actual_mw", "error_mw"]]
        ),
        "actuals": records(actuals.rename(columns={"generation_mw": "actual_mw"})),
        "metrics": analysis.error_metrics(hourly),
    }


def accuracy(deadline: time) -> dict:
    compared = day_ahead_comparison(deadline)
    by_day = analysis.daily_summary(compared)
    by_day["delivery_day"] = by_day["delivery_day"].astype(str)
    return {
        "metrics": analysis.error_metrics(compared),
        "by_hour": records(analysis.error_by_hour_of_day(compared)),
        "by_day": records(by_day),
        "by_horizon": records(analysis.error_by_horizon(all_versions_comparison())),
    }


def forecast_history(start_time: pd.Timestamp, deadline: time) -> dict | None:
    versions = all_versions_comparison()
    versions = versions[versions["start_time"] == start_time].sort_values("publish_time")
    if versions.empty:
        return None

    day = analysis.local_day(pd.Series([start_time])).iloc[0]
    cutoff = analysis.decision_cutoff(day, deadline)
    available = versions["publish_time"] <= cutoff

    table = versions[["publish_time", "horizon_h", "forecast_mw"]].copy()
    table["available_at_deadline"] = available
    table["selected"] = False
    if available.any():
        table.loc[versions[available].index[-1], "selected"] = True

    return {
        "start_time": start_time,
        "cutoff_utc": cutoff,
        "actual_mw": versions["actual_mw"].iloc[0],
        "versions": records(table),
    }
