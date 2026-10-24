
"""Tests for CareerPilot HTTP observability."""

import json
import re

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.observability import ObservabilityMiddleware


def test_each_request_receives_unique_request_id():
    test_app = FastAPI()
    test_app.add_middleware(ObservabilityMiddleware)

    @test_app.get("/ping")
    def ping():
        return {"status": "ok"}

    with TestClient(test_app) as client:
        first = client.get("/ping")
        second = client.get("/ping")

    assert first.status_code == 200
    assert second.status_code == 200

    first_id = first.headers["x-request-id"]
    second_id = second.headers["x-request-id"]

    assert re.fullmatch(r"[0-9a-f]{32}", first_id)
    assert re.fullmatch(r"[0-9a-f]{32}", second_id)
    assert first_id != second_id


def test_request_logging_contains_structured_fields(caplog):
    test_app = FastAPI()
    test_app.add_middleware(ObservabilityMiddleware)

    @test_app.get("/ping")
    def ping():
        return {"status": "ok"}

    with caplog.at_level("INFO", logger="backend.app.observability"):
        with TestClient(test_app) as client:
            response = client.get("/ping")

    records = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "backend.app.observability"
    ]

    assert len(records) == 1

    event = records[0]
    assert event["event"] == "http_request"
    assert event["request_id"] == response.headers["x-request-id"]
    assert event["method"] == "GET"
    assert event["status_code"] == 200
    assert isinstance(event["duration_ms"], (int, float))
    assert event["duration_ms"] >= 0


def test_rejected_request_is_logged_without_sensitive_data(caplog):
    test_app = FastAPI()

    @test_app.get("/private")
    def private():
        return {"status": "ok"}

    from starlette.responses import JSONResponse

    @test_app.middleware("http")
    async def reject_request(request, call_next):
        return JSONResponse(
            status_code=403,
            content={"detail": "Forbidden"},
        )

    test_app.add_middleware(ObservabilityMiddleware)

    secret = "private-resume-information"

    with caplog.at_level("INFO", logger="backend.app.observability"):
        with TestClient(test_app) as client:
            response = client.get(
                f"/private?resume={secret}"
            )

    assert response.status_code == 403
    assert "x-request-id" in response.headers

    records = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "backend.app.observability"
    ]

    assert len(records) == 1
    assert records[0]["status_code"] == 403
    assert records[0]["request_id"] == response.headers["x-request-id"]
    assert secret not in json.dumps(records)


def test_prometheus_request_counter_increments():
    from prometheus_client import REGISTRY

    test_app = FastAPI()
    test_app.add_middleware(ObservabilityMiddleware)

    @test_app.get("/ping")
    def ping():
        return {"status": "ok"}

    labels = {"method": "GET", "status_code": "200"}

    before = REGISTRY.get_sample_value(
        "careerpilot_http_requests_total",
        labels,
    ) or 0

    with TestClient(test_app) as client:
        response = client.get("/ping")

    after = REGISTRY.get_sample_value(
        "careerpilot_http_requests_total",
        labels,
    )

    assert response.status_code == 200
    assert after == before + 1


def test_prometheus_request_duration_histogram_records_request():
    from prometheus_client import REGISTRY

    test_app = FastAPI()
    test_app.add_middleware(ObservabilityMiddleware)

    @test_app.get("/ping")
    def ping():
        return {"status": "ok"}

    labels = {"method": "GET", "status_code": "200"}

    before = REGISTRY.get_sample_value(
        "careerpilot_http_request_duration_seconds_count",
        labels,
    ) or 0

    with TestClient(test_app) as client:
        response = client.get("/ping")

    after = REGISTRY.get_sample_value(
        "careerpilot_http_request_duration_seconds_count",
        labels,
    )

    assert response.status_code == 200
    assert after == before + 1
