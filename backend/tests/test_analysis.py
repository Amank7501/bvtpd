from datetime import date, time

import pandas as pd
import pytest

from app.analysis import (
    compare_with_actuals,
    decision_cutoff,
    error_by_horizon,
    error_metrics,
    select_day_ahead_forecasts,
)


def ts(value: str) -> pd.Timestamp:
    return pd.Timestamp(value, tz="UTC")


def forecasts_table(rows):
    return pd.DataFrame(
        [{"start_time": ts(s), "publish_time": ts(p), "generation_mw": g} for s, p, g in rows]
    )


def test_cutoff_is_deadline_on_previous_day_in_uk_time():
    assert decision_cutoff(date(2026, 1, 15), time(9, 0)) == ts("2026-01-14 09:00")


def test_cutoff_respects_british_summer_time():
    # In July the UK is UTC+1, so 09:00 local is 08:00 UTC.
    assert decision_cutoff(date(2026, 7, 15), time(9, 0)) == ts("2026-07-14 08:00")


def test_selects_latest_forecast_published_before_cutoff():
    forecasts = forecasts_table(
        [
            ("2026-01-15 18:00", "2026-01-13 22:30", 100),
            ("2026-01-15 18:00", "2026-01-14 07:30", 200),  # latest before 09:00 -> chosen
            ("2026-01-15 18:00", "2026-01-14 09:30", 300),  # after cutoff -> ignored
            ("2026-01-15 18:00", "2026-01-15 07:30", 400),  # after cutoff -> ignored
        ]
    )
    selected = select_day_ahead_forecasts(forecasts, time(9, 0))

    assert len(selected) == 1
    assert selected.loc[0, "forecast_mw"] == 200
    assert selected.loc[0, "publish_time"] == ts("2026-01-14 07:30")


def test_forecast_published_exactly_at_cutoff_is_allowed():
    forecasts = forecasts_table([("2026-01-15 00:00", "2026-01-14 09:00", 500)])
    assert select_day_ahead_forecasts(forecasts, time(9, 0)).loc[0, "forecast_mw"] == 500


def test_each_target_hour_gets_its_own_selection():
    forecasts = forecasts_table(
        [
            ("2026-01-15 00:00", "2026-01-14 07:30", 10),
            ("2026-01-16 00:00", "2026-01-14 07:30", 20),
            ("2026-01-16 00:00", "2026-01-15 07:30", 30),  # cutoff for 16th is 15th 09:00
        ]
    )
    selected = select_day_ahead_forecasts(forecasts, time(9, 0))
    assert selected["forecast_mw"].tolist() == [10, 30]


def test_compare_aligns_hourly_forecast_with_matching_half_hour_actual():
    forecasts = pd.DataFrame(
        {
            "start_time": [ts("2026-01-15 10:00")],
            "publish_time": [ts("2026-01-14 07:30")],
            "forecast_mw": [1000],
        }
    )
    actuals = pd.DataFrame(
        {
            "start_time": [ts("2026-01-15 10:00"), ts("2026-01-15 10:30")],
            "generation_mw": [800, 9999],
        }
    )
    compared = compare_with_actuals(forecasts, actuals)

    assert len(compared) == 1
    assert compared.loc[0, "error_mw"] == 200  # forecast too high by 200
    assert compared.loc[0, "horizon_h"] == pytest.approx(26.5)


def test_error_metrics_on_known_numbers():
    compared = pd.DataFrame({"error_mw": [100.0, -100.0, 300.0, -300.0], "actual_mw": [1000.0] * 4})
    m = error_metrics(compared)

    assert m["count"] == 4
    assert m["mae_mw"] == 200
    assert m["bias_mw"] == 0
    assert m["rmse_mw"] == pytest.approx(223.6, abs=0.1)
    assert m["nmae_pct"] == 20
    assert m["max_over_mw"] == 300
    assert m["max_under_mw"] == -300


def test_error_by_horizon_buckets_lead_time():
    compared = pd.DataFrame({"horizon_h": [1.0, 5.0, 7.0], "error_mw": [10.0, -30.0, 50.0]})
    result = error_by_horizon(compared, bucket_hours=6)

    first, second = result.iloc[0], result.iloc[1]
    assert (first["horizon_from_h"], first["horizon_to_h"], first["count"]) == (0, 6, 2)
    assert first["mae_mw"] == 20
    assert first["bias_mw"] == -10
    assert (second["horizon_from_h"], second["count"]) == (6, 1)
