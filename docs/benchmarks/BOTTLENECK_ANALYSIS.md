# OmniGuard Bottleneck Analysis Report

## Scope

This report analyzes bottlenecks using load-test artifacts in docs/benchmarks/k6-50.json, docs/benchmarks/k6-200.json, and docs/benchmarks/k6-500.json.

## Load Test Summary

| Concurrency | Requests/s | Avg Latency | p95 Latency | Error Rate |
|---|---:|---:|---:|---:|
| 50 VUs | 345.75 | 92.84 ms | 164.65 ms | 0.00% |
| 200 VUs | 338.61 | 535.47 ms | 739.46 ms | 0.00% |
| 500 VUs | 280.94 | 1706.50 ms | 2043.91 ms | 0.00% |

## Bottleneck Signals

1. Throughput plateaus from 50 to 200 VUs and drops at 500 VUs.
2. Latency grows significantly at 500 VUs while errors remain 0%.
3. This pattern indicates queueing and saturation before hard failure.

## Most Likely Constraints

1. FastAPI worker and Python runtime concurrency limits under high parallel requests.
2. Upstream fetch path and response serialization cost on cache-miss traffic.
3. Nginx rate limiting and connection management can dominate when testing through ingress.
4. Redis and app container resource limits (CPU/memory) can increase tail latency at peak.

## Why Error Rate Stayed Low

- Retries and graceful error handling protect against immediate failures.
- Cache and gateway behavior preserve correctness under stress.
- System degrades primarily in latency before failing requests.

## Recommended Optimizations

1. Increase API replicas and tune runtime worker settings.
2. Raise cache hit ratio by tuning TTL for read-heavy endpoints.
3. Tune Nginx limit and connection settings for target traffic profile.
4. Add container CPU/memory and connection pool profiling during high-load runs.
5. Add a 1000 VU scenario to measure next saturation threshold.

## Reproduction Commands

Use the commands in docs/benchmarks/k6-results.md to regenerate all benchmark artifacts.
