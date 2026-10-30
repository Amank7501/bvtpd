"""FastAPI application: HTTP endpoints for the wind forecast portal.

Run locally from the backend folder:
    uvicorn app.main:app --reload
Interactive docs: http://localhost:8000/docs
"""

from datetime import date, datetime, time

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app import service
from app.config import (
    ALLOWED_ORIGINS,
    DECISION_DEADLINE_LOCAL,
    DELIVERY_END,
    DELIVERY_START,
    MARKET_TZ,
)
from app.schemas import Accuracy, DayForecast, ForecastHistory, Meta

app = FastAPI(
    title="Wind Forecast Portal API",
    description="Day-ahead GB wind forecasts vs actuals (Elexon BMRS), January 2026 decisions.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)

DEFAULT_DEADLINE = DECISION_DEADLINE_LOCAL.strftime("%H:%M")


def deadline_param(
    deadline: str = Query(
        DEFAULT_DEADLINE,
        pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
        description="Order deadline in UK time on the day before delivery (HH:MM).",
    ),
) -> time:
    return time.fromisoformat(deadline)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/meta", response_model=Meta)
def meta():
    return {
        "delivery_start": DELIVERY_START,
        "delivery_end": DELIVERY_END,
        "default_deadline": DEFAULT_DEADLINE,
        "market_timezone": MARKET_TZ,
        "unit": "MW",
    }


@app.get("/api/forecast", response_model=DayForecast)
def forecast_for_day(
    day: date = Query(..., description="Delivery day, YYYY-MM-DD"),
    deadline: time = Depends(deadline_param),
):
    """The forecast the buyer had at the deadline for each hour of `day`, with actuals and errors."""
    if not DELIVERY_START <= day <= DELIVERY_END:
        raise HTTPException(404, f"No data for {day}. Available: {DELIVERY_START} to {DELIVERY_END}.")
    result = service.day_forecast(day, deadline)
    if result is None:
        raise HTTPException(404, f"No forecasts available for {day}.")
    return {**result, "deadline": deadline.strftime("%H:%M")}


@app.get("/api/accuracy", response_model=Accuracy)
def accuracy(deadline: time = Depends(deadline_param)):
    """Accuracy of day-ahead forecasts over the whole period, plus breakdowns."""
    return {**service.accuracy(deadline), "deadline": deadline.strftime("%H:%M")}


@app.get("/api/forecast-history", response_model=ForecastHistory)
def forecast_history(
    start_time: datetime = Query(..., description="Target hour, e.g. 2026-01-15T18:00:00Z"),
    deadline: time = Depends(deadline_param),
):
    """Every forecast version published for one target hour, marking the one used at the deadline."""
    target = pd.Timestamp(start_time)
    target = target.tz_localize("UTC") if target.tzinfo is None else target.tz_convert("UTC")
    result = service.forecast_history(target, deadline)
    if result is None:
        raise HTTPException(404, f"No forecasts for {target.isoformat()}. Use a whole hour in the window.")
    return {**result, "deadline": deadline.strftime("%H:%M")}
