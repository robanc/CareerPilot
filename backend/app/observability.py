
"""Privacy-conscious HTTP request logging and correlation IDs."""

import json
import logging
import time
import uuid

from prometheus_client import Counter, Histogram
from starlette.types import ASGIApp, Message, Receive, Scope, Send


logger = logging.getLogger(__name__)

HTTP_REQUESTS = Counter(
    "careerpilot_http_requests_total",
    "Total HTTP requests handled by CareerPilot.",
    ["method", "status_code"],
)

HTTP_REQUEST_DURATION = Histogram(
    "careerpilot_http_request_duration_seconds",
    "Duration of HTTP requests handled by CareerPilot.",
    ["method", "status_code"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf")),
)

class ObservabilityMiddleware:
    """Record HTTP outcomes without logging user-submitted content."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex
        started = time.perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code

            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append(
                    (b"x-request-id", request_id.encode("ascii"))
                )
                message = {**message, "headers": headers}

            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            duration_ms = round(
                (time.perf_counter() - started) * 1000, 2
            )

            method = scope["method"].upper()
            status = str(status_code)
            duration_seconds = duration_ms / 1000

            HTTP_REQUESTS.labels(
                method=method,
                status_code=status,
            ).inc()

            HTTP_REQUEST_DURATION.labels(
                method=method,
                status_code=status,
            ).observe(duration_seconds)

            logger.info(
                json.dumps(
                    {
                        "event": "http_request",
                        "request_id": request_id,
                        "method": scope["method"],
                        "status_code": status_code,
                        "duration_ms": duration_ms,
                    }
                )
            )
