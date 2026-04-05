# 🚨 Runbook: High Latency

> **Alert**: `HighLatencyP95`  
> **Severity**: Warning / Critical  
> **Trigger**: P95 latency > 2s for 5 minutes (warning) or > 5s (critical)

---

## 📋 Quick Reference

| Item | Value |
|------|-------|
| **Alert Name** | HighLatencyP95 / HighLatencyP99 |
| **Warning Threshold** | P95 > 2 seconds |
| **Critical Threshold** | P99 > 5 seconds |
| **Duration** | 5 minutes |
| **Impact** | Poor user experience, timeouts |

---

## 🔍 Step 1: Assess Current Latency (1 minute)

### Check Current Percentiles

```bash
# P50 (median)
curl -s 'http://localhost:9090/api/v1/query?query=histogram_quantile(0.50,sum(rate(omniguard_request_latency_seconds_bucket[5m]))by(le))' | jq '.data.result[0].value[1]'

# P95
curl -s 'http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,sum(rate(omniguard_request_latency_seconds_bucket[5m]))by(le))' | jq '.data.result[0].value[1]'

# P99
curl -s 'http://localhost:9090/api/v1/query?query=histogram_quantile(0.99,sum(rate(omniguard_request_latency_seconds_bucket[5m]))by(le))' | jq '.data.result[0].value[1]'
```

### Check Latency by Endpoint

```bash
curl -s 'http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,sum(rate(omniguard_request_latency_seconds_bucket[5m]))by(le,endpoint))' | jq '.data.result[] | {endpoint: .metric.endpoint, p95: .value[1]}'
```

### Quick Latency Test

```bash
# Test actual latency
curl -w "Total: %{time_total}s, Connect: %{time_connect}s\n" -o /dev/null -s http://localhost/api/data
```

---

## 🔍 Step 2: Identify Root Cause

### Check Cache Hit Ratio

```bash
curl -s http://localhost/api/stats | jq '.hit_ratio'
# If < 0.5, low cache hits are causing latency
```

### Check Resource Usage

```bash
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemPerc}}"
```

**Interpret Results**:

| CPU | Memory | Likely Cause |
|-----|--------|--------------|
| >80% | Normal | CPU bottleneck |
| Normal | >80% | Memory pressure |
| Normal | Normal | External dependency |

### Check Redis Latency

```bash
docker exec omniguard-redis redis-cli --latency -c 100
# Expected: avg < 1ms
# If > 10ms: Redis is slow
```

### Check Upstream Latency

```bash
# Direct upstream test
curl -w "Time: %{time_total}s\n" -o /dev/null -s https://jsonplaceholder.typicode.com/posts/1
# Expected: < 500ms
```

---

## 🛠 Step 3: Apply Fix

### 3.1 Low Cache Hit Ratio

**Symptoms**: hit_ratio < 50%, many cache misses

```bash
# Increase cache TTL
# Edit docker-compose.yml or .env:
# CACHE_TTL=300  (from 60)

# Restart API to apply
docker compose up -d --no-deps omniguard-api
```

### 3.2 CPU Bottleneck

**Symptoms**: CPU > 80% on API containers

```bash
# Scale horizontally
docker compose up -d --scale omniguard-api=5

# Verify scaling
docker compose ps | grep omniguard-api
```

### 3.3 Redis Slow

**Symptoms**: Redis latency > 10ms

```bash
# Check for slow commands
docker exec omniguard-redis redis-cli SLOWLOG GET 10

# Check memory
docker exec omniguard-redis redis-cli INFO memory

# If memory high, increase maxmemory
docker exec omniguard-redis redis-cli CONFIG SET maxmemory 256mb

# Or flush stale data
docker exec omniguard-redis redis-cli FLUSHDB
```

### 3.4 Upstream Slow

**Symptoms**: Upstream response time > 500ms

```bash
# Increase timeout to prevent errors
# UPSTREAM_TIMEOUT=30 (from 10)

# Increase retries
# (modify upstream.py retry_with_backoff)

# Or increase cache TTL aggressively
# CACHE_TTL=600
```

### 3.5 Memory Pressure

**Symptoms**: Memory > 80%, possible swapping

```bash
# Increase memory limits
# Edit docker-compose.yml:
# memory: 512M (from 256M)

docker compose up -d --no-deps omniguard-api
```

### 3.6 Connection Pool Exhaustion

**Symptoms**: Latency spikes with bursts of traffic

```bash
# Check active connections
docker exec omniguard-redis redis-cli INFO clients

# Increase connection pool in code
# keepalive 64 (nginx)
# max_connections 50 (redis pool)
```

---

## ✅ Step 4: Verify Improvement

### Monitor Latency

```bash
# Watch latency for 5 minutes
watch -n 30 'curl -s "http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,sum(rate(omniguard_request_latency_seconds_bucket[5m]))by(le))" | jq ".data.result[0].value[1]"'
```

**Expected**: P95 should drop below 2s within 5-10 minutes

### Test Endpoints

```bash
# Run 10 requests, measure latency
for i in {1..10}; do
  curl -w "%{time_total}\n" -o /dev/null -s http://localhost/api/data
done | awk '{sum+=$1} END {print "Avg: " sum/NR "s"}'
```

### Check Grafana

Open http://localhost:3000/d/omniguard

Verify:
- Latency graph trending down
- Cache hit ratio improving
- No error spikes

---

## 📊 Latency Targets

| Percentile | Good | Warning | Critical |
|------------|------|---------|----------|
| P50 | < 50ms | < 200ms | > 500ms |
| P95 | < 200ms | < 2s | > 5s |
| P99 | < 500ms | < 5s | > 10s |

---

## 🔄 Long-term Fixes

### If latency is consistently high:

1. **Add more replicas**
   ```bash
   docker compose up -d --scale omniguard-api=10
   ```

2. **Increase cache TTL**
   ```yaml
   environment:
     - CACHE_TTL=300
   ```

3. **Optimize Redis**
   ```yaml
   redis:
     command: redis-server --maxmemory 512mb
   ```

4. **Add edge caching (CDN)**
   - CloudFlare, Fastly, AWS CloudFront

5. **Optimize upstream**
   - Connection pooling
   - Response compression
   - Batch requests

---

## 📝 Post-Incident

### Document Findings

```markdown
## Latency Incident - [DATE]

### Timeline
- [HH:MM] Alert fired (P95 > 2s)
- [HH:MM] Investigation: Found [root cause]
- [HH:MM] Fix applied: [what was done]
- [HH:MM] Latency normalized

### Root Cause
[Detailed explanation]

### Metrics During Incident
- Peak P95: [X]s
- Cache hit ratio: [Y]%
- CPU utilization: [Z]%

### Prevention
[Long-term fixes planned]
```

---

## 📞 Escalation

| Latency | Response |
|---------|----------|
| P95 > 2s | Warning - investigate |
| P95 > 5s | Critical - immediate action |
| P95 > 10s | Page entire team |
| Timeout errors | Emergency response |

---

## 📚 Related Runbooks

- [Runbook: High 5xx Error Rate](./high-5xx-error-rate.md)
- [Runbook: Redis Down](./redis-down.md)
- [Runbook: Low Cache Hit Ratio](./low-cache-hit-ratio.md)
