# 🚨 Runbook: High 5xx Error Rate

> **Alert**: `High5xxErrorRate`  
> **Severity**: Critical  
> **Trigger**: 5xx error rate > 5% for 1 minute

---

## 📋 Quick Reference

| Item | Value |
|------|-------|
| **Alert Name** | High5xxErrorRate |
| **Threshold** | >5% of requests returning 5xx |
| **Duration** | 1 minute |
| **Severity** | Critical |
| **On-Call Response** | Immediate |
| **Escalation** | 15 minutes |

---

## 🎯 Symptoms

- Users reporting "Server Error" or blank pages
- Grafana error rate panel turns red
- Alert notification received (Discord/Slack/PagerDuty)
- Health check may still pass (5xx can be intermittent)

---

## 🔍 Step 1: Assess Impact (2 minutes)

### Check Current Error Rate

```bash
# Query Prometheus for current error rate
curl -s 'http://localhost:9090/api/v1/query?query=sum(rate(omniguard_errors_total{error_type="server_error"}[1m]))/sum(rate(omniguard_requests_total[1m]))*100' | jq '.data.result[0].value[1]'
```

**Expected Output**: Number representing error percentage

### Check Error Distribution

```bash
# Which endpoints are failing?
curl -s 'http://localhost:9090/api/v1/query?query=sum(rate(omniguard_errors_total{error_type="server_error"}[5m]))by(endpoint)' | jq '.data.result[] | {endpoint: .metric.endpoint, rate: .value[1]}'
```

### Check Recent Deployments

```bash
# List recent container starts
docker ps --format "{{.Names}}\t{{.CreatedAt}}" | sort -k2 -r | head -10
```

**Decision Point**:
- If error rate > 20%: Proceed to **Step 2 (Emergency Rollback)**
- If error rate 5-20%: Continue to **Step 3 (Investigate)**
- If error rate dropping: Monitor for 5 minutes

---

## 🔥 Step 2: Emergency Rollback (if > 20% errors)

### 2.1 Identify Rollback Target

```bash
# List available rollback images
docker images omniguard-api --format "{{.Tag}}\t{{.CreatedAt}}" | grep rollback | head -5
```

### 2.2 Execute Rollback

```bash
# Set rollback tag
export ROLLBACK_TAG=rollback-20240115-103045  # Replace with actual

# Apply rollback
docker tag omniguard-api:${ROLLBACK_TAG} omniguard-api:latest
docker compose up -d --no-deps omniguard-api

# Verify rollback
docker compose ps | grep omniguard-api
```

### 2.3 Verify Recovery

```bash
# Check health
curl -s http://localhost/health | jq '.status'

# Check error rate (should be dropping)
watch -n 5 'curl -s "http://localhost:9090/api/v1/query?query=sum(rate(omniguard_errors_total[1m]))/sum(rate(omniguard_requests_total[1m]))*100" | jq ".data.result[0].value[1]"'
```

### 2.4 Notify Team

```
🔴 ROLLBACK EXECUTED

Service: OmniGuard
Time: [TIMESTAMP]
Rolled back to: [ROLLBACK_TAG]
Reason: 5xx error rate exceeded 20%

Current status: Monitoring
Next steps: Root cause investigation
```

**After rollback**: Skip to **Step 6 (Post-Incident)**

---

## 🔍 Step 3: Investigate Root Cause

### 3.1 Check Application Logs

```bash
# Recent errors in API logs
docker compose logs omniguard-api --since=5m 2>&1 | grep -i "error\|exception\|traceback" | tail -50

# Parse JSON logs for errors
docker compose logs omniguard-api --since=5m 2>&1 | jq -R 'fromjson? | select(.level == "ERROR")' | head -20
```

**Common Error Patterns**:

| Error Pattern | Likely Cause | Go To |
|--------------|--------------|-------|
| `ConnectionError: redis` | Redis down | Step 4.1 |
| `UpstreamError: 502` | Upstream API down | Step 4.2 |
| `MemoryError` | OOM | Step 4.3 |
| `ValidationError` | Bad input flooding | Step 4.4 |
| `TimeoutError` | Slow dependency | Step 4.5 |

### 3.2 Check Container Status

```bash
# All containers status
docker compose ps

# Check for OOMKilled
docker inspect omniguard-api-1 --format='{{.State.OOMKilled}}'
docker inspect omniguard-api-2 --format='{{.State.OOMKilled}}'
docker inspect omniguard-api-3 --format='{{.State.OOMKilled}}'

# Check container restarts
docker inspect omniguard-api-1 --format='{{.RestartCount}}'
```

