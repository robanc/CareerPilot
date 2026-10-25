# CareerPilot Observability

CareerPilot includes a local OpenTelemetry monitoring stack
for collecting and visualizing application metrics, traces,
and structured logs.

## Architecture

- OpenTelemetry SDK: Instruments the CareerPilot FastAPI backend.
- OpenTelemetry Collector: Receives and routes telemetry.
- Prometheus: Stores application metrics.
- Tempo: Stores distributed traces.
- Loki: Stores structured application logs.
- Grafana: Visualizes metrics, traces, and logs.

## Monitoring Scope

The monitoring stack runs as a separate Docker Compose project
named `careerpilot-monitoring`.

All published monitoring ports are bound to `127.0.0.1`
for local development.

Telemetry export from the CareerPilot backend is opt-in.
It is disabled unless `CAREERPILOT_OTLP_ENABLED=true`.

This setup does not require access to the CareerPilot
development or test PostgreSQL databases.

The monitoring stack is not configured for the Render deployment.

## Starting the Monitoring Stack

From the CareerPilot project root, run:

```powershell
docker compose -f monitoring/docker-compose.yml up -d --pull never
```

This starts the five monitoring services using locally available images.

### Local Monitoring URLs

| Service | URL |
|---|---|
| Grafana | http://127.0.0.1:3000 |
| Prometheus | http://127.0.0.1:9090 |
| Tempo | http://127.0.0.1:3200 |
| Loki | http://127.0.0.1:3100 |

### Check Container Status

```powershell
docker compose -f monitoring/docker-compose.yml ps
```

### Stop the Monitoring Stack

```powershell
docker compose -f monitoring/docker-compose.yml stop
```

Use `stop` to preserve monitoring data volumes.

Do not use `down -v` unless you intentionally want to delete monitoring data.

## Observability Verification

The CareerPilot backend uses the OpenTelemetry SDK to export
metrics, traces, and structured logs to the local Collector.

All three signals use the service name `careerpilot-backend`.

### Metrics — Prometheus

Open Grafana at http://127.0.0.1:3000.

1. Navigate to Explore.
2. Select the Prometheus data source.
3. Enter this PromQL query:

```promql
careerpilot_http_requests_total{exported_job="careerpilot-backend"}
```

The metric records HTTP requests by method and status code.

The following duration metrics are also available:

- `careerpilot_http_request_duration_seconds_bucket`
- `careerpilot_http_request_duration_seconds_count`
- `careerpilot_http_request_duration_seconds_sum`

Metrics are exported only when OpenTelemetry is enabled.
Historical data may remain available after the test process exits.

### Traces — Tempo

1. Open Grafana Explore.
2. Select the Tempo data source.
3. Search for traces from `careerpilot-backend`.
4. Open a trace to inspect its spans and execution timeline.

CareerPilot instruments HTTP requests with an `http.request` span.

The resume-matching service also creates a `resume.match` span,
allowing the matching operation to be inspected in Tempo.

### Structured Logs — Loki

1. Open Grafana Explore.
2. Select the Loki data source.
3. Enter this LogQL query:

```logql
{service_name="careerpilot-backend"}
```

HTTP request logs include:

- `event`
- `request_id`
- `trace_id`
- `method`
- `status_code`
- `duration_ms`

To find logs for a specific request, use:

```logql
{service_name="careerpilot-backend"} |= "REQUEST_ID"
```

Replace `REQUEST_ID` with the request identifier returned
in the HTTP `x-request-id` response header.

### Trace and Log Correlation

The `trace_id` in a structured HTTP request log identifies
the corresponding trace stored in Tempo.

This allows a request to be investigated across logs and traces.

The correlation was verified using synthetic test requests.
No real resumes or personal information were required.

## Privacy and Security

- Telemetry export is disabled by default.
- Local telemetry export requires `CAREERPILOT_OTLP_ENABLED=true`.
- Monitoring ports are published only on `127.0.0.1`.
- HTTP request logs do not include request bodies or resume text.
- Monitoring does not require PostgreSQL database access.
- Monitoring is not enabled in the Render deployment.
- Loki authentication is disabled for this local-only setup.
- Loki log retention is not explicitly configured.

Do not expose this monitoring stack publicly without
appropriate authentication, network restrictions, and
additional security controls.

## Validation Results

The observability implementation was verified using
synthetic requests and test data.

Verified capabilities:

- OpenTelemetry Collector receives telemetry.
- Prometheus receives CareerPilot HTTP metrics.
- Tempo stores HTTP and resume-matching traces.
- Loki stores structured HTTP request logs.
- Grafana connects successfully to all three data sources.
- HTTP request logs and traces share matching trace IDs.
- All three telemetry signals use `careerpilot-backend`
  as the service identity.
- All 10 observability tests passed.

These checks were performed locally without modifying
the development PostgreSQL database or deploying to Render.