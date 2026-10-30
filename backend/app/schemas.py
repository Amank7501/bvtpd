"""Shapes of the API responses. FastAPI uses these to validate output and build /docs."""

from datetime import date, datetime

from pydantic import BaseModel


class Meta(BaseModel):
    delivery_start: date
    delivery_end: date
    default_deadline: str
    market_timezone: str
    unit: str


class Metrics(BaseModel):
    count: int
    mae_mw: float
    rmse_mw: float
    bias_mw: float
    nmae_pct: float
    p10_mw: float
    p50_mw: float
    p90_mw: float
    max_over_mw: float
    max_under_mw: float


class HourPoint(BaseModel):
    start_time: datetime
    publish_time: datetime
    horizon_h: float
    forecast_mw: float
    actual_mw: float | None
    error_mw: float | None


class ActualPoint(BaseModel):
    start_time: datetime
    actual_mw: float


class DayForecast(BaseModel):
    delivery_day: date
    deadline: str
    cutoff_utc: datetime
    hourly: list[HourPoint]
    actuals: list[ActualPoint]
    metrics: Metrics


class GroupStats(BaseModel):
    count: int
    mae_mw: float
    rmse_mw: float
    bias_mw: float


class HourOfDayRow(GroupStats):
    hour: int


class DayRow(GroupStats):
    delivery_day: date
    max_abs_error_mw: float


class HorizonRow(GroupStats):
    horizon_from_h: int
    horizon_to_h: int


class Accuracy(BaseModel):
    deadline: str
    metrics: Metrics
    by_hour: list[HourOfDayRow]
    by_day: list[DayRow]
    by_horizon: list[HorizonRow]


class ForecastVersion(BaseModel):
    publish_time: datetime
    horizon_h: float
    forecast_mw: float
    available_at_deadline: bool
    selected: bool


class ForecastHistory(BaseModel):
    start_time: datetime
    deadline: str
    cutoff_utc: datetime
    actual_mw: float | None
    versions: list[ForecastVersion]
