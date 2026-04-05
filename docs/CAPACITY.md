# 📊 OmniGuard Capacity Planning Guide

> Understanding system limits, scaling strategies, and capacity calculations.

---

## 📋 Table of Contents

1. [System Specifications](#-system-specifications)
2. [Capacity Limits](#-capacity-limits)
3. [Performance Benchmarks](#-performance-benchmarks)
4. [Scaling Calculator](#-scaling-calculator)
5. [Bottleneck Analysis](#-bottleneck-analysis)
6. [Scaling Strategies](#-scaling-strategies)
7. [Cost Estimation](#-cost-estimation)
8. [Monitoring for Scale](#-monitoring-for-scale)

---

## 🖥 System Specifications

### Default Configuration

| Component | Replicas | CPU | Memory | Storage |
|-----------|----------|-----|--------|---------|
| Nginx | 1 | 0.25 | 64MB | - |
| FastAPI | 3 | 0.5 | 256MB | - |
| Redis | 1 | 0.25 | 128MB | 1GB |
| Prometheus | 1 | 0.5 | 256MB | 10GB |
| Grafana | 1 | 0.25 | 128MB | 1GB |
| **Total** | **7** | **2.75** | **1.25GB** | **12GB** |

### Minimum Requirements

For **development/testing**:
- **CPU**: 2 cores
- **Memory**: 4GB RAM
- **Storage**: 20GB SSD

For **production**:
- **CPU**: 4+ cores
- **Memory**: 8GB+ RAM
- **Storage**: 50GB+ SSD (for metrics retention)

---

## 📈 Capacity Limits

### Per-Component Limits

#### FastAPI (per replica)
| Metric | Limit | Notes |
|--------|-------|-------|
| Concurrent connections | 1,000 | uvicorn worker limit |
| Requests per second | 2,000-5,000 | Depends on payload size |
| Memory per request | ~1MB | For JSON processing |
| Max request body | 10MB | Nginx limit |

#### Redis
| Metric | Limit | Notes |
|--------|-------|-------|
| Max keys | ~1M | With 128MB memory |
| Connections | 10,000 | Default max clients |
| Commands/sec | 100,000+ | Single-threaded |
| Max value size | 512MB | Per key |

#### Nginx
| Metric | Limit | Notes |
|--------|-------|-------|
| Concurrent connections | 10,000+ | Per worker |
| Requests per second | 50,000+ | Static content |
| Rate limit | 100/s/IP | Configured |

### System-Wide Limits

| Configuration | Max RPS | Latency P95 | Notes |
|--------------|---------|-------------|-------|
| Default (3 replicas) | 3,000-5,000 | <100ms | Cache hit scenario |
| Scaled (10 replicas) | 10,000-20,000 | <100ms | Horizontal scaling |
| Max theoretical | 50,000+ | <50ms | Redis/Nginx limits |

---

## ⚡ Performance Benchmarks

### Test Environment
```
Hardware: AWS c5.xlarge (4 vCPU, 8GB RAM)
Load Tool: k6
Test Duration: 60 seconds
Payload: ~1KB JSON response
```

### Benchmark Results

#### Scenario 1: Cache Hits (95% hit rate)
```
RPS: 5,000
Concurrent Users: 100
Results:
  - P50 Latency: 5ms
  - P95 Latency: 15ms
  - P99 Latency: 35ms
  - Error Rate: 0%
  - Cache Hit Ratio: 95%
```

#### Scenario 2: Cache Misses (cold cache)
```
RPS: 1,000
Concurrent Users: 50
Results:
  - P50 Latency: 150ms
  - P95 Latency: 350ms
  - P99 Latency: 500ms
  - Error Rate: 0.1%
  - Cache Hit Ratio: 0%
```

#### Scenario 3: Mixed Traffic (realistic)
```
RPS: 3,000
Concurrent Users: 100
Cache Hit Ratio: 75%
Results:
  - P50 Latency: 25ms
  - P95 Latency: 120ms
  - P99 Latency: 250ms
  - Error Rate: 0.01%
```

### Benchmark Commands

```bash
# Install k6
brew install k6  # or download from k6.io

# Run load test
k6 run --vus 100 --duration 60s - <<EOF
import http from 'k6/http';
import { check, sleep } from 'k6';

export default function () {
  const res = http.get('http://localhost/api/data');
  check(res, {
    'status is 200': (r) => r.status === 200,
    'latency < 500ms': (r) => r.timings.duration < 500,
  });
  sleep(0.1);
}
EOF
```

---

## 🧮 Scaling Calculator

### Formula

```
Required Replicas = (Target RPS × Safety Factor) / (RPS per Replica × Cache Hit Ratio)

Where:
- Safety Factor = 1.5 (50% headroom for spikes)
- RPS per Replica = 2,000 (cache hit) or 500 (cache miss)
- Cache Hit Ratio = Expected hit rate (0.0 - 1.0)
```

### Quick Reference Table

| Target RPS | Cache Hit Rate | Recommended Replicas | Redis Memory |
|------------|----------------|---------------------|--------------|
| 100 | 80% | 2 | 128MB |
| 500 | 75% | 3 | 128MB |
| 1,000 | 80% | 3-4 | 256MB |
| 2,500 | 80% | 5-6 | 256MB |
| 5,000 | 85% | 8-10 | 512MB |
| 10,000 | 90% | 15-20 | 1GB |
| 25,000 | 90% | 35-40 | 2GB |
| 50,000 | 95% | 60+ | 4GB |

### Memory Calculator

```
Redis Memory = (Unique Endpoints × Average Response Size × 1.5)

Example:
- 100 unique endpoints
- 5KB average response
- Memory = 100 × 5KB × 1.5 = 750KB (+ overhead = ~10MB)
```

### Example Calculation

**Scenario**: E-commerce product API
- **Target**: 5,000 RPS peak
- **Cache hit rate**: 85% (product data changes rarely)
- **Safety factor**: 1.5

```
Required = (5000 × 1.5) / (2000 × 0.85)
         = 7500 / 1700
         = 4.4 → 5 replicas (round up)
```

**Recommendation**: 5-6 API replicas, 512MB Redis

---

## 🔍 Bottleneck Analysis

### Identifying Bottlenecks

```
Check in this order:
1. Nginx → High connection queue
2. FastAPI → High CPU, request backlog
3. Redis → High memory, slow commands
4. Upstream → Timeout errors, retries
5. Network → High latency between containers
```

### Diagnostic Commands

```bash
# 1. Nginx bottleneck check
docker exec omniguard-nginx cat /var/log/nginx/error.log | grep -i "worker_connections"

# 2. FastAPI bottleneck check
docker stats --format "{{.Name}}: CPU {{.CPUPerc}}, MEM {{.MemPerc}}"
# If CPU >80% → Scale horizontally

# 3. Redis bottleneck check
docker exec omniguard-redis redis-cli INFO stats | grep -E "total_connections|rejected|used_memory"

# 4. Upstream bottleneck check
curl -s http://localhost/api/stats | jq '.cache_hits, .cache_misses'
# If misses >> hits → Increase TTL or check upstream

# 5. Network latency check
docker exec omniguard-api-1 ping -c 5 redis
```

### Bottleneck Resolution Matrix

| Symptom | Bottleneck | Solution |
|---------|------------|----------|
| P95 >500ms, CPU <50% | Upstream | Increase TTL, add retries |
| P95 >500ms, CPU >80% | FastAPI | Add replicas |
| Connection refused | Nginx | Increase worker_connections |
| Redis timeout | Redis | Increase memory, check slowlog |
| Sporadic 502 errors | Health check | Tune health check intervals |

---

## 📈 Scaling Strategies

### Horizontal Scaling (Recommended)

Add more FastAPI replicas:

```bash
# Scale to 10 replicas
docker compose up -d --scale omniguard-api=10

# Verify scaling
docker compose ps | grep omniguard-api
```

**When to use**:
- CPU consistently >70%
- Request queue building up
- P95 latency increasing

### Vertical Scaling

Increase resources per container:

```yaml
# docker-compose.yml
omniguard-api:
  deploy:
    resources:
      limits:
        cpus: "1.0"      # Double from 0.5
        memory: 512M     # Double from 256M
```

**When to use**:
- Memory pressure (OOMKilled)
- Single request needs more CPU

### Redis Scaling

```yaml
# Increase memory
redis:
  command: >
    redis-server
    --maxmemory 512mb  # Increase from 128mb
```

**For extreme scale** (>50k RPS):
- Use Redis Cluster
- Multiple Redis instances with sharding

### Nginx Scaling

```nginx
# nginx.conf - Increase workers
worker_processes auto;
worker_connections 4096;  # Increase from 1024
```

---

## 💰 Cost Estimation

### Cloud Cost Calculator

#### AWS (ECS/Fargate)

| Component | Size | Monthly Cost |
|-----------|------|--------------|
| Nginx | 0.25 vCPU, 0.5GB | $15 |
| FastAPI x3 | 0.5 vCPU, 1GB each | $90 |
| Redis (ElastiCache t3.micro) | | $15 |
| ALB | | $20 |
| **Total (3 replicas)** | | **~$140/month** |

#### Scaling Costs

| RPS | Replicas | Estimated Monthly Cost |
|-----|----------|----------------------|
| 1,000 | 3 | $140 |
| 5,000 | 8 | $300 |
| 10,000 | 15 | $550 |
| 25,000 | 35 | $1,200 |
| 50,000 | 70 | $2,500 |

### Cost Optimization Tips

1. **Increase cache TTL** - Reduce upstream calls
2. **Right-size containers** - Don't over-provision
3. **Use spot instances** - For non-critical workloads
4. **Reserved capacity** - 30-50% discount
5. **Cache aggressively** - Higher hit rate = fewer replicas needed

---

## 📊 Monitoring for Scale

### Key Metrics to Watch

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| CPU % (per replica) | >70% | >85% | Scale up |
| Memory % | >75% | >90% | Increase limits |
| P95 Latency | >500ms | >2s | Investigate |
| Error Rate | >1% | >5% | Alert on-call |
| Cache Hit Ratio | <50% | <25% | Increase TTL |
| Redis Memory | >70% | >90% | Increase maxmemory |
| Request Queue | >100 | >500 | Scale Nginx |

### Prometheus Queries for Capacity

```promql
# Current RPS
sum(rate(omniguard_requests_total[5m]))

# Headroom (% of capacity used)
sum(rate(omniguard_requests_total[5m])) / (count(up{job="omniguard-api"}) * 2000) * 100

# Projected capacity needed (based on growth)
predict_linear(sum(rate(omniguard_requests_total[1h]))[24h:1h], 86400 * 30)

# Cost per request (efficiency metric)
sum(rate(omniguard_cache_misses_total[1h])) / sum(rate(omniguard_requests_total[1h]))
```

### Alerting Thresholds for Scale

```yaml
# Capacity warning - 70% of estimated max
- alert: CapacityWarning
  expr: |
    sum(rate(omniguard_requests_total[5m])) > 
    (count(up{job="omniguard-api"}) * 2000 * 0.7)
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Approaching capacity limits"
    description: "Current RPS is {{ $value | humanize }}. Consider scaling."

# Capacity critical - 90% of estimated max
- alert: CapacityCritical
  expr: |
    sum(rate(omniguard_requests_total[5m])) > 
    (count(up{job="omniguard-api"}) * 2000 * 0.9)
  for: 2m
  labels:
    severity: critical
```

---

## 📝 Capacity Planning Checklist

### Before Launch
- [ ] Baseline performance testing complete
- [ ] Scaling limits documented
- [ ] Auto-scaling configured (if available)
- [ ] Alerts for capacity metrics set
- [ ] Cost budget approved

### Monthly Review
- [ ] Review RPS trends
- [ ] Check cache hit ratio
- [ ] Review error rates
- [ ] Update capacity projections
- [ ] Optimize if needed

### Before Major Events (Sales, Launches)
- [ ] Pre-scale replicas
- [ ] Warm cache with expected queries
- [ ] Increase Redis memory
- [ ] Test at 2x expected load
- [ ] Have rollback plan ready

---

## 🔮 Scaling Roadmap

### Phase 1: Current (1-5K RPS)
- Docker Compose
- 3 API replicas
- Single Redis instance
- Prometheus/Grafana

### Phase 2: Growth (5-25K RPS)
- Docker Swarm or Kubernetes
- 10-30 API replicas
- Redis Sentinel (HA)
- Managed monitoring (Datadog/Grafana Cloud)

### Phase 3: Scale (25K+ RPS)
- Kubernetes with HPA
- 50+ API replicas
- Redis Cluster
- CDN for static responses
- Multi-region deployment

---

## 🧪 Load Testing Scripts

OmniGuard includes reproducible k6 load testing scripts in `tests/load/`.

### Available Scripts

| Script | Concurrency | Duration | Purpose |
|--------|-------------|----------|---------|
| `baseline.js` | 50 VUs | 60s | Baseline performance validation |
| `stress.js` | 100→500 VUs | ~4min | Stress test with ramping |
| `load-test.js` | 50/200/500 | ~4min | Full suite with all scenarios |

### Running Load Tests

```bash
# Install k6
# macOS: brew install k6
# Windows: choco install k6
# Linux: sudo gpg -k && sudo apt install k6

# Run baseline test (50 concurrent users)
k6 run tests/load/baseline.js

# Run stress test (500+ concurrent users)
k6 run tests/load/stress.js

# Run with custom base URL
k6 run -e BASE_URL=http://your-server tests/load/baseline.js

# Export results to JSON
k6 run --out json=results.json tests/load/baseline.js
```

### Performance Thresholds

| Scenario | P95 Latency | Error Rate | Pass Criteria |
|----------|-------------|------------|---------------|
| Baseline (50 VUs) | <500ms | <1% | Standard operation |
| Moderate (200 VUs) | <1000ms | <2% | Moderate load |
| Stress (500 VUs) | <2000ms | <5% | Peak load tolerance |

### Sample Results Template

```
╔═══════════════════════════════════════════════════════════════╗
║                    LOAD TEST RESULTS                          ║
╠═══════════════════════════════════════════════════════════════╣
║  Test Date:       YYYY-MM-DD HH:MM                            ║
║  Environment:     [production/staging/local]                  ║
║  Replicas:        [N] API instances                           ║
╠═══════════════════════════════════════════════════════════════╣
║  BASELINE (50 VUs)                                            ║
║    P95 Latency:   _____ ms                                    ║
║    Error Rate:    _____ %                                     ║
║    RPS:           _____ req/s                                 ║
╠═══════════════════════════════════════════════════════════════╣
║  STRESS (500 VUs)                                             ║
║    P95 Latency:   _____ ms                                    ║
║    Error Rate:    _____ %                                     ║
║    Peak RPS:      _____ req/s                                 ║
╠═══════════════════════════════════════════════════════════════╣
║  BOTTLENECK ANALYSIS                                          ║
║  [Describe the primary bottleneck observed and mitigation]    ║
╚═══════════════════════════════════════════════════════════════╝
```

---

## 📈 Bottleneck Report

> Document findings from actual load test runs here.

### Baseline Findings (Template)

**Test Configuration:**
- Date: [YYYY-MM-DD]
- Replicas: [N]
- Redis Memory: [128MB/256MB/...]

**Observations:**
1. **Primary Bottleneck:** [Describe - e.g., "Redis memory approaching limit at 500 VUs"]
2. **Secondary Bottleneck:** [Describe - e.g., "API CPU saturation at 85%"]

**Impact:**
- P95 increased from Xms to Yms when hitting bottleneck
- Error rate spiked to Z% at peak

**Mitigation Applied:**
- [What was changed - e.g., "Increased Redis memory to 256MB"]
- [Result - e.g., "P95 reduced to 150ms, error rate to 0.1%"]
