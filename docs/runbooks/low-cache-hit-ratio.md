# 🚨 Runbook: Low Cache Hit Ratio

> **Alert**: `LowCacheHitRatio`  
> **Severity**: Warning  
> **Trigger**: Cache hit ratio < 50% for 10 minutes

---

## 📋 Quick Reference

| Item | Value |
|------|-------|
| **Alert Name** | LowCacheHitRatio |
| **Threshold** | < 50% hit ratio |
| **Duration** | 10 minutes |
| **Severity** | Warning |
| **Impact** | Higher latency, increased upstream load |

---

## 🎯 Impact Assessment

When cache hit ratio is low:
- ⚠️ More requests hit upstream API
- ⚠️ Higher latency for users
- ⚠️ Upstream API may be overloaded
- ⚠️ Higher resource consumption

---

## 🔍 Step 1: Check Current Status

### Current Hit Ratio

```bash
curl -s http://localhost/api/stats | jq
```

**Output**:
```json
{
  "cache_hits": 1000,
  "cache_misses": 2000,
  "hit_ratio": 0.33,     // 33% - this is low!
  "total_requests": 3000
}
```

### Prometheus Query

```bash
curl -s 'http://localhost:9090/api/v1/query?query=sum(rate(omniguard_cache_hits_total[5m]))/(sum(rate(omniguard_cache_hits_total[5m]))+sum(rate(omniguard_cache_misses_total[5m])))' | jq '.data.result[0].value[1]'
```

---

## 🔍 Step 2: Identify Root Cause

### Possible Causes

| Cause | Diagnostic | Solution |
|-------|------------|----------|
| **Redis down** | `redis-cli ping` fails | [Runbook: Redis Down](./redis-down.md) |
| **TTL too short** | High traffic, low TTL | Increase TTL |
| **Cache just cleared** | Recent FLUSHDB | Wait for warm-up |
| **High cardinality** | Many unique endpoints | Review endpoint design |
| **Recent deployment** | Cold cache | Pre-warm cache |
| **Traffic spike** | New users/endpoints | Scale up |

### Check Redis Status

```bash
# Is Redis responding?
docker exec omniguard-redis redis-cli ping

# How many keys are cached?
docker exec omniguard-redis redis-cli DBSIZE

# Check memory usage
docker exec omniguard-redis redis-cli INFO memory | grep used_memory_human
```

### Check Request Patterns

```bash
# Are many different endpoints being requested?
docker compose logs omniguard-api --since=10m | grep -oP 'endpoint.*?[,}]' | sort | uniq -c | sort -rn | head -20
```

### Check Cache TTL

```bash
# Check TTL on existing keys
docker exec omniguard-redis redis-cli KEYS "omniguard:*" | head -5 | while read key; do
  echo "$key: $(docker exec omniguard-redis redis-cli TTL $key)s remaining"
done
```

---

## 🛠 Step 3: Apply Fix

### 3.1 Redis Is Down → [Go to Redis Runbook](./redis-down.md)

### 3.2 Increase Cache TTL

If current TTL is too short for your traffic pattern:

```bash
# Check current TTL setting
docker compose config | grep CACHE_TTL

# Update docker-compose.yml
# CACHE_TTL=300  # 5 minutes instead of 60s

# Apply change
docker compose up -d --no-deps omniguard-api

# Verify new TTL
curl -s http://localhost/api/data
docker exec omniguard-redis redis-cli TTL "omniguard:data:/posts"
```

**TTL Guidelines**:

| Data Type | Recommended TTL |
|-----------|-----------------|
| Frequently changing | 60s |
| Semi-static | 300s (5 min) |
| Rarely changing | 3600s (1 hour) |
| Static reference data | 86400s (1 day) |

### 3.3 Pre-Warm Cache After Deployment

```bash
#!/bin/bash
# cache-warm.sh - Run after deployment

echo "Warming cache..."

# Popular endpoints
ENDPOINTS=(
  "/posts"
  "/users"
  "/comments"
  "/posts/1"
  "/posts/2"
  "/posts/3"
)

for endpoint in "${ENDPOINTS[@]}"; do
  echo "Warming: $endpoint"
  curl -s "http://localhost/api/data?endpoint=$endpoint" > /dev/null
  sleep 0.5
done

echo "Cache warm-up complete!"
curl -s http://localhost/api/stats | jq
```

### 3.4 Increase Redis Memory (for high cardinality)

```bash
# Check current memory
docker exec omniguard-redis redis-cli INFO memory | grep maxmemory

# Increase maxmemory
docker exec omniguard-redis redis-cli CONFIG SET maxmemory 512mb

# Or update docker-compose.yml:
# command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
```

### 3.5 Review Endpoint Design

If you're seeing many unique endpoints:

```bash
# Check endpoint distribution
docker compose logs omniguard-api --since=1h | grep -oP 'endpoint.*?[,}]' | sort | uniq -c | sort -rn | head -30
```

**If too many unique endpoints**:
- Consider grouping endpoints
- Use query parameters instead of path parameters
- Implement bulk endpoints

---

## ✅ Step 4: Verify Improvement

### Monitor Hit Ratio

```bash
# Watch hit ratio improve
watch -n 30 'curl -s http://localhost/api/stats | jq ".hit_ratio"'
```

**Expected**: Hit ratio should climb above 50% within 10-15 minutes

### Check Grafana

Open http://localhost:3000/d/omniguard

Look at the "Cache Hit Ratio" gauge - should be turning green

---

## 📊 Hit Ratio Targets

| Hit Ratio | Status | Action |
|-----------|--------|--------|
| > 80% | 🟢 Excellent | Maintain |
| 60-80% | 🟡 Good | Monitor |
| 50-60% | 🟠 Warning | Investigate |
| < 50% | 🔴 Poor | Immediate action |

---

## 📝 Post-Incident

### Document Findings

```markdown
## Cache Hit Ratio Incident - [DATE]

### Timeline
- [HH:MM] Alert: LowCacheHitRatio fired (ratio: X%)
- [HH:MM] Investigation: Found [cause]
- [HH:MM] Fix applied: [TTL increase / cache warm / etc]
- [HH:MM] Hit ratio recovered to Y%

### Root Cause
[Why was hit ratio low?]

### Prevention
- [ ] Adjust TTL for data patterns
- [ ] Add cache warming to deployment
- [ ] Monitor endpoint cardinality
```

---

## 📞 Escalation

| Hit Ratio | Response |
|-----------|----------|
| 40-50% | Warning - investigate |
| 25-40% | High priority - fix ASAP |
| < 25% | Critical - immediate action |
| 0% | Redis likely down |

---

## 📚 Related Runbooks

- [Runbook: Redis Down](./redis-down.md)
- [Runbook: High Latency](./high-latency.md)
- [Runbook: High 5xx Error Rate](./high-5xx-error-rate.md)
