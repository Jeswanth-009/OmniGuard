# 🚨 OmniGuard Failure Modes Document

> Comprehensive documentation of failure scenarios, their detection, impact, and recovery procedures.

---

## 📋 Table of Contents

1. [Overview](#-overview)
2. [Failure Mode Matrix](#-failure-mode-matrix)
3. [Detailed Failure Modes](#-detailed-failure-modes)
4. [Detection & Alerting](#-detection--alerting)
5. [Recovery Verification](#-recovery-verification)

---

## 🎯 Overview

This document catalogs all known failure modes for the OmniGuard API Gateway, following the FMEA (Failure Mode and Effects Analysis) methodology. Each failure mode includes:

- **Trigger**: What causes the failure
- **Impact**: Effect on system and users
- **Detection**: How we know it's happening
- **Mitigation**: Immediate actions to reduce impact
- **Recovery Verification**: How we confirm the system is healthy

---

## 📊 Failure Mode Matrix

| ID | Failure Mode | Severity | Detection Time | MTTR Target |
|----|--------------|----------|----------------|-------------|
| FM-001 | Redis Connection Loss | Critical | <30s | 5 min |
| FM-002 | Upstream API Unavailable | High | <1 min | N/A (external) |
| FM-003 | API Instance Crash | High | <30s | 2 min |
| FM-004 | Nginx Load Balancer Down | Critical | <30s | 3 min |
| FM-005 | High Error Rate (>5%) | High | <1 min | 10 min |
| FM-006 | Cache Poisoning | Medium | Manual | 5 min |
| FM-007 | Memory Exhaustion (OOM) | High | <1 min | 5 min |
| FM-008 | Network Partition | Critical | <1 min | Variable |
| FM-009 | Certificate Expiry | Medium | 7 days | 30 min |
| FM-010 | Disk Space Exhaustion | Medium | <5 min | 15 min |

---

## 📝 Detailed Failure Modes

### FM-001: Redis Connection Loss

**Trigger:**
- Redis container crashes or restarts
- Network connectivity issues to Redis
- Redis memory exhaustion (maxmemory reached)
- Authentication failure

**Impact:**
- All cache operations fail
- Every request becomes a cache MISS
- Increased load on upstream API
- Potential upstream rate limiting
- Health check reports "unhealthy" for Redis

**Detection:**
```yaml
Alert: RedisDown
Metric: redis_up == 0
Threshold: 1 minute
```

**Mitigation:**
1. Traffic continues with degraded performance (all cache misses)
2. Circuit breaker prevents cascade failures
3. Automatic retry with backoff for transient issues

**Recovery:**
```bash
# Check Redis status
docker exec omniguard-redis redis-cli ping

# Restart if needed
docker compose restart redis

# Verify connection restored
curl http://localhost/health | jq '.redis'
```

**Recovery Verification:**
- [ ] `redis_up == 1` in Prometheus
- [ ] Health endpoint shows `redis.status = "healthy"`
- [ ] Cache HITs resuming in metrics

---

### FM-002: Upstream API Unavailable

**Trigger:**
- Upstream service (JSONPlaceholder) is down
- Network issues between OmniGuard and upstream
- Upstream rate limiting triggered
- DNS resolution failure

**Impact:**
- All cache MISS requests fail with 502/503
- Cached data continues serving (cache HITs work)
- New or expired data cannot be fetched
- User-facing errors for uncached endpoints

**Detection:**
```yaml
Alert: UpstreamDown
Metric: omniguard_errors_total{error_type="server_error"} rate > 0.1
Threshold: 2 minutes
```

**Mitigation:**
1. Serve stale cache if available (not currently implemented)
2. Return graceful error response with context
3. Retry with exponential backoff (3 attempts max)

**Recovery:**
- External dependency - no direct recovery action
- Verify upstream health: `curl https://jsonplaceholder.typicode.com/posts/1`

**Recovery Verification:**
- [ ] Upstream responds to test request
- [ ] Error rate returns to <1%
- [ ] New cache entries being created

---

### FM-003: API Instance Crash

**Trigger:**
- Unhandled exception in application code
- OOMKilled by container runtime
- Python interpreter crash
- Deadlock or infinite loop

**Impact:**
- Reduced capacity (N-1 instances)
- Nginx routes traffic to remaining instances
- Slight latency increase due to rebalancing
- Potential request failures during failover

**Detection:**
```yaml
Alert: ServiceDown
Metric: up{job="omniguard-api"} == 0
Threshold: 1 minute
```

**Mitigation:**
1. Docker restart policy auto-restarts container
2. Nginx health checks remove unhealthy upstream
3. Load distributed to remaining instances

**Recovery:**
```bash
# Check container status
docker compose ps omniguard-api

# Check exit reason
docker inspect omniguard-api-1 --format='{{.State.OOMKilled}}'

# Manual restart if needed
docker compose up -d --scale omniguard-api=3 --no-deps omniguard-api
```

**Recovery Verification:**
- [ ] All 3 instances showing "Up (healthy)"
- [ ] Instance visible in Prometheus targets
- [ ] Traffic distributed across all instances

---

### FM-004: Nginx Load Balancer Down

**Trigger:**
- Nginx container crash
- Configuration syntax error
- Port binding conflict
- Resource exhaustion

**Impact:**
- **Complete service outage**
- No traffic reaches API instances
- All external requests fail
- Health checks inaccessible

**Detection:**
```yaml
Alert: NginxDown
Metric: Container health check fails
Threshold: 30 seconds
```

**Mitigation:**
1. None - this is a total outage scenario
2. Failover to secondary LB (if configured)

**Recovery:**
```bash
# Check nginx logs
docker compose logs nginx --tail=50

# Validate config
docker exec omniguard-nginx nginx -t

# Restart
docker compose restart nginx

# Or full recreate
docker compose up -d --force-recreate nginx
```

**Recovery Verification:**
- [ ] `curl http://localhost/health` returns 200
- [ ] Nginx container status is "healthy"
- [ ] Traffic flowing to backend instances

---

### FM-005: High Error Rate (>5%)

**Trigger:**
- Upstream API issues
- Application bugs
- Resource exhaustion
- Configuration errors
- Malformed client requests

**Impact:**
- Users experience errors
- SLA breach potential
- Customer complaints
- Data inconsistency risk

**Detection:**
```yaml
Alert: High5xxErrorRate
Metric: rate(omniguard_errors_total{error_type="server_error"}[5m]) / rate(omniguard_requests_total[5m]) > 0.05
Threshold: 1 minute
```

**Mitigation:**
1. Identify error source from logs
2. Check upstream health
3. Scale up if resource-related
4. Rollback recent deployments if applicable

**Recovery:**
```bash
# Check error breakdown
curl -s http://localhost:9090/api/v1/query?query=omniguard_errors_total | jq

# View recent errors
docker compose logs omniguard-api 2>&1 | grep -i error | tail -20
```

**Recovery Verification:**
- [ ] Error rate < 1%
- [ ] No new error types appearing
- [ ] Alert resolved in Alertmanager

---

### FM-006: Cache Poisoning

**Trigger:**
- Upstream returns incorrect data
- Application caches error response
- Race condition during cache update
- Manual cache manipulation

**Impact:**
- Users receive stale/incorrect data
- Potentially serving error pages as cached content
- Trust issues with API responses

**Detection:**
- Manual verification or user reports
- Inconsistent responses for same endpoint

**Mitigation:**
1. Clear affected cache keys immediately
2. Force refresh on critical endpoints
3. Investigate root cause

**Recovery:**
```bash
# Clear specific key
curl -X DELETE "http://localhost/api/cache?key=/posts"

# Clear all cache
docker exec omniguard-redis redis-cli FLUSHDB

# Verify cache cleared
docker exec omniguard-redis redis-cli KEYS "omniguard:*"
```

**Recovery Verification:**
- [ ] Fresh data being cached
- [ ] No complaints of stale data
- [ ] Cache hit ratio recovering

---

### FM-007: Memory Exhaustion (OOM)

**Trigger:**
- Memory leak in application
- Large response bodies
- Too many concurrent requests
- Redis memory limit reached

**Impact:**
- Container killed by OOM killer
- Service disruption during restart
- Potential data loss in Redis if not persisted

**Detection:**
```yaml
Alert: HighMemoryUsage
Metric: container_memory_usage_bytes / container_spec_memory_limit_bytes > 0.9
Threshold: 5 minutes
```

**Mitigation:**
1. Increase memory limits (temporary)
2. Scale horizontally to distribute load
3. Identify memory leak and patch

**Recovery:**
```bash
# Check if OOMKilled
docker inspect omniguard-api-1 --format='{{.State.OOMKilled}}'

# Increase limit in docker-compose.yml
# memory: 512M -> 1G

# Restart with new limits
docker compose up -d
```

**Recovery Verification:**
- [ ] Memory usage stable below 75%
- [ ] No OOMKilled events
- [ ] Service uptime increasing

---

### FM-008: Network Partition

**Trigger:**
- Docker network issues
- DNS resolution failures
- Container network isolation
- Network congestion

**Impact:**
- Services cannot communicate
- Redis appears down to API
- Upstream unreachable
- Partial or complete outage

**Detection:**
- Multiple service health checks failing
- Cross-service communication errors

**Mitigation:**
1. Identify network scope of issue
2. Restart Docker networking
3. Recreate container network

**Recovery:**
```bash
# Check network
docker network inspect omniguard-network

# Test container connectivity
docker exec omniguard-api-1 ping -c 3 redis

# Recreate network
docker compose down
docker network prune -f
docker compose up -d
```

**Recovery Verification:**
- [ ] All containers on same network
- [ ] Inter-container ping successful
- [ ] Health checks passing

---

### FM-009: Certificate Expiry

**Trigger:**
- TLS certificates expire
- Certificate renewal failed
- Wrong certificate deployed

**Impact:**
- HTTPS connections fail
- Browser security warnings
- API clients reject connections

**Detection:**
- Monitor certificate expiry dates
- Alert 7 days before expiry

**Mitigation:**
1. Have certificate renewal automated (Let's Encrypt)
2. Keep backup certificates ready
3. Know the renewal process

**Recovery:**
```bash
# Check certificate expiry
echo | openssl s_client -connect localhost:443 2>/dev/null | openssl x509 -noout -dates

# Renew certificate (depends on your CA)
# For Let's Encrypt: certbot renew

# Reload nginx with new cert
docker exec omniguard-nginx nginx -s reload
```

**Recovery Verification:**
- [ ] Certificate valid for >30 days
- [ ] HTTPS connections successful
- [ ] No browser warnings

---

### FM-010: Disk Space Exhaustion

**Trigger:**
- Log files growing unbounded
- Docker images/volumes accumulating
- Prometheus metrics retention
- Redis RDB/AOF files

**Impact:**
- Container crashes on write attempts
- Prometheus stops recording
- Redis persistence fails
- Application logging fails

**Detection:**
```bash
df -h /var/lib/docker
```

**Mitigation:**
1. Configure log rotation
2. Set retention policies
3. Clean unused Docker resources

**Recovery:**
```bash
# Clean Docker resources
docker system prune -af

# Clear old logs
docker compose logs --no-log-prefix 2>/dev/null

# Verify space freed
df -h
```

**Recovery Verification:**
- [ ] Disk usage < 80%
- [ ] Services writing normally
- [ ] Log rotation configured

---

## 🔔 Detection & Alerting

### Alert Priority Matrix

| Priority | Response Time | Examples |
|----------|---------------|----------|
| P1 Critical | Immediate (< 5 min) | Complete outage, data loss risk |
| P2 High | < 30 min | Degraded service, high error rate |
| P3 Medium | < 2 hours | Performance degradation, warnings |
| P4 Low | Next business day | Informational, capacity planning |

### Alert Channels

| Channel | Priority | Configuration |
|---------|----------|---------------|
| PagerDuty | P1 | Service key in alertmanager.yml |
| Slack | P2-P3 | Webhook URL configured |
| Email | P3-P4 | SMTP settings in alertmanager.yml |

---

## ✅ Recovery Verification Checklist

After any incident, verify:

- [ ] All containers healthy: `docker compose ps`
- [ ] Health endpoint returns 200: `curl http://localhost/health`
- [ ] Prometheus targets up: Check Prometheus UI
- [ ] Error rate < 1%: Check Grafana dashboard
- [ ] Latency P95 < 500ms: Check metrics
- [ ] Cache hit ratio > 50%: Check stats
- [ ] No pending alerts: Check Alertmanager
- [ ] Logs clean of errors: Review recent logs

---

## 📚 Related Documentation

- [Troubleshooting Guide](./TROUBLESHOOTING.md)
- [Capacity Planning](./CAPACITY.md)
- [Runbooks](./runbooks/)
- [Deployment Guide](./DEPLOYMENT.md)
