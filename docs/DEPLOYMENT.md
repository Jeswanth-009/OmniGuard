# 🚀 OmniGuard Deployment Guide

> Complete guide for deploying OmniGuard to production, including rollback procedures and scaling strategies.

---

## 📋 Table of Contents

1. [Pre-Deployment Checklist](#-pre-deployment-checklist)
2. [Deployment Methods](#-deployment-methods)
3. [Production Deployment](#-production-deployment)
4. [Rollback Procedures](#-rollback-procedures)
5. [Scaling](#-scaling)
6. [Health Verification](#-health-verification)
7. [Maintenance Windows](#-maintenance-windows)

---

## ✅ Pre-Deployment Checklist

Before deploying to production, verify:

### Code Quality
- [ ] All tests passing (`pytest tests/ -v`)
- [ ] Coverage ≥70% (`pytest --cov=app --cov-fail-under=70`)
- [ ] No security vulnerabilities (`bandit -r app/`)
- [ ] Dependencies up-to-date (`pip list --outdated`)

### Infrastructure
- [ ] Redis cluster is healthy
- [ ] Docker registry is accessible
- [ ] Network policies allow traffic
- [ ] SSL certificates are valid
- [ ] DNS records configured

### Configuration
- [ ] Environment variables set in production
- [ ] Secrets stored securely (not in code)
- [ ] Logging configured for production
- [ ] Alertmanager webhook URLs updated

### Monitoring
- [ ] Grafana dashboards imported
- [ ] Prometheus targets configured
- [ ] Alert notification channels tested

---

## 🛠 Deployment Methods

### Method 1: Docker Compose (Simple/Single Server)

Best for: Development, staging, small-scale production.

```bash
# Pull latest images
docker compose pull

# Deploy with zero downtime
docker compose up -d --scale omniguard-api=3 --no-deps omniguard-api

# Verify deployment
docker compose ps
curl http://localhost/health
```

### Method 2: Docker Swarm (Multi-Node)

Best for: Medium-scale production with automatic failover.

```bash
# Initialize swarm (first time only)
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml omniguard

# Check services
docker service ls
docker service ps omniguard_omniguard-api
```

### Method 3: Kubernetes (Enterprise)

Best for: Large-scale, cloud-native deployments.

```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# Check deployment
kubectl get pods -n omniguard
kubectl rollout status deployment/omniguard-api -n omniguard
```

---

## 🏭 Production Deployment

### Step-by-Step Deployment Process

#### Step 1: Notify Team
```bash
# Post to Slack/Teams
echo "🚀 Starting OmniGuard deployment v1.2.0 at $(date)"
```

#### Step 2: Create Backup Point
```bash
# Tag current deployment
docker tag omniguard-api:latest omniguard-api:rollback-$(date +%Y%m%d-%H%M%S)

# Backup Redis data (optional but recommended)
docker exec omniguard-redis redis-cli BGSAVE
docker cp omniguard-redis:/data/dump.rdb ./backups/redis-$(date +%Y%m%d).rdb
```

#### Step 3: Build New Image
```bash
# Build with version tag
export VERSION=$(git describe --tags --always)
docker build -t omniguard-api:${VERSION} -t omniguard-api:latest .

# Push to registry (if using remote registry)
docker push your-registry.com/omniguard-api:${VERSION}
docker push your-registry.com/omniguard-api:latest
```

#### Step 4: Rolling Deployment
```bash
# Rolling update (one container at a time)
docker compose up -d --no-deps --build omniguard-api

# For Docker Swarm
docker service update --image omniguard-api:${VERSION} omniguard_omniguard-api

# For Kubernetes
kubectl set image deployment/omniguard-api \
  omniguard-api=your-registry.com/omniguard-api:${VERSION} \
  -n omniguard
```

#### Step 5: Verify Deployment
```bash
# Check new version is running
curl -s http://localhost/health | jq '.version'

# Check all replicas healthy
docker compose ps
curl http://localhost/health

# Monitor logs for errors
docker compose logs -f --tail=100 omniguard-api | grep -i error
```

#### Step 6: Monitor for 10 Minutes
```bash
# Watch error rate in Prometheus
curl -s 'http://localhost:9090/api/v1/query?query=sum(rate(omniguard_errors_total[5m]))' | jq

# Check Grafana dashboard for anomalies
echo "🔍 Check Grafana: http://localhost:3000/d/omniguard"
```

#### Step 7: Confirm Success
```bash
echo "✅ Deployment complete at $(date)"
```

---

## 🔄 Rollback Procedures

### When to Rollback

Rollback immediately if you observe:
- 5xx error rate > 5% for 2+ minutes
- P95 latency > 5 seconds
- Health check failures
- Redis connection errors
- Memory/CPU exhaustion

### Quick Rollback (< 2 minutes)

#### Docker Compose
```bash
# Identify rollback image
docker images omniguard-api --format "{{.Tag}}" | grep rollback

# Rollback to specific version
export ROLLBACK_TAG=rollback-20240115-103045
docker tag omniguard-api:${ROLLBACK_TAG} omniguard-api:latest
docker compose up -d --no-deps omniguard-api

# Verify rollback
curl http://localhost/health
```

#### Docker Swarm
```bash
# Rollback to previous version
docker service rollback omniguard_omniguard-api

# Or specify exact image
docker service update --rollback omniguard_omniguard-api
```

#### Kubernetes
```bash
# Automatic rollback to previous revision
kubectl rollout undo deployment/omniguard-api -n omniguard

# Rollback to specific revision
kubectl rollout undo deployment/omniguard-api --to-revision=3 -n omniguard

# Check rollback status
kubectl rollout status deployment/omniguard-api -n omniguard
```

### Post-Rollback Actions

1. **Notify team** about rollback
2. **Preserve logs** from failed deployment
3. **Create incident ticket** with details
4. **Investigate root cause** before re-deploying

```bash
# Save logs from failed deployment
docker compose logs omniguard-api > failed-deployment-$(date +%Y%m%d-%H%M%S).log

# Create incident summary
cat << EOF > incident-$(date +%Y%m%d).md
# Deployment Incident $(date)

## What happened
Deployment of version X.Y.Z failed

## Symptoms observed
- [List symptoms]

## Root cause
- [To be determined]

## Resolution
Rolled back to version A.B.C

## Action items
- [ ] Fix the issue
- [ ] Add tests to prevent recurrence
EOF
```

---

## 📈 Scaling

### Horizontal Scaling (More Replicas)

```bash
# Scale to 5 replicas
docker compose up -d --scale omniguard-api=5

# Verify scaling
docker compose ps | grep omniguard-api

# Nginx automatically discovers new containers
```

### Vertical Scaling (More Resources)

Update `docker-compose.yml`:
```yaml
omniguard-api:
  deploy:
    resources:
      limits:
        cpus: "1.0"      # Increase from 0.5
        memory: 512M     # Increase from 256M
      reservations:
        cpus: "0.25"
        memory: 256M
```

### Redis Scaling

For high-traffic scenarios, consider:

```yaml
# Redis Cluster mode
redis:
  image: redis:7.2-alpine
  command: >
    redis-server
    --maxmemory 512mb
    --maxmemory-policy allkeys-lru
```

### Scaling Checklist

| Traffic Level | API Replicas | Redis Memory | Nginx Workers |
|--------------|--------------|--------------|---------------|
| < 100 RPS | 3 | 128MB | 2 |
| 100-500 RPS | 5 | 256MB | 4 |
| 500-1000 RPS | 10 | 512MB | 8 |
| > 1000 RPS | 20+ | 1GB+ | 16 |

---

## 💚 Health Verification

### Automated Health Checks

```bash
#!/bin/bash
# health-check.sh - Run after deployment

echo "🔍 Running health verification..."

# 1. API Health
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/health)
if [ "$HTTP_CODE" != "200" ]; then
  echo "❌ Health endpoint returned $HTTP_CODE"
  exit 1
fi
echo "✅ Health endpoint: OK"

# 2. All replicas responding
for i in {1..10}; do
  SERVED_BY=$(curl -s -I http://localhost/api/data | grep X-Served-By | cut -d: -f2)
  echo "Request $i served by:$SERVED_BY"
done

# 3. Cache working
curl -s http://localhost/api/data > /dev/null  # Prime cache
CACHE_STATUS=$(curl -s -I http://localhost/api/data | grep X-Cache | cut -d: -f2 | tr -d ' ')
if [ "$CACHE_STATUS" != "HIT" ]; then
  echo "❌ Cache not working (got $CACHE_STATUS)"
  exit 1
fi
echo "✅ Cache: Working"

# 4. Prometheus metrics
METRICS=$(curl -s http://localhost/metrics | grep omniguard_requests_total | head -1)
if [ -z "$METRICS" ]; then
  echo "❌ Metrics not available"
  exit 1
fi
echo "✅ Metrics: Available"

# 5. Redis connection
REDIS_STATUS=$(curl -s http://localhost/health | jq -r '.redis.status')
if [ "$REDIS_STATUS" != "healthy" ]; then
  echo "❌ Redis unhealthy"
  exit 1
fi
echo "✅ Redis: Connected"

echo "🎉 All health checks passed!"
```

### Manual Verification Checklist

- [ ] Landing page loads (http://localhost)
- [ ] API docs accessible (http://localhost/docs)
- [ ] Health check returns 200 (http://localhost/health)
- [ ] Cache HIT/MISS headers present
- [ ] Grafana shows data (http://localhost:3000)
- [ ] Prometheus targets UP (http://localhost:9090/targets)

---

## 🔧 Maintenance Windows

### Scheduled Maintenance

```bash
#!/bin/bash
# maintenance.sh - Put system in maintenance mode

echo "🔧 Entering maintenance mode..."

# 1. Update Nginx to return 503
docker exec omniguard-nginx sh -c 'echo "return 503;" > /etc/nginx/maintenance.conf'
docker exec omniguard-nginx nginx -s reload

# 2. Wait for in-flight requests
sleep 30

# 3. Perform maintenance
echo "Performing maintenance tasks..."
# ... your tasks here ...

# 4. Exit maintenance mode
docker exec omniguard-nginx sh -c 'rm /etc/nginx/maintenance.conf'
docker exec omniguard-nginx nginx -s reload

echo "✅ Maintenance complete"
```

### Zero-Downtime Updates

For Redis updates or schema changes:

```bash
# 1. Add new replica
docker compose up -d --scale omniguard-api=4

# 2. Drain old replica
docker stop omniguard-api-1

# 3. Update and restart
docker compose up -d --no-deps omniguard-api-1

# 4. Scale back
docker compose up -d --scale omniguard-api=3
```

---

## 📞 Emergency Contacts

| Role | Contact | When to Page |
|------|---------|--------------|
| On-Call SRE | oncall@company.com | Any P1 incident |
| Backend Lead | backend-lead@company.com | Deployment failures |
| DevOps | devops@company.com | Infrastructure issues |

---

## 📝 Deployment Log Template

```markdown
# Deployment Log - [DATE]

## Summary
- **Version**: v1.2.0
- **Deployer**: @username
- **Start Time**: 14:00 UTC
- **End Time**: 14:15 UTC
- **Status**: ✅ Success / ❌ Rolled Back

## Changes
- Feature X added
- Bug Y fixed
- Dependency Z updated

## Verification
- [ ] Health check passed
- [ ] Smoke tests passed
- [ ] Monitored for 10 minutes
- [ ] No alert spike

## Notes
Any relevant observations or issues encountered.
```