### 3.3 Check Resource Usage

```bash
# Current resource usage
docker stats --no-stream

# High CPU or memory?
docker stats --no-stream --format "{{.Name}}: CPU {{.CPUPerc}}, MEM {{.MemPerc}}" | grep omniguard
```

---

## 🛠 Step 4: Apply Fix

### 4.1 Redis Connection Issues

```bash
# Check Redis status
docker compose ps redis
docker exec omniguard-redis redis-cli ping

# If Redis is down, restart it
docker compose restart redis

# Wait for connections to recover
sleep 10
docker compose restart omniguard-api
```

### 4.2 Upstream API Issues

```bash
# Check upstream health
curl -v https://jsonplaceholder.typicode.com/posts/1

# If upstream is down, enable fallback (if available)
# Or increase cache TTL to reduce upstream calls
docker exec omniguard-redis redis-cli CONFIG SET maxmemory 256mb

# Restart API to pick up cached data
docker compose restart omniguard-api
```

### 4.3 Memory Issues (OOM)

```bash
# Increase memory limits
# Edit docker-compose.yml:
# memory: 512M  # Increase from 256M

# Apply changes
docker compose up -d --no-deps omniguard-api

# Or scale horizontally
docker compose up -d --scale omniguard-api=5
```

### 4.4 Bad Input Flooding

```bash
# Check for IP flooding
docker compose logs nginx --since=5m | grep -oP '\d+\.\d+\.\d+\.\d+' | sort | uniq -c | sort -rn | head -10

# If one IP is flooding, block it
# Add to nginx.conf: deny 1.2.3.4;
docker exec omniguard-nginx nginx -s reload
```

### 4.5 Slow Dependencies

```bash
# Check latency percentiles
curl -s 'http://localhost:9090/api/v1/query?query=histogram_quantile(0.99,sum(rate(omniguard_request_latency_seconds_bucket[5m]))by(le))' | jq '.data.result[0].value[1]'

# If P99 > 5s, increase timeout
# Edit config.py: UPSTREAM_TIMEOUT = 30

# Or reduce load
docker compose up -d --scale omniguard-api=5
```

---

## ✅ Step 5: Verify Recovery

### 5.1 Monitor Error Rate

```bash
# Watch error rate for 5 minutes
watch -n 10 'curl -s "http://localhost:9090/api/v1/query?query=sum(rate(omniguard_errors_total[1m]))/sum(rate(omniguard_requests_total[1m]))*100" | jq ".data.result[0].value[1]"'
```

**Expected**: Error rate should drop below 1% within 5 minutes

### 5.2 Smoke Test

```bash
# Test critical endpoints
curl -w "Status: %{http_code}, Time: %{time_total}s\n" -o /dev/null -s http://localhost/health
curl -w "Status: %{http_code}, Time: %{time_total}s\n" -o /dev/null -s http://localhost/api/data
```

### 5.3 Confirm Alert Resolved

Check Alertmanager: http://localhost:9093

The alert should move from "Firing" to "Resolved"

---

## 📝 Step 6: Post-Incident

### 6.1 Document Incident

```markdown
# Incident Report - [DATE]

## Timeline
- [HH:MM] Alert fired
- [HH:MM] On-call acknowledged
- [HH:MM] Root cause identified
- [HH:MM] Fix applied
- [HH:MM] Service recovered

## Root Cause
[Description of what caused the 5xx errors]

## Resolution
[What was done to fix it]

## Impact
- Duration: [X minutes]
- Error rate peak: [Y%]
- Estimated affected requests: [Z]

## Action Items
- [ ] Add monitoring for [X]
- [ ] Fix underlying bug
- [ ] Update runbook with learnings
```

### 6.2 Notify Stakeholders

```
✅ INCIDENT RESOLVED

Service: OmniGuard
Incident Duration: [X minutes]
Root Cause: [Brief description]
Resolution: [Brief description]
Impact: [Estimated affected users/requests]

Full incident report to follow.
```

### 6.3 Create Follow-up Ticket

Create a ticket for:
- Root cause fix (if temporary workaround applied)
- Prevention measures
- Monitoring improvements

---

## 📞 Escalation

| Time | Action |
|------|--------|
| 0-5 min | Primary on-call investigates |
| 5-15 min | If unresolved, page secondary |
| 15-30 min | If unresolved, page team lead |
| 30+ min | Incident commander takes over |

---

## 📚 Related Runbooks

- [Runbook: Service Down](./service-down.md)
- [Runbook: High Latency](./high-latency.md)
- [Runbook: Redis Down](./redis-down.md)
