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

## Alerting

Prometheus evaluates local alert rules from
`monitoring/alerts/careerpilot.rules.yml`, mounted read-only
into the Prometheus container at `/etc/prometheus/alerts`.

Alerting is local-only:

- Firing and pending alerts are visible at
  http://127.0.0.1:9090/alerts and through the Grafana
  Prometheus data source (`ALERTS` series).
- No Alertmanager is configured.
- No notifications (email, chat, paging) are sent.
- Alerting is not enabled in the Render deployment.

### Alert Rules

| Alert | Condition | For | Severity |
|---|---|---|---|
| `CareerPilotHigh5xxRate` | 5xx responses above 5% of requests over 5 minutes, with at least 10 requests in that window | 5m | warning |
| `CareerPilotHighAverageLatency` | Average request duration above 0.5 seconds over 5 minutes | 10m | warning |
| `CareerPilotBackendTelemetryMissing` | No `careerpilot_http_requests_total{exported_job="careerpilot-backend"}` series | 5m | info |
| `CareerPilotOtelCollectorDown` | `up{job="careerpilot-otel-collector"} == 0` | 2m | warning |

The rules use the metrics exported over OTLP and re-exposed
by the OpenTelemetry Collector:

- `careerpilot_http_requests_total`
- `careerpilot_http_request_duration_seconds_sum`
- `careerpilot_http_request_duration_seconds_count`

The backend service name appears as the `exported_job` label.
Request metrics carry `method` and `status_code` labels;
there is no per-route label.

Latency is alerted on the average (sum divided by count).
The OTLP histogram uses the OpenTelemetry SDK's default
bucket boundaries, so percentile alerts are not configured.

### Expected Telemetry-Missing Alerts

`CareerPilotBackendTelemetryMissing` is expected to fire
in normal local use when:

- `CAREERPILOT_OTLP_ENABLED` is not `true`.
- The backend is not running.
- The backend has started but has not yet served a request.

The Collector drops backend series about 5 minutes after
the last update, so the alert fires roughly 10 minutes
after the backend stops exporting.

If the Collector itself is down, both
`CareerPilotOtelCollectorDown` and
`CareerPilotBackendTelemetryMissing` fire.

### Validating Alert Rules

The rules have unit tests in
`monitoring/alerts/tests/careerpilot.rules.test.yml`.
They use synthetic series only and need no running
monitoring services, backend, or database.

The test file is outside the `*.rules.yml` glob, so
Prometheus does not load it as a rule file.

The CI `monitoring-config` job runs `promtool` from the
pinned Prometheus image. To run the same checks locally:

```powershell
docker run --rm --entrypoint /bin/promtool `
  --volume "${PWD}/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro" `
  --volume "${PWD}/monitoring/alerts:/etc/prometheus/alerts:ro" `
  prom/prometheus:v3.14.0 check config /etc/prometheus/prometheus.yml

docker run --rm --entrypoint /bin/promtool `
  --volume "${PWD}/monitoring/alerts:/etc/prometheus/alerts:ro" `
  prom/prometheus:v3.14.0 test rules /etc/prometheus/alerts/tests/careerpilot.rules.test.yml
```

These commands start a short-lived `promtool` container
only. They do not affect the running monitoring stack.

The `alerts` volume mount is new, so an existing Prometheus
container must be recreated once to pick it up. This keeps
the `prometheus_data` volume:

```powershell
docker compose -f monitoring/docker-compose.yml up -d --pull never prometheus
```

After that, Prometheus loads rule edits on restart:

```powershell
docker compose -f monitoring/docker-compose.yml restart prometheus
```

## Privacy and Security

- Telemetry export is disabled by default.
- Local telemetry export requires `CAREERPILOT_OTLP_ENABLED=true`.
- Monitoring ports are published only on `127.0.0.1`.
- HTTP request logs do not include request bodies or resume text.
- Monitoring does not require PostgreSQL database access.
- Monitoring is not enabled in the Render deployment.
- Loki authentication is disabled for this local-only setup.
- Loki log retention is not explicitly configured.
- Alert rules are evaluated locally; no alert notifications are configured.

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