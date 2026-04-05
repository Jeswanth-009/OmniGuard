# 🚨 Runbook: Service Down

> **Alert**: `ServiceDown`  
> **Severity**: Critical  
> **Trigger**: One or more API instances unreachable for 1 minute

---

## 📋 Quick Reference

| Item | Value |
|------|-------|
| **Alert Name** | ServiceDown |
| **Threshold** | Instance health check fails |
| **Duration** | 1 minute |
| **Severity** | Critical |
| **On-Call Response** | Immediate |
| **Escalation** | 10 minutes |

---

## 🔍 Step 1: Assess Scope (1 minute)

### Check Which Instances Are Down

```bash
# Check all container status
docker compose ps

# Expected output shows all services "Up (healthy)"
# Look for "Exit" or "Unhealthy" status
```

### Check Prometheus Targets

```bash
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.health != "up") | {job: .labels.job, instance: .labels.instance, health: .health, lastError: .lastError}'
```

### Check If Service Is Partially Up

```bash
# Test through load balancer
curl -s http://localhost/health

# If this works, some instances are still serving traffic
# If this fails, all instances are down
```

**Decision Point**:
- All instances down: Proceed to **Step 2 (Full Outage)**
- Some instances down: Proceed to **Step 3 (Partial Outage)**

---

## 🔥 Step 2: Full Outage Recovery

### 2.1 Check Infrastructure

```bash
# Is Docker daemon running?
docker info

# Is the host under resource pressure?
free -h
df -h
```

### 2.2 Check Container Logs for Crash Reason

```bash
# Get logs from crashed container
docker compose logs omniguard-api --tail=100

# Check for common crash patterns
docker compose logs omniguard-api 2>&1 | grep -i "error\|killed\|fatal\|panic"
```

### 2.3 Restart All Services

```bash
# Full restart
docker compose down
docker compose up -d

# Wait for health checks
sleep 30

# Verify recovery
docker compose ps
curl http://localhost/health
```

### 2.4 If Restart Fails

```bash
# Check for port conflicts
netstat -tlnp | grep -E "80|8000|6379"

# Check for resource exhaustion
docker system df
docker system prune -f  # Clean up if needed

# Try starting services individually
docker compose up -d redis
sleep 5
docker compose up -d omniguard-api
sleep 10
docker compose up -d nginx
```

---

## 🛠 Step 3: Partial Outage Recovery

### 3.1 Identify Failing Instance

```bash
# List all API containers with status
docker ps -a --filter "name=omniguard-api" --format "{{.Names}}\t{{.Status}}"
```

### 3.2 Check Specific Instance Logs

```bash
# Replace N with the failing instance number
docker logs omniguard-api-N --tail=100
```

### 3.3 Restart Failing Instance

```bash
# Restart specific container
docker restart omniguard-api-N

# Verify it's back
docker ps | grep omniguard-api-N
```

### 3.4 If Instance Won't Start

```bash
# Remove and recreate
docker rm -f omniguard-api-N
docker compose up -d --scale omniguard-api=3 --no-deps omniguard-api
```

---

## 🔍 Step 4: Root Cause Investigation

### Common Causes

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| Container exits immediately | Missing config/dependency | Check logs, verify env vars |
| Container restarts repeatedly | OOMKilled or crash loop | Increase memory, fix bug |
| Container "Unhealthy" | Health check failing | Check /health endpoint |
| All containers down | Docker daemon issue | Restart Docker |

### Check OOMKilled

```bash
for i in 1 2 3; do
  echo "Container $i OOMKilled: $(docker inspect omniguard-api-$i --format='{{.State.OOMKilled}}')"
done
```

### Check Exit Code

```bash
docker inspect omniguard-api-1 --format='{{.State.ExitCode}}'
# Exit codes:
# 0 = Normal exit
# 1 = Application error
# 137 = OOMKilled (128 + 9)
# 139 = Segfault (128 + 11)
```

### Check Resource Limits

```bash
# View resource usage
docker stats --no-stream

# If near limits, increase in docker-compose.yml
```

---

## ✅ Step 5: Verify Recovery

### 5.1 All Instances Healthy

```bash
# Check all containers
docker compose ps

# Expected: All show "Up (healthy)"
```

### 5.2 Test Endpoints

```bash
# Health check
curl -s http://localhost/health | jq

# Data endpoint
curl -s http://localhost/api/data | jq '.success'

# Metrics
curl -s http://localhost/metrics | head -5
```

### 5.3 Check Load Balancing

```bash
# Verify traffic goes to all instances
for i in {1..10}; do
  curl -s -I http://localhost/api/data | grep X-Served-By
done | sort | uniq -c

# Should show distribution across all instances
```

### 5.4 Monitor for 10 Minutes

```bash
watch -n 30 'docker compose ps | grep omniguard-api'
```

---

## 📝 Step 6: Post-Incident

### Document the Incident

```markdown
## Incident: Service Down - [DATE]

### Timeline
- [HH:MM] Alert: ServiceDown fired
- [HH:MM] Investigation started
- [HH:MM] Root cause identified: [X]
- [HH:MM] Fix applied
- [HH:MM] Service restored

### Root Cause
[What caused the service to go down]

### Impact
- Downtime: [X minutes]
- Affected endpoints: [All / Partial]
- User impact: [Description]

### Prevention
[What changes will prevent recurrence]
```

### Notification Template

```
🟢 SERVICE RESTORED

Service: OmniGuard
Downtime: [X minutes]
Root Cause: [Brief description]
Resolution: [What was done]

Monitoring for stability.
```

---

## 🔄 Prevention Checklist

After recovery, review:

- [ ] Memory limits appropriate?
- [ ] Health check timeout adequate?
- [ ] Logging sufficient to diagnose?
- [ ] Auto-restart policy configured?
- [ ] Alerting threshold appropriate?

---

## 📞 Escalation Path

| Time | Action |
|------|--------|
| 0-2 min | Primary on-call investigates |
| 2-10 min | Attempt recovery |
| 10 min | Page secondary if unresolved |
| 20 min | Page engineering lead |
| 30 min | Incident commander, all-hands |

---

## 📚 Related Runbooks

- [Runbook: High 5xx Error Rate](./high-5xx-error-rate.md)
- [Runbook: Redis Down](./redis-down.md)
- [Runbook: High Latency](./high-latency.md)
