# 🔧 OmniGuard Troubleshooting Guide

> Common issues, their symptoms, causes, and step-by-step solutions.

---

## 📋 Table of Contents

1. [Quick Diagnosis](#-quick-diagnosis)
2. [Startup Issues](#-startup-issues)
3. [Connection Issues](#-connection-issues)
4. [Performance Issues](#-performance-issues)
5. [Cache Issues](#-cache-issues)
6. [Monitoring Issues](#-monitoring-issues)
7. [Docker Issues](#-docker-issues)
8. [Debugging Tools](#-debugging-tools)

---

## 🔍 Quick Diagnosis

### Health Check Decision Tree

```
Is /health returning 200?
├── NO → Go to "Startup Issues"
└── YES → Check response content
    ├── redis.status = "unhealthy" → Go to "Redis Connection"
    ├── upstream.status = "unhealthy" → Go to "Upstream Issues"
    └── All healthy but slow → Go to "Performance Issues"
```

### Quick Status Commands

```bash
# Overall status
docker compose ps

# Recent logs (last 50 lines)
docker compose logs --tail=50

# Health check
curl -s http://localhost/health | jq

# Prometheus targets
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'
```

---

## 🚀 Startup Issues

### Issue: Container Exits Immediately

**Symptoms:**
- `docker compose ps` shows container as "Exited"
- Application never starts

**Diagnosis:**
```bash
# Check exit code and logs
docker compose logs omniguard-api | tail -100
docker inspect omniguard-api --format='{{.State.ExitCode}}'
```

**Common Causes & Solutions:**

| Exit Code | Cause | Solution |
|-----------|-------|----------|
| 1 | Python exception | Check logs for traceback |
| 137 | Out of memory (OOMKilled) | Increase memory limit |
| 139 | Segmentation fault | Check dependencies |

**Solution for Exit Code 1:**
```bash
# Usually a missing dependency or config error
docker compose logs omniguard-api 2>&1 | grep -i "error\|exception\|failed"

# Common fixes:
# 1. Missing environment variable
docker compose config  # Verify env vars are set

# 2. Port already in use
netstat -tlnp | grep 8000
```

**Solution for Exit Code 137 (OOM):**
```yaml
# Increase memory in docker-compose.yml
omniguard-api:
  deploy:
    resources:
      limits:
        memory: 512M  # Increase from 256M
```

---

### Issue: "Address Already in Use"

**Symptoms:**
```
Error: [Errno 98] Address already in use: ('0.0.0.0', 8000)
```

**Solution:**
```bash
# Find process using port 8000
netstat -tlnp | grep 8000
# or on Windows
netstat -ano | findstr 8000

# Kill the process
kill -9 <PID>
# or on Windows
taskkill /PID <PID> /F

# Restart containers
docker compose down
docker compose up -d
```

---

### Issue: "Cannot Connect to Redis"

**Symptoms:**
```
ConnectionError: Error connecting to redis://redis:6379
```

**Diagnosis:**
```bash
# Check if Redis container is running
docker compose ps redis

# Test Redis connection
docker exec omniguard-redis redis-cli ping
# Expected: PONG

# Check Redis logs
docker compose logs redis
```

**Solutions:**

1. **Redis not started yet:**
```bash
# Ensure Redis starts before API
docker compose up -d redis
sleep 5
docker compose up -d omniguard-api
```

2. **Wrong Redis host:**
```bash
# Verify REDIS_HOST in docker-compose.yml
# Should be "redis" not "localhost" in Docker network
```

3. **Redis authentication required:**
```yaml
# Add password to docker-compose.yml
environment:
  - REDIS_PASSWORD=your-password
```

---

## 🔌 Connection Issues

### Issue: Nginx Returns 502 Bad Gateway

**Symptoms:**
- Browser shows "502 Bad Gateway"
- curl returns empty response

**Diagnosis:**
```bash
# Check if API containers are running
docker compose ps omniguard-api

# Check Nginx can reach API
docker exec omniguard-nginx wget -qO- http://omniguard-api:8000/health

# Check Nginx logs
docker compose logs nginx | grep -i error
```

**Solutions:**

1. **API containers not healthy:**
```bash
# Restart API containers
docker compose restart omniguard-api
```

2. **DNS resolution issue:**
```bash
# Verify container name resolution
docker exec omniguard-nginx nslookup omniguard-api
```

3. **Network issue:**
```bash
# Recreate network
docker compose down
docker network prune -f
docker compose up -d
```

---

### Issue: Upstream API Timeout

**Symptoms:**
```json
{
  "error": true,
  "code": "UPSTREAM_ERROR",
  "message": "Upstream service unavailable after retries"
}
```

**Diagnosis:**
```bash
# Test upstream directly
curl -v https://jsonplaceholder.typicode.com/posts/1

# Check from inside container
docker exec omniguard-api-1 python -c "import httpx; print(httpx.get('https://jsonplaceholder.typicode.com/posts/1').status_code)"
```

**Solutions:**

1. **Increase timeout:**
```yaml
environment:
  - UPSTREAM_TIMEOUT=30  # Increase from default 10
```

2. **Check DNS resolution:**
```bash
docker exec omniguard-api-1 nslookup jsonplaceholder.typicode.com
```

3. **Check outbound connectivity:**
```bash
# Test from container
docker exec omniguard-api-1 ping -c 3 8.8.8.8
```

---

## ⚡ Performance Issues

### Issue: High Latency (P95 > 2s)

**Symptoms:**
- Slow API responses
- Grafana shows latency spikes
- Alert: HighLatencyP95 firing

**Diagnosis:**
```bash
# Check current latency in Prometheus
curl -s 'http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,sum(rate(omniguard_request_latency_seconds_bucket[5m]))by(le))' | jq '.data.result[0].value[1]'

# Check cache hit ratio
curl -s http://localhost/api/stats | jq '.hit_ratio'
```

**Solutions:**

1. **Low cache hit ratio (< 50%):**
```bash
# Increase TTL
environment:
  - CACHE_TTL=300  # Increase from 60s
```

2. **Redis slow:**
```bash
# Check Redis latency
docker exec omniguard-redis redis-cli --latency

# Check Redis memory
docker exec omniguard-redis redis-cli INFO memory | grep used_memory_human
```

3. **Not enough replicas:**
```bash
# Scale up
docker compose up -d --scale omniguard-api=5
```

4. **Slow upstream:**
- Enable caching more aggressively
- Consider circuit breaker pattern

---

### Issue: High CPU Usage

**Symptoms:**
- Container using 100% CPU
- System becomes unresponsive

**Diagnosis:**
```bash
# Check container stats
docker stats omniguard-api-1 omniguard-api-2 omniguard-api-3

# Check top processes in container
docker exec omniguard-api-1 top -bn1 | head -20
```

**Solutions:**

1. **Limit CPU in docker-compose.yml:**
```yaml
deploy:
  resources:
    limits:
      cpus: "0.5"
```

2. **Scale horizontally instead:**
```bash
docker compose up -d --scale omniguard-api=6
```

---

### Issue: High Memory Usage / OOMKilled

**Symptoms:**
- Container restarts unexpectedly
- `docker inspect` shows OOMKilled: true

**Diagnosis:**
```bash
# Check memory usage
docker stats --no-stream

# Check if OOMKilled
docker inspect omniguard-api-1 --format='{{.State.OOMKilled}}'
```

**Solutions:**

1. **Increase memory limit:**
```yaml
deploy:
  resources:
    limits:
      memory: 512M  # Increase
```

2. **Check for memory leaks:**
```bash
# Monitor over time
watch -n 5 'docker stats --no-stream | grep omniguard-api'
```

---

## 💾 Cache Issues

### Issue: Cache Always MISS

**Symptoms:**
- X-Cache header always shows MISS
- Cache hit ratio is 0%

**Diagnosis:**
```bash
# Check if Redis is storing keys
docker exec omniguard-redis redis-cli KEYS "omniguard:*"

# Check TTL on a key
docker exec omniguard-redis redis-cli TTL "omniguard:data:/posts"
```

**Solutions:**

1. **Redis connection issue:**
```bash
# Test Redis from API container
docker exec omniguard-api-1 python -c "
import redis
r = redis.Redis(host='redis', port=6379)
print(r.ping())
"
```

2. **Key prefix mismatch:**
```bash
# Verify CACHE_PREFIX matches in all containers
docker compose config | grep CACHE_PREFIX
```

3. **Serialization error:**
```bash
# Check logs for cache errors
docker compose logs omniguard-api | grep -i "cache"
```

---

### Issue: Cache Poisoning (Stale Data)

**Symptoms:**
- Old data being served
- Changes not reflected

**Solutions:**

1. **Clear specific cache:**
```bash
curl -X DELETE "http://localhost/api/cache?key=/posts"
```

2. **Clear all cache:**
```bash
docker exec omniguard-redis redis-cli FLUSHDB
```

3. **Force refresh:**
```bash
curl "http://localhost/api/data?force_refresh=true"
```

---

## 📊 Monitoring Issues

### Issue: Prometheus Target Down

**Symptoms:**
- Prometheus targets page shows "DOWN"
- No metrics in Grafana

**Diagnosis:**
```bash
# Check Prometheus targets
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health, lastError: .lastError}'

# Test metrics endpoint directly
curl http://localhost/metrics | head -20
```

**Solutions:**

1. **Container not exposing metrics:**
```bash
# Verify /metrics endpoint
curl -v http://localhost/metrics
```

2. **Prometheus can't reach target:**
```bash
# Test from Prometheus container
docker exec omniguard-prometheus wget -qO- http://omniguard-api:8000/metrics | head -5
```

3. **Wrong scrape config:**
```yaml
# Check prometheus.yml
scrape_configs:
  - job_name: 'omniguard-api'
    static_configs:
      - targets: ['omniguard-api:8000']  # Not localhost!
```

---

### Issue: Grafana Dashboard Empty

**Symptoms:**
- Dashboard shows "No Data"
- Panels are blank

**Solutions:**

1. **Check datasource:**
```bash
# Verify Prometheus datasource in Grafana
curl -u admin:omniguard http://localhost:3000/api/datasources
```

2. **Check time range:**
- Dashboard might be looking at wrong time period
- Reset to "Last 1 hour"

3. **Reimport dashboard:**
```bash
# Dashboard JSON is at:
# observability/grafana/provisioning/dashboards/omniguard-dashboard.json
```

---

### Issue: Alerts Not Firing

**Symptoms:**
- Conditions met but no alerts
- Alertmanager shows no alerts

**Diagnosis:**
```bash
# Check alert rules in Prometheus
curl http://localhost:9090/api/v1/rules | jq '.data.groups[].rules[] | {name: .name, state: .state}'

# Check Alertmanager
curl http://localhost:9093/api/v2/alerts
```

**Solutions:**

1. **Alert rules not loaded:**
```bash
# Verify rules file exists
docker exec omniguard-prometheus cat /etc/prometheus/rules/alerts.yml
```

2. **Webhook URL wrong:**
```yaml
# Check alertmanager.yml
receivers:
  - name: 'webhook-discord'
    webhook_configs:
      - url: 'http://your-webhook-url'  # Verify this is correct
```

---

## 🐳 Docker Issues

### Issue: "No Space Left on Device"

**Symptoms:**
```
Error: no space left on device
```

**Solutions:**
```bash
# Clean unused images and containers
docker system prune -af

# Clean volumes (WARNING: deletes data)
docker volume prune -f

# Check disk usage
docker system df
```

---

### Issue: Network Conflict

**Symptoms:**
```
Error: network omniguard-network: subnet 172.28.0.0/16 overlaps
```

**Solutions:**
```bash
# Remove conflicting network
docker network rm omniguard-network

# Or use different subnet in docker-compose.yml
networks:
  omniguard-network:
    ipam:
      config:
        - subnet: 172.30.0.0/16  # Different subnet
```

---

## 🔬 Debugging Tools

### Interactive Shell

```bash
# Get shell in running container
docker exec -it omniguard-api-1 /bin/sh

# Run Python interactively
docker exec -it omniguard-api-1 python
```

### Log Analysis

```bash
# Follow logs in real-time
docker compose logs -f omniguard-api

# Search for errors
docker compose logs omniguard-api 2>&1 | grep -i "error\|exception\|traceback"

# JSON log parsing
docker compose logs omniguard-api 2>&1 | jq -R 'fromjson? | select(.level == "ERROR")'
```

### Network Debugging

```bash
# Check container networking
docker network inspect omniguard-network

# Test connectivity between containers
docker exec omniguard-nginx ping -c 3 omniguard-api

# Check DNS resolution
docker exec omniguard-api-1 nslookup redis
```

### Redis Debugging

```bash
# Interactive Redis CLI
docker exec -it omniguard-redis redis-cli

# Common commands:
# INFO            - Server info
# KEYS *          - List all keys
# GET key         - Get value
# TTL key         - Time to live
# MONITOR         - Real-time command log (Ctrl+C to exit)
# SLOWLOG GET 10  - Slow queries
```

### Performance Profiling

```bash
# CPU profiling
docker exec omniguard-api-1 python -m cProfile -s cumtime app/main.py

# Memory profiling (install memory_profiler first)
docker exec omniguard-api-1 python -m memory_profiler app/main.py
```

---

## 🆘 Still Stuck?

1. **Check the logs** - 90% of issues are visible in logs
2. **Restart containers** - `docker compose restart`
3. **Nuclear option** - `docker compose down -v && docker compose up -d`
4. **Open an issue** - Include logs, config, and steps to reproduce

```bash
# Generate debug bundle
mkdir debug-$(date +%Y%m%d)
docker compose logs > debug-$(date +%Y%m%d)/logs.txt
docker compose config > debug-$(date +%Y%m%d)/config.txt
docker ps -a > debug-$(date +%Y%m%d)/containers.txt
curl -s http://localhost/health > debug-$(date +%Y%m%d)/health.json
```
