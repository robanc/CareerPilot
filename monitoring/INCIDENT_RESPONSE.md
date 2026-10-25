# CareerPilot Incident Response Runbook

This runbook explains how to respond to the four local
Prometheus alerts defined in
`monitoring/alerts/careerpilot.rules.yml`.

## 1. Purpose and Scope

This runbook covers:

- `CareerPilotHigh5xxRate`
- `CareerPilotHighAverageLatency`
- `CareerPilotBackendTelemetryMissing`
- `CareerPilotOtelCollectorDown`

Scope and limits:

- **Local development only.** The alerts run in the local
  `careerpilot-monitoring` Docker Compose project, with all
  ports bound to `127.0.0.1`.
- **No Alertmanager is configured.** No email, chat, paging,
  or other notification is sent.
- **No on-call rotation exists.** Detection is manual:
  someone must open http://127.0.0.1:9090/alerts or query
  the `ALERTS` series in Grafana.
- **Render is not monitored.** These alerts do not cover the
  public demo on Render. For Render, see
  `docs/deployment-render.md`.
- If Prometheus is stopped, no alert is evaluated.
  "No alerts" does not mean "healthy".

For the monitoring stack itself, see `monitoring/README.md`.

## 2. Safety Rules

These rules apply to every step of this runbook, whether a
developer or an AI agent is responding.

- **Read-only first.** Investigation uses read-only queries
  and status commands only.
- **Developer approval is required** before any restart,
  container recreation, configuration change, code change,
  or other remediation.
- **No database changes.** Do not run `DROP`, `TRUNCATE`,
  bulk `DELETE`, migrations, or resets. Do not connect to the
  development database without explicit approval. Never point
  tests or cleanup at it.
- **No destructive Docker commands.** Never run
  `docker compose down -v`, and never remove the
  `prometheus_data`, `postgres_data`, or other volumes.
- **No secrets.** Do not read, print, or paste `.env` values,
  credentials, tokens, or keys into incident notes. Use
  `--quiet` with `docker compose config`.
- **No resume content.** Never copy request bodies, resume
  text, or job descriptions into incident records. Request IDs
  and trace IDs are safe to record.
- **Render is out of scope.** Do not deploy or change Render
  as part of responding to a local alert.

## 3. Severity Levels

Only the two severities used by the existing rules apply.

