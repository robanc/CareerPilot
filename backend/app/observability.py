
"""Privacy-conscious HTTP request logging and correlation IDs."""

import json
import logging
import os
import time
import uuid

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import Counter, Histogram
from starlette.types import ASGIApp, Message, Receive, Scope, Send


logger = logging.getLogger(__name__)

service_resource = Resource.create({
    "service.name": "careerpilot-backend",
})

log_provider = None

if os.getenv("CAREERPILOT_OTLP_ENABLED", "").lower() == "true":
    log_provider = LoggerProvider(resource=service_resource)

    log_exporter = OTLPLogExporter(
        endpoint="http://127.0.0.1:4318/v1/logs",
        timeout=5,
    )

    log_provider.add_log_record_processor(
        BatchLogRecordProcessor(log_exporter)
    )

    log_handler = LoggingHandler(
        level=logging.INFO,
        logger_provider=log_provider,
    )

    logger.addHandler(log_handler)
    logger.setLevel(logging.INFO)

provider = TracerProvider(resource=service_resource)

if os.getenv("CAREERPILOT_OTLP_ENABLED", "").lower() == "true":
    exporter = OTLPSpanExporter(
        endpoint="http://127.0.0.1:4318/v1/traces",
        timeout=5,
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))

trace.set_tracer_provider(provider)
tracer = trace.get_tracer("careerpilot.backend")

metric_reader = None

if os.getenv("CAREERPILOT_OTLP_ENABLED", "").lower() == "true":
    metric_exporter = OTLPMetricExporter(
        endpoint="http://127.0.0.1:4318/v1/metrics",
        timeout=5,
    )
    metric_reader = PeriodicExportingMetricReader(
        metric_exporter,
        export_interval_millis=5000,
    )
    meter_provider = MeterProvider(
        metric_readers=[metric_reader],
        resource=service_resource,
    )
    metrics.set_meter_provider(meter_provider)

meter = metrics.get_meter("careerpilot.backend")

OTEL_HTTP_REQUESTS = meter.create_counter(
    "careerpilot.http.requests",
    description="Total HTTP requests handled by CareerPilot.",
    unit="1",
)

OTEL_HTTP_DURATION = meter.create_histogram(
    "careerpilot.http.request.duration",
    description="HTTP request duration.",
    unit="s",
)

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

        with tracer.start_as_current_span("http.request"):
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

                OTEL_HTTP_REQUESTS.add(
                    1,
                    attributes={
                        "method": method,
                        "status_code": status,
                    },
                )

                OTEL_HTTP_DURATION.record(
                    duration_seconds,
                    attributes={
                        "method": method,
                        "status_code": status,
                    },
                )

                logger.info(
                    json.dumps(
                        {
                            "event": "http_request",
                            "request_id": request_id,
                            "trace_id": format(
                                trace.get_current_span().get_span_context().trace_id,
                                "032x",
                            ),
                            "method": scope["method"],
                            "status_code": status_code,
                            "duration_ms": duration_ms,
                        }
                    )
                )
