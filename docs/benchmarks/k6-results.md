# OmniGuard k6 Benchmark Results

## Test Scope

- Date: 2026-04-04
- Tool: `grafana/k6`
- Script: `loadtest/k6-api-load.js`
- Duration per scenario: 30s
- Target endpoint: `http://omniguard-omniguard-api-1:8000/api/csv/users`
- Network: `omniguard_omniguard-network`

## Commands Used

```powershell
docker run --rm -i --network omniguard_omniguard-network `
  --env TARGET_URL=http://omniguard-omniguard-api-1:8000/api/csv/users `
  -v "${PWD}/loadtest:/scripts" -v "${PWD}/docs/benchmarks:/results" `
  grafana/k6 run --vus 50 --duration 30s --summary-export /results/k6-50.json /scripts/k6-api-load.js

docker run --rm -i --network omniguard_omniguard-network `
  --env TARGET_URL=http://omniguard-omniguard-api-1:8000/api/csv/users `
  -v "${PWD}/loadtest:/scripts" -v "${PWD}/docs/benchmarks:/results" `
  grafana/k6 run --vus 200 --duration 30s --summary-export /results/k6-200.json /scripts/k6-api-load.js

docker run --rm -i --network omniguard_omniguard-network `
  --env TARGET_URL=http://omniguard-omniguard-api-1:8000/api/csv/users `
  -v "${PWD}/loadtest:/scripts" -v "${PWD}/docs/benchmarks:/results" `
  grafana/k6 run --vus 500 --duration 30s --summary-export /results/k6-500.json /scripts/k6-api-load.js
```

## Results Summary

| VUs | Requests/s | Avg Latency | p95 Latency | HTTP Error Rate |
|---|---:|---:|---:|---:|
| 50  | 345.75 | 92.84 ms | 164.65 ms | 0.00% |
| 200 | 338.61 | 535.47 ms | 739.46 ms | 0.00% |
| 500 | 280.94 | 1706.50 ms | 2043.91 ms | 0.00% |

## Artifacts

- `docs/benchmarks/k6-50.json`
- `docs/benchmarks/k6-200.json`
- `docs/benchmarks/k6-500.json`

## Notes

- Throughput remains stable from 50 to 200 VUs, then decreases at 500 VUs as latency rises.
- All runs remained below the 3s p95 threshold in `loadtest/k6-api-load.js`.
- These tests target the API service directly. If benchmarking through Nginx, account for Nginx rate-limiting configuration (`limit_req`) which intentionally sheds excess traffic.