| Severity | Alerts | Meaning | Response |
|---|---|---|---|
| `warning` | `CareerPilotHigh5xxRate`, `CareerPilotHighAverageLatency`, `CareerPilotOtelCollectorDown` | A real problem is likely. | Triage now. |
| `info` | `CareerPilotBackendTelemetryMissing` | Often expected locally. | Work through [section 6](#6-expected-versus-unexpected-missing-telemetry) before treating it as an incident. |

No `critical` severity is defined.

## 4. First Five Minutes

1. Open http://127.0.0.1:9090/alerts. Note the alert name,
   labels, state (`pending` or `firing`), and active time.
2. Confirm Prometheus can scrape the Collector:

   ```promql
   up{job="careerpilot-otel-collector"}
   ```

3. Check the monitoring containers (read-only):

   ```powershell
   docker compose -f monitoring/docker-compose.yml ps
   ```

4. Establish how the backend is running:
   - Running at all?
   - Started on the host, or inside Docker Compose?
   - Started with `CAREERPILOT_OTLP_ENABLED=true`?
5. Choose the playbook:
   - Collector down: [5.4](#54-careerpilototelcollectordown-warning)
   - Telemetry missing: [section 6](#6-expected-versus-unexpected-missing-telemetry)
   - 5xx rate: [5.1](#51-careerpilothigh5xxrate-warning)
   - Latency: [5.2](#52-careerpilothighaveragelatency-warning)

If several alerts fire together, start with the Collector.
A Collector outage can also lead to
`CareerPilotBackendTelemetryMissing` once that alert's own
delay has passed.

## 5. Alert Playbooks

All backend metrics carry `exported_job="careerpilot-backend"`
and the labels `method` and `status_code`. There is no route
or path label.

### 5.1 CareerPilotHigh5xxRate (warning)

**Meaning:** More than 5% of backend requests returned a 5xx
status over 5 minutes, with at least 10 requests in that
window, sustained for 5 minutes.

**Likely causes:**

- Database unreachable or misconfigured.
- Unhandled exception in a route. The middleware records
  unhandled exceptions as status `500`.
- A recent local code or configuration change.

**Investigate (Prometheus / Grafana):**

Current 5xx ratio:

```promql
sum(rate(careerpilot_http_requests_total{exported_job="careerpilot-backend", status_code=~"5.."}[5m])) / sum(rate(careerpilot_http_requests_total{exported_job="careerpilot-backend"}[5m]))
```

Request rate by method and status code:

```promql
sum by (method, status_code) (rate(careerpilot_http_requests_total{exported_job="careerpilot-backend"}[5m]))
```

**Investigate (Loki):** find failing requests and their IDs.

```logql
{service_name="careerpilot-backend"} | json | status_code >= 500
```

> **Unverified:** this query assumes the Loki log line is the
> raw JSON request log. If `| json` does not extract fields,
> fall back to `{service_name="careerpilot-backend"} |= "\"status_code\": 5"`.

**Investigate (Tempo):** copy a `trace_id` from a failing log
line and open it in Grafana Explore with the Tempo data source.
Check the `http.request` span and, for resume matching, the
`resume.match` span.

**Database checks:** limited to read-only signals, such as
the backend `/health` response and backend startup logs.
Do not query, repair, or reset the database without approval.

**Recover (developer approval required):** fix the code or
configuration, or restart the backend.

**Verify:** see [section 8](#8-recovery-verification).
The ratio must stay below 5% over a full 5-minute window.

### 5.2 CareerPilotHighAverageLatency (warning)

**Meaning:** The average request duration (sum divided by
count) has been above 0.5 seconds for 10 minutes.

**Likely causes:**

- Large resume-matching inputs.
- Slow database responses.
- A resource-constrained host.

**Investigate (Prometheus / Grafana):**

Average latency in seconds:

```promql
sum(rate(careerpilot_http_request_duration_seconds_sum{exported_job="careerpilot-backend"}[5m])) / sum(rate(careerpilot_http_request_duration_seconds_count{exported_job="careerpilot-backend"}[5m]))
```

Average latency in seconds, by method:

```promql
sum by (method) (rate(careerpilot_http_request_duration_seconds_sum{exported_job="careerpilot-backend"}[5m])) / sum by (method) (rate(careerpilot_http_request_duration_seconds_count{exported_job="careerpilot-backend"}[5m]))
```

Do not use `histogram_quantile()` on these metrics. The OTLP
histogram uses the SDK's default bucket boundaries, so
percentiles are not meaningful.

**Investigate (Loki):** find slow requests.

```logql
{service_name="careerpilot-backend"} | json | duration_ms > 500
```

> **Unverified:** same `| json` assumption as in 5.1.

**Investigate (Tempo):** open the `trace_id` of slow requests.
Compare the `resume.match` span duration with the overall
`http.request` span.

**Limitation:** metrics, logs, and spans do not record the
route. Identify the slow endpoint from trace contents and
timing.

**Recover (developer approval required):** address the
cause, for example a code fix or reducing local load.

**Verify:** see [section 8](#8-recovery-verification).
The average must stay below 0.5 seconds.

### 5.3 CareerPilotBackendTelemetryMissing (info)

**Meaning:** No `careerpilot_http_requests_total` series with
`exported_job="careerpilot-backend"` has been present in
Prometheus for 5 minutes.

This alert is often expected locally. Use the decision table in
[section 6](#6-expected-versus-unexpected-missing-telemetry)
before treating it as an incident.

### 5.4 CareerPilotOtelCollectorDown (warning)

**Meaning:** Prometheus has failed to scrape the OpenTelemetry
Collector (`up{job="careerpilot-otel-collector"} == 0`) for
2 minutes.

**Impact:**

- The backend keeps serving requests.
- Backend telemetry sent during the outage may be delayed or
  lost, depending on outage duration. Traces and logs are
  held in bounded in-memory SDK queues, and the backend's
  OTLP exporters use a 5-second timeout. A short outage may
  lose little; a longer one is likely to leave a gap in
  Grafana. How much is lost has not been measured.
- Backend counters are exported as cumulative totals, so
  totals are expected to be correct again after exports
  resume, but samples for the outage window may be missing.
- When the scrape fails, Prometheus marks the Collector's
  series stale. `CareerPilotBackendTelemetryMissing` may then
  fire after its own 5-minute `for` delay, which is later than
  this alert's 2 minutes. If the outage ends sooner, it may
  not fire at all.
- If both alerts fire, treat the Collector as the root cause.

**Investigate (read-only):**

```powershell
docker compose -f monitoring/docker-compose.yml ps
docker compose -f monitoring/docker-compose.yml logs --tail 100 otel-collector
```

Also check the target state at http://127.0.0.1:9090/targets.

**Recover (developer approval required):**

```powershell
docker compose -f monitoring/docker-compose.yml restart otel-collector
```

If the container no longer exists, recreate only that service:

```powershell
docker compose -f monitoring/docker-compose.yml up -d --pull never otel-collector
```

**Verify:** `up{job="careerpilot-otel-collector"}` returns `1`.
If OTLP export is enabled, backend series reappear after the
backend next handles a request and exports.
See [section 8](#8-recovery-verification).

## 6. Expected Versus Unexpected Missing Telemetry

Work through this table top to bottom for
`CareerPilotBackendTelemetryMissing`.

| Check | Classification | Action |
|---|---|---|
| `CareerPilotOtelCollectorDown` is also firing, or `up{job="careerpilot-otel-collector"}` is `0`. | **Incident** | Follow [5.4](#54-careerpilototelcollectordown-warning). |
| `CAREERPILOT_OTLP_ENABLED` is not `true`. | **Expected** | None. Telemetry export is opt-in. |
| The backend is intentionally stopped. | **Expected** | None. |
| The backend has started but has not yet served a request. | **Expected** | Clears after the first request. |
| The backend runs inside Docker Compose (port 8002). | **Expected (configuration)** | See the Docker networking note below. |
| OTLP enabled, backend running on the host, serving requests, and series still missing. | **Incident** | Check Collector logs, the Prometheus targets page, and whether the backend can reach `127.0.0.1:4318`. |

**Timing:** the Collector stops exposing a series about
5 minutes after its last update, and the alert then waits
5 minutes. The alert therefore appears roughly 10 minutes
after export stops. This is derived from configuration
defaults and the rule; it has not been measured.

> **Unverified Docker networking assumption:** the backend
> exports OTLP to the hard-coded endpoint `127.0.0.1:4318`.
> Inside a Docker container, `127.0.0.1` refers to the
> container itself, so a backend started with the main
> `docker-compose.yml` probably cannot reach the Collector.
> This has not been tested.

Expected cases do not need an incident record. Note them only
if they caused confusion.

## 7. Investigation Reference

### Prometheus and Grafana

| Tool | URL |
|---|---|
| Prometheus alerts | http://127.0.0.1:9090/alerts |
| Prometheus targets | http://127.0.0.1:9090/targets |
| Grafana | http://127.0.0.1:3000 |

Each query below can be pasted on its own into the Prometheus
query page or Grafana Explore (Prometheus data source).

All firing alerts:

```promql
ALERTS{alertstate="firing"}
```

Scrape target health:

```promql
up
```

Request rate by status code:

```promql
sum by (status_code) (rate(careerpilot_http_requests_total{exported_job="careerpilot-backend"}[5m]))
```

### Loki (logs)

```logql
{service_name="careerpilot-backend"}
{service_name="careerpilot-backend"} |= "REQUEST_ID"
```

Replace `REQUEST_ID` with the value of the `x-request-id`
response header.

Request log fields: `event`, `request_id`, `trace_id`,
`method`, `status_code`, `duration_ms`.

### Tempo (traces)

- Search for service `careerpilot-backend`, or paste a
  `trace_id` from a log line.
- Spans: `http.request` for each request, and `resume.match`
  for resume matching.
- The `http.request` span does not record HTTP status or
  route, so Tempo cannot be searched directly for failing
  requests. Start from Loki, then follow the `trace_id`.

### What telemetry does not contain

- Request bodies, resume text, or job descriptions.
- Routes or URL paths.
- User identity.

## 8. Recovery Verification

Verification has two kinds of step:

- **Read-only checks** look at existing state: the alerts
  page, PromQL queries, and existing Loki logs and Tempo
  traces. They need no approval.
- **Generating a synthetic request** (for example
  `GET /health`) creates new traffic and telemetry. It
  **requires developer approval** first.

### 8.1 Always (read-only)

1. The alert that triggered the incident shows **inactive**
   at http://127.0.0.1:9090/alerts, not just `pending`.
2. No database, volume, or Render setting was changed without
   recorded developer approval.

### 8.2 By incident type (read-only)

| Incident | Check |
|---|---|
| `CareerPilotHigh5xxRate` | The 5xx ratio query in [5.1](#51-careerpilothigh5xxrate-warning) stays below `0.05` over a full 5-minute window, or the backend has had too little traffic to evaluate it. |
| `CareerPilotHighAverageLatency` | The average latency query in [5.2](#52-careerpilothighaveragelatency-warning) stays below `0.5` over a full 5-minute window. |
| `CareerPilotOtelCollectorDown` | `up{job="careerpilot-otel-collector"}` is `1`. |
| `CareerPilotBackendTelemetryMissing` (real incident) | `careerpilot_http_requests_total{exported_job="careerpilot-backend"}` returns series again. |

The 5xx and latency checks rely on backend metrics, so they
apply only when OTLP export is enabled.

### 8.3 By telemetry state

**OTLP export enabled** (`CAREERPILOT_OTLP_ENABLED=true`):

- Read-only: recent requests appear in Prometheus metrics,
  and existing Loki logs link by `trace_id` to Tempo traces.
- If there is no recent traffic, a synthetic request may be
  used to confirm the full path, **with developer approval
  only**. It should then appear in metrics, logs, and traces.

**OTLP export intentionally disabled:**

- Do not expect backend metrics, logs, or traces. Their
  absence is not a failure.
- `CareerPilotBackendTelemetryMissing` is expected to stay
  active. It is not evidence of an unresolved incident.
- Verify only the read-only checks that do not need backend
  telemetry, such as `up{job="careerpilot-otel-collector"}`.
  Any backend health check by request requires approval.

Clear-down timing is inferred from the 5-minute rate windows
and the absence of `keep_firing_for`. It has not been measured.

## 9. Escalation

| Level | Who | May do |
|---|---|---|
| 1 | Developer or AI agent | Read-only triage using this runbook. |
| 2 | Developer (maintainer) | Approve restarts, configuration changes, code fixes, and any database action. |

There is no pager or on-call rotation. Escalating means
stopping work and reporting findings to the developer.

**Stop and escalate immediately if:**

- The database might be damaged or data might be lost.
- Secrets might have been exposed.
- Resume content appears in logs or telemetry.
- The problem might also affect the Render demo.
- The next step would be destructive or irreversible.

## 10. Incident Records

Create a record for every real incident. Expected
telemetry-missing cases do not need one.

Records must not contain secrets, `.env` values, request
bodies, or resume content. Request IDs, trace IDs, and PromQL
results are safe to include.

AI-assisted incident response must also be logged in
`docs/ai-development-log.md`, as required by `AGENTS.md`.

### Incident Report Template

```markdown
## Incident <YYYY-MM-DD>-<n>

- **Alert:** <alert name>
- **Severity:** <warning | info>
- **Classification:** <incident | expected behavior>
- **Active (UTC):** <timestamp>
- **Resolved (UTC):** <timestamp>
- **Responder:** <developer | AI agent, with reviewer>

### Impact

<What was affected, and for how long.>

### Timeline (UTC)

- <time> - <event>

### Evidence

- PromQL: <query> = <value at time>
- Request IDs: <ids>
- Trace IDs: <ids>

### Root Cause

<Confirmed cause, or "unknown" with what was ruled out.>

### Actions Taken

- <action> - <read-only | approved by developer>

### Verification

- [ ] Alert inactive at /alerts
- [ ] Incident-specific check from section 8.2 passed
- [ ] OTLP export state: <enabled | intentionally disabled>
- [ ] If enabled: recent requests visible in metrics, logs, and traces
- [ ] Synthetic request used: <no | yes, approved by developer>
- [ ] No unapproved database, volume, or Render changes

### Follow-ups

- <follow-up item>
```

## 11. Known Limitations

- Detection is manual. No Alertmanager or notifications are
  configured.
- Prometheus is not monitored. If it is down, no alerts fire.
- No per-route metrics, logs, or span attributes.
- No percentile latency. The OTLP histogram uses default
  SDK bucket boundaries.
- Thresholds are tuned for low-traffic local use.
- The Render deployment is not monitored by these alerts.
- The LogQL `| json` queries and the Docker networking
  behaviour described above have not been verified.
- Alert firing and clear-down timings are derived from rule
  configuration and synthetic `promtool` tests, not measured
  on the live stack.
