"""Print the forecast accuracy results for January 2026 decisions.

Run from the backend folder:
    python -m scripts.accuracy_report
"""

import pandas as pd

from app.analysis import (
    compare_with_actuals,
    daily_summary,
    decision_cutoff,
    error_by_horizon,
    error_by_hour_of_day,
    error_metrics,
    select_day_ahead_forecasts,
)
from app.config import DECISION_DEADLINE_LOCAL, DELIVERY_START
from app.data_store import load_actuals, load_forecasts


def main() -> None:
    actuals, forecasts = load_actuals(), load_forecasts()

    print(f"Decision deadline: {DECISION_DEADLINE_LOCAL:%H:%M} UK time on the day before delivery")
    print(f"e.g. delivery {DELIVERY_START} -> cutoff {decision_cutoff(DELIVERY_START)}\n")

    selected = select_day_ahead_forecasts(forecasts)
    compared = compare_with_actuals(selected, actuals)

    print("=== DAY-AHEAD FORECAST ACCURACY (forecast - actual) ===")
    for name, value in error_metrics(compared).items():
        print(f"  {name:<14}{value:>10,}")

    lead = compared["horizon_h"]
    print(f"\nLead time of the forecasts used: {lead.min():.1f}h to {lead.max():.1f}h ahead\n")

    print("=== ERROR BY LEAD TIME (all forecast versions) ===")
    print(error_by_horizon(compare_with_actuals(forecasts, actuals)).to_string(index=False))

    print("\n=== ERROR BY HOUR OF DAY (UK time) ===")
    print(error_by_hour_of_day(compared).to_string(index=False))

    print("\n=== 5 WORST DELIVERY DAYS (by MAE) ===")
    with pd.option_context("display.width", 120):
        print(daily_summary(compared).nlargest(5, "mae_mw").to_string(index=False))


if __name__ == "__main__":
    main()
