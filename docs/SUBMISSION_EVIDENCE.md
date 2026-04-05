# Submission Evidence Pack

Use this document to fill the submission form quickly.

## Repository URL

Replace with your public repo URL after push:
- https://github.com/<your-user-or-org>/OmniGuard

Required entry point:
- run.py

## Reliability

### Bronze

1. Working GET /health endpoint
- Evidence: app/main.py (health endpoint), README.md (health quick check), tests/test_main.py (health test).

2. Unit tests and pytest collection succeed
- Evidence: pytest.ini, tests/test_main.py, tests/test_integration.py.

3. CI workflow executes tests automatically
- Evidence: .github/workflows/ci.yml (test job).

### Silver

1. Automated test coverage >= 50%
- Evidence: .github/workflows/ci.yml (coverage gate is 70, which is above 50).

2. Integration/API tests exist and are detectable
- Evidence: tests/test_integration.py, .github/workflows/ci.yml (integration job).

3. Error handling for failures is documented
- Evidence: docs/FAILURE_MODES.md, docs/TROUBLESHOOTING.md, app/main.py (structured exception handlers).

### Gold

1. Automated test coverage >= 70%
- Evidence: .github/workflows/ci.yml (COVERAGE_THRESHOLD=70).

2. Invalid input paths return clean structured errors
- Evidence: app/main.py (ErrorResponse and exception handlers), tests/test_main.py (validation tests), tests/test_integration.py (malformed input test).

3. Evidence of service restart behavior after forced failure
- Evidence: docker-compose.yml (restart policies and health checks), docs/FAILURE_MODES.md (API crash, nginx down recovery workflows).

4. Failure modes and recovery expectations documented
- Evidence: docs/FAILURE_MODES.md.

## Documentation

### Bronze

1. README has clear setup/run instructions
- Evidence: README.md.

2. Architecture diagram evidence provided
- Evidence: docs/ARCHITECTURE.md and README.md architecture section.

3. API endpoints and usage documented
- Evidence: README.md API reference and app/main.py OpenAPI routes.

### Silver

1. Deployment and rollback steps documented
- Evidence: docs/DEPLOYMENT.md.

2. Troubleshooting steps documented
- Evidence: docs/TROUBLESHOOTING.md.

3. Required environment variables listed and explained
- Evidence: README.md configuration section and .env.example.

### Gold

1. Operational runbook exists and is actionable
- Evidence: docs/runbooks/ directory, docs/runbooks/alert-routing-validation.md.

2. Major technical decisions and rationale documented
- Evidence: docs/DECISIONS.md.

3. Capacity assumptions and known limits documented
- Evidence: docs/CAPACITY.md.

## Scalability

### Bronze

1. k6 or Locust is configured
- Evidence: loadtest/k6-api-load.js.

2. Evidence of load test at 50 concurrent users
- Evidence: docs/benchmarks/k6-results.md and docs/benchmarks/k6-50.json.

3. Baseline p95 latency and error rate documented
- Evidence: docs/benchmarks/k6-results.md.

### Silver

1. Evidence of successful load at 200 concurrent users
- Evidence: docs/benchmarks/k6-results.md and docs/benchmarks/k6-200.json.

2. Docker Compose includes multiple app instances
- Evidence: docker-compose.yml (replicas: 3).

3. Load balancer config present
- Evidence: nginx/nginx.conf.

4. Response time remains under 3s at scale-out load
- Evidence: docs/benchmarks/k6-results.md (500 VUs p95 < 3s).

### Gold

1. Evidence demonstrates tsunami-level throughput
- Evidence: docs/benchmarks/k6-results.md (high-concurrency 500 VU run and throughput metrics).

2. Redis caching implementation shown in repository
- Evidence: app/cache.py, app/main.py (X-Cache behavior), docker-compose.yml (redis service).

3. Bottleneck analysis report documented
- Evidence: docs/benchmarks/BOTTLENECK_ANALYSIS.md.

4. Error rate below 5% during high load
- Evidence: docs/benchmarks/k6-results.md (0.00% at 50/200/500 VUs).

## Incident Response

### Bronze

1. Structured JSON logging includes timestamp and level
- Evidence: app/main.py (CustomJsonFormatter fields timestamp and level).

2. /metrics endpoint returns monitoring data
- Evidence: app/main.py (/metrics endpoint), tests/test_main.py (metrics test).

3. Logs inspectable without SSH
- Evidence: docs/TROUBLESHOOTING.md (docker compose logs commands).

### Silver

1. Alert rules for service down and high error rate
- Evidence: observability/prometheus/rules/alerts.yml (ServiceDown and High5xxErrorRate).

2. Alerts routed to operator channel
- Evidence: observability/alertmanager.yml (webhook/slack/email/pagerduty receivers), docs/runbooks/alert-routing-validation.md.

3. Alerting latency documented with <=5 minute objective
- Evidence: docs/runbooks/alert-routing-validation.md and docs/FAILURE_MODES.md (detection and response timing targets).

### Gold

1. Dashboard evidence covers latency, traffic, errors, saturation
- Evidence: observability/grafana/provisioning/dashboards/omniguard-dashboard.json and app/main.py saturation metrics.

2. Runbook includes actionable alert-response procedures
- Evidence: docs/runbooks/high-5xx-error-rate.md, docs/runbooks/high-latency.md, docs/runbooks/service-down.md.

3. Root-cause analysis of simulated incident documented
- Evidence: docs/runbooks/SIMULATED_INCIDENT_RCA.md.

## Optional Screenshot Targets

If judges ask for screenshots, capture these pages and attach images:

1. Health endpoint JSON from http://localhost/health.
2. Grafana dashboard from http://localhost:3000.
3. Prometheus alert rules page from http://localhost:9090/rules.
4. CI pipeline run summary page showing all jobs green.
