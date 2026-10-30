"""End-to-end API tests against the saved January 2026 data."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_meta_describes_window():
    body = client.get("/api/meta").json()
    assert body["delivery_start"] == "2026-01-02"
    assert body["delivery_end"] == "2026-02-01"
    assert body["default_deadline"] == "09:00"


def test_forecast_for_day():
    response = client.get("/api/forecast", params={"day": "2026-01-15"})
    assert response.status_code == 200
    body = response.json()

    assert body["cutoff_utc"].startswith("2026-01-14T09:00")
    assert len(body["hourly"]) == 24
    assert len(body["actuals"]) == 48
    assert body["metrics"]["count"] == 24
    # Every forecast used must have been published before the cutoff.
    assert all(point["publish_time"] <= body["cutoff_utc"] for point in body["hourly"])


def test_forecast_day_outside_window_is_404():
    assert client.get("/api/forecast", params={"day": "2025-06-01"}).status_code == 404


def test_invalid_deadline_is_rejected():
    response = client.get("/api/forecast", params={"day": "2026-01-15", "deadline": "25:00"})
    assert response.status_code == 422


def test_accuracy_summary():
    body = client.get("/api/accuracy").json()
    assert body["metrics"]["count"] == 744
    assert len(body["by_hour"]) == 24
    assert len(body["by_day"]) == 31
    assert body["by_horizon"][0]["horizon_from_h"] == 0


def test_later_deadline_uses_fresher_forecasts():
    early = client.get("/api/forecast", params={"day": "2026-01-15", "deadline": "06:00"}).json()
    late = client.get("/api/forecast", params={"day": "2026-01-15", "deadline": "23:00"}).json()

    def mean_horizon(body):
        return sum(p["horizon_h"] for p in body["hourly"]) / len(body["hourly"])

    assert mean_horizon(late) < mean_horizon(early)


def test_forecast_history_marks_selected_version():
    response = client.get("/api/forecast-history", params={"start_time": "2026-01-15T18:00:00Z"})
    assert response.status_code == 200
    body = response.json()

    selected = [v for v in body["versions"] if v["selected"]]
    assert len(selected) == 1
    assert selected[0]["available_at_deadline"]
    assert selected[0]["publish_time"] <= body["cutoff_utc"]
    assert body["actual_mw"] == 7672


def test_forecast_history_unknown_hour_is_404():
    response = client.get("/api/forecast-history", params={"start_time": "2026-01-15T18:30:00Z"})
    assert response.status_code == 404
