# OmniGuard Architecture

## System Overview

OmniGuard is a caching API gateway with horizontal app replicas, Redis caching, and a full observability stack.

```text
Client -> Nginx -> FastAPI replicas -> Redis cache -> Upstream API
                     |
                     -> /metrics -> Prometheus -> Grafana + Alertmanager
```

## Components

| Component | Purpose | Main Config |
|---|---|---|
| Nginx | Ingress, rate limiting, load balancing | nginx/nginx.conf |
| FastAPI | API logic, validation, metrics, health checks | app/main.py |
| Redis | Cache storage for upstream responses | app/cache.py |
| Prometheus | Metrics collection and rule evaluation | observability/prometheus.yml |
| Alertmanager | Alert routing to webhook/email/slack channels | observability/alertmanager.yml |
| Grafana | Dashboards for latency, errors, traffic, cache | observability/grafana/provisioning/dashboards/omniguard-dashboard.json |

## Request Flow

1. Client request reaches Nginx.
2. Nginx forwards to FastAPI service and applies rate limits for API paths.
3. FastAPI checks Redis for cached response.
4. On cache hit, FastAPI returns cached data.
5. On cache miss, FastAPI calls upstream API, stores response in Redis, then returns data.
6. FastAPI exports request, latency, error, cache, and saturation metrics at /metrics.

## Reliability and Recovery Design

- Health endpoints are exposed for app and nginx.
- Docker restart policies and health checks support automatic recovery.
- Prometheus alert rules detect service down, high error rates, and high latency.
- Runbooks document mitigation and recovery actions for common incidents.

## Scalability Design

- App service runs with multiple replicas in compose configuration.
- Nginx load-balances traffic across app replicas.
- Redis reduces upstream dependency load by serving repeated reads from cache.

## Observability Design

- Structured JSON logging in app layer.
- Prometheus metrics at /metrics.
- Grafana dashboard tracks latency, traffic, error, and cache health.
- Alertmanager routes alerts to configured channels.
