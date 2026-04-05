# 🚨 Runbook: Redis Down

> **Alert**: `RedisDown`  
> **Severity**: Critical  
> **Trigger**: Redis connection fails for 1 minute

---

## 📋 Quick Reference

| Item | Value |
|------|-------|
| **Alert Name** | RedisDown |
| **Threshold** | redis_up == 0 |
| **Duration** | 1 minute |
| **Severity** | Critical |
| **Impact** | All cache misses, high upstream load |
| **On-Call Response** | Immediate |

---

## 🎯 Impact Assessment

When Redis is down:
- ❌ All requests result in cache MISS
- ❌ Upstream API receives all traffic
- ❌ Response latency increases significantly
- ❌ Upstream may be overwhelmed
- ⚠️ Health check shows Redis unhealthy

---

## 🔍 Step 1: Confirm Redis Is Down (30 seconds)

### Check Redis Container

```bash
# Container status
docker compose ps redis

# Try to ping Redis
docker exec omniguard-redis redis-cli ping
# Expected: PONG
# If error: Redis is down
```

### Check Health Endpoint

```bash
curl -s http://localhost/health | jq '.redis'
# Expected: {"status": "healthy", "connected": true}
```

### Check Prometheus

```bash
curl -s 'http://localhost:9090/api/v1/query?query=redis_up' | jq '.data.result[0].value[1]'
# 0 = Down, 1 = Up
```

---

## 🔥 Step 2: Attempt Quick Recovery (2 minutes)

### 2.1 Restart Redis Container

```bash
docker compose restart redis

# Wait for startup
sleep 10

# Verify recovery
docker exec omniguard-redis redis-cli ping
```

### 2.2 If Restart Fails, Check Logs

```bash
docker compose logs redis --tail=100
```

**Common Error Messages**:

| Error | Cause | Solution |
|-------|-------|----------|
| `Can't open/create append-only file` | Disk full or permissions | Clear disk, fix permissions |
| `maxmemory reached` | Memory exhausted | Increase maxmemory |
| `MISCONF Redis is configured to save RDB` | Disk write failed | Fix disk issues |
| `Connection refused` | Redis not starting | Check port conflicts |

---

## 🛠 Step 3: Fix Specific Issues

### 3.1 Disk Full

```bash
# Check disk space
df -h

# Clean Docker artifacts
docker system prune -f

# Clean old Redis data if needed
docker exec omniguard-redis rm -f /data/dump.rdb

# Restart Redis
docker compose restart redis
```

### 3.2 Memory Exhaustion

```bash
# Check Redis memory
docker exec omniguard-redis redis-cli INFO memory | grep used_memory_human

# Increase maxmemory in docker-compose.yml
# maxmemory 256mb (from 128mb)

# Or flush all data (last resort - clears cache)
docker exec omniguard-redis redis-cli FLUSHALL

# Restart with new config
docker compose up -d --no-deps redis
```

### 3.3 Port Conflict

```bash
# Check what's using port 6379
netstat -tlnp | grep 6379

# If another process, kill it or change Redis port
# Or stop the conflicting service
```

### 3.4 Corrupt Data

```bash
# Remove corrupt data files
docker compose down redis
docker volume rm omniguard_redis_data

# Restart fresh (cache will be cold)
docker compose up -d redis
```

---

## 🔄 Step 4: Verify Recovery

### 4.1 Redis Is Responding

```bash
# Ping test
docker exec omniguard-redis redis-cli ping
# Expected: PONG

# Check INFO
docker exec omniguard-redis redis-cli INFO server | head -10
```

### 4.2 API Can Connect

```bash
# Health check shows Redis healthy
curl -s http://localhost/health | jq '.redis.status'
# Expected: "healthy"
```

### 4.3 Cache Is Working

```bash
# First request (should be MISS)
curl -s -I http://localhost/api/data | grep X-Cache

# Second request (should be HIT)
curl -s -I http://localhost/api/data | grep X-Cache
# Expected: X-Cache: HIT
```

### 4.4 Monitor for 10 Minutes

```bash
# Watch cache stats
watch -n 10 'curl -s http://localhost/api/stats | jq ".hit_ratio"'
```

---

## 🔥 Step 5: Emergency: Redis Won't Recover

If Redis cannot be recovered quickly:

### Option A: Run Without Redis (Degraded Mode)

The application will continue to work but all requests will be cache misses.

```bash
# Monitor upstream load
# May need to throttle traffic or add more API replicas
docker compose up -d --scale omniguard-api=5
```

### Option B: Launch New Redis Instance

```bash
# Stop broken Redis
docker compose stop redis

# Start fresh Redis (loses all cache)
docker compose up -d redis

# Cache will warm up naturally
```

### Option C: Use Alternate Redis (if available)

```bash
# Point to backup Redis
export REDIS_HOST=redis-backup.internal
docker compose up -d --no-deps omniguard-api
```

---

## 📝 Step 6: Post-Incident

### Cache Warming

After Redis recovery, cache will be cold. Consider:

```bash
# Pre-warm popular endpoints
curl http://localhost/api/data?endpoint=/posts
curl http://localhost/api/data?endpoint=/users
curl http://localhost/api/data?endpoint=/comments
```

### Document Incident

```markdown
## Incident: Redis Down - [DATE]

### Timeline
- [HH:MM] Alert: RedisDown fired
- [HH:MM] Investigation started
- [HH:MM] Root cause: [X]
- [HH:MM] Fix applied
- [HH:MM] Redis restored
- [HH:MM] Cache warm-up complete

### Root Cause
[What caused Redis to go down]

### Impact
- Duration: [X minutes]
- Cache hit ratio during incident: 0%
- Latency increase: [X]ms

### Prevention
[What changes will prevent recurrence]
```

---

## 🛡 Prevention Measures

### Monitoring
- [ ] Alert on Redis memory > 70%
- [ ] Alert on Redis connection errors
- [ ] Monitor disk space on Redis host

### Configuration
- [ ] Set appropriate maxmemory
- [ ] Configure maxmemory-policy (allkeys-lru)
- [ ] Enable Redis persistence (AOF)

### Backup
- [ ] Regular RDB snapshots
- [ ] Test restore procedure
- [ ] Consider Redis Sentinel for HA

---

## 📞 Escalation

| Time | Action |
|------|--------|
| 0-2 min | Attempt restart |
| 2-5 min | Investigate root cause |
| 5-10 min | Page secondary if unresolved |
| 10+ min | Consider degraded mode |

---

## 📚 Related Runbooks

- [Runbook: High 5xx Error Rate](./high-5xx-error-rate.md)
- [Runbook: High Latency](./high-latency.md)
- [Runbook: Low Cache Hit Ratio](./low-cache-hit-ratio.md)
