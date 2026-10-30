"""Core business logic: pick the forecast available at decision time and measure its error.

Sign convention used everywhere:
    error_mw = forecast_mw - actual_mw
    positive -> forecast was too high -> wind under-delivered -> buyer was short
    negative -> forecast was too low  -> buyer bought more than needed
"""

from datetime import date, datetime, time, timedelta

import numpy as np
import pandas as pd

from app.config import DECISION_DEADLINE_LOCAL, MARKET_TZ


def decision_cutoff(delivery_day: date, deadline: time = DECISION_DEADLINE_LOCAL) -> pd.Timestamp:
    """UTC moment by which orders for `delivery_day` must be placed (deadline on the day before)."""
    local = pd.Timestamp(datetime.combine(delivery_day - timedelta(days=1), deadline))
    return local.tz_localize(MARKET_TZ).tz_convert("UTC")


def _local_day(times: pd.Series) -> pd.Series:
    return times.dt.tz_convert(MARKET_TZ).dt.date


def select_day_ahead_forecasts(
    forecasts: pd.DataFrame, deadline: time = DECISION_DEADLINE_LOCAL
) -> pd.DataFrame:
    """For every target hour, keep the latest forecast published at or before its decision cutoff.

    Returns columns: start_time, publish_time, forecast_mw.
    """
    df = forecasts.copy()
    days = _local_day(df["start_time"])
    cutoffs = {day: decision_cutoff(day, deadline) for day in days.unique()}
    df["cutoff"] = pd.to_datetime(days.map(cutoffs), utc=True)

    available = df[df["publish_time"] <= df["cutoff"]]
    latest = available.sort_values("publish_time").groupby("start_time").tail(1)

    return (
        latest.rename(columns={"generation_mw": "forecast_mw"})[
            ["start_time", "publish_time", "forecast_mw"]
        ]
        .sort_values("start_time")
        .reset_index(drop=True)
    )


def compare_with_actuals(forecasts: pd.DataFrame, actuals: pd.DataFrame) -> pd.DataFrame:
    """Join forecasts to actuals on the same start time and add error and lead time.

    Forecasts are hourly and actuals half-hourly, so each forecast hour is compared
    with the actual half-hour that starts on that hour (no interpolation).
    Accepts the output of select_day_ahead_forecasts or the raw forecasts table.
    """
    fc = forecasts.rename(columns={"generation_mw": "forecast_mw"})
    act = actuals.rename(columns={"generation_mw": "actual_mw"})
    df = fc.merge(act, on="start_time", how="inner")
    df["error_mw"] = df["forecast_mw"] - df["actual_mw"]
    df["horizon_h"] = (df["start_time"] - df["publish_time"]).dt.total_seconds() / 3600
    return df


def error_metrics(compared: pd.DataFrame) -> dict:
    """Headline accuracy numbers for a set of forecast-vs-actual rows."""
    error = compared["error_mw"]
    mae = error.abs().mean()
    return {
        "count": int(len(error)),
        "mae_mw": round(float(mae), 1),
        "rmse_mw": round(float(np.sqrt((error**2).mean())), 1),
        "bias_mw": round(float(error.mean()), 1),
        # MAE as % of average actual output: comparable across periods of different windiness
        "nmae_pct": round(float(mae / compared["actual_mw"].mean() * 100), 1),
        # 80% of errors fall between p10 and p90 -> the "buffer" range for buying decisions
        "p10_mw": round(float(error.quantile(0.10)), 1),
        "p50_mw": round(float(error.quantile(0.50)), 1),
        "p90_mw": round(float(error.quantile(0.90)), 1),
        "max_over_mw": round(float(error.max()), 1),
        "max_under_mw": round(float(error.min()), 1),
    }


def _group_metrics(compared: pd.DataFrame, key: pd.Series) -> pd.DataFrame:
    grouped = compared.groupby(key)["error_mw"]
    return pd.DataFrame(
        {
            "count": grouped.size(),
            "mae_mw": grouped.apply(lambda e: e.abs().mean()).round(1),
            "rmse_mw": grouped.apply(lambda e: np.sqrt((e**2).mean())).round(1),
            "bias_mw": grouped.mean().round(1),
        }
    )


def error_by_horizon(compared_all_versions: pd.DataFrame, bucket_hours: int = 6) -> pd.DataFrame:
    """How accuracy changes with lead time. Use every forecast version, not just the selected one."""
    bucket = (compared_all_versions["horizon_h"] // bucket_hours * bucket_hours).astype(int)
    result = _group_metrics(compared_all_versions, bucket.rename("horizon_from_h")).reset_index()
    result["horizon_to_h"] = result["horizon_from_h"] + bucket_hours
    return result[["horizon_from_h", "horizon_to_h", "count", "mae_mw", "rmse_mw", "bias_mw"]]


def error_by_hour_of_day(compared: pd.DataFrame) -> pd.DataFrame:
    """Accuracy per UK local hour of the delivery day."""
    hour = compared["start_time"].dt.tz_convert(MARKET_TZ).dt.hour.rename("hour")
    return _group_metrics(compared, hour).reset_index()


def daily_summary(compared: pd.DataFrame) -> pd.DataFrame:
    """Accuracy per delivery day, plus the single worst hour of each day."""
    day = _local_day(compared["start_time"]).rename("delivery_day")
    result = _group_metrics(compared, day)
    result["max_abs_error_mw"] = compared.groupby(day)["error_mw"].apply(lambda e: e.abs().max())
    return result.reset_index()
