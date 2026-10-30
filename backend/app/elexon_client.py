"""Thin client for the two Elexon BMRS datasets we use.

- FUELHH  : actual generation by fuel type, half-hourly (we keep WIND only)
- WINDFOR : national wind generation forecasts, hourly, re-published several times a day
"""

import time
from datetime import date, datetime, timedelta

import requests

from app.config import ELEXON_BASE_URL

REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 4
CHUNK_DAYS = 7  # keep each request small so a single call never gets too large


class ElexonError(RuntimeError):
    pass


def _get(path: str, params: dict) -> list[dict]:
    """GET a dataset endpoint, retrying on rate limits (429) and server errors (5xx)."""
    url = f"{ELEXON_BASE_URL}{path}"
    for attempt in range(1, MAX_RETRIES + 1):
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        if response.status_code == 200:
            return response.json()
        if response.status_code == 429 or response.status_code >= 500:
            wait = 2**attempt
            print(f"  Elexon returned {response.status_code}, retrying in {wait}s...")
            time.sleep(wait)
            continue
        raise ElexonError(f"{response.status_code} from {url}: {response.text[:200]}")
    raise ElexonError(f"Gave up on {url} after {MAX_RETRIES} attempts")


def _date_chunks(start: date, end: date):
    """Split [start, end] (inclusive) into consecutive chunks of CHUNK_DAYS."""
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(chunk_start + timedelta(days=CHUNK_DAYS - 1), end)
        yield chunk_start, chunk_end
        chunk_start = chunk_end + timedelta(days=1)


def fetch_wind_actuals(start: date, end: date) -> list[dict]:
    """Actual wind generation for settlement dates start..end (inclusive)."""
    rows = []
    for chunk_start, chunk_end in _date_chunks(start, end):
        rows += _get(
            "/datasets/FUELHH/stream",
            {
                "settlementDateFrom": chunk_start.isoformat(),
                "settlementDateTo": chunk_end.isoformat(),
                "fuelType": "WIND",
            },
        )
    return rows


def fetch_wind_forecasts(start: date, end: date) -> list[dict]:
    """Every wind forecast published between start 00:00 and end 23:59:59 UTC."""
    rows = []
    for chunk_start, chunk_end in _date_chunks(start, end):
        publish_from = datetime.combine(chunk_start, datetime.min.time())
        publish_to = datetime.combine(chunk_end, datetime.max.time()).replace(microsecond=0)
        rows += _get(
            "/datasets/WINDFOR/stream",
            {
                "publishDateTimeFrom": publish_from.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "publishDateTimeTo": publish_to.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )
    return rows
