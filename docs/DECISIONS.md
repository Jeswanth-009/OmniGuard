# 🧠 OmniGuard Decision Log (ADR)

> Architecture Decision Records documenting why we made specific technical choices.

---

## 📋 Decision Index

| ID | Decision | Status | Date |
|----|----------|--------|------|
| ADR-001 | [Use FastAPI as Web Framework](#adr-001-use-fastapi-as-web-framework) | ✅ Accepted | 2024-01 |
| ADR-002 | [Use Redis for Caching](#adr-002-use-redis-for-caching) | ✅ Accepted | 2024-01 |
| ADR-003 | [Use Nginx as Load Balancer](#adr-003-use-nginx-as-load-balancer) | ✅ Accepted | 2024-01 |
| ADR-004 | [Use Prometheus + Grafana for Observability](#adr-004-use-prometheus--grafana-for-observability) | ✅ Accepted | 2024-01 |
| ADR-005 | [Use Docker Compose for Orchestration](#adr-005-use-docker-compose-for-orchestration) | ✅ Accepted | 2024-01 |
| ADR-006 | [Use Pydantic for Validation](#adr-006-use-pydantic-for-validation) | ✅ Accepted | 2024-01 |
| ADR-007 | [Use JSON Structured Logging](#adr-007-use-json-structured-logging) | ✅ Accepted | 2024-01 |
| ADR-008 | [3 API Replicas as Default](#adr-008-3-api-replicas-as-default) | ✅ Accepted | 2024-01 |

---

## ADR-001: Use FastAPI as Web Framework

### Status
✅ Accepted

### Context
We need a Python web framework to build a high-performance API gateway. The framework must support:
- Async operations for high concurrency
- Automatic OpenAPI documentation
- Type hints and validation
- WebSocket support (future)
- Production-ready performance

### Options Considered

| Framework | Pros | Cons |
|-----------|------|------|
| **FastAPI** | Async-native, auto docs, Pydantic integration, high performance | Newer ecosystem |
| Flask | Mature, simple, large ecosystem | Sync by default, no built-in validation |
| Django | Batteries included, ORM | Heavy for API gateway, sync-first |
| Starlette | Lightweight, fast | No auto docs, manual validation |
| aiohttp | Pure async | More boilerplate, no auto docs |

### Decision
**Use FastAPI** for the following reasons:

1. **Native async support** - Critical for a gateway handling many concurrent upstream requests
2. **Automatic OpenAPI** - Swagger UI generated from code, always in sync
3. **Pydantic integration** - Validation for free, clear error messages
4. **Performance** - One of the fastest Python frameworks (comparable to Node/Go)
5. **Developer experience** - Type hints, IDE support, less boilerplate

### Consequences
- **Positive**: High performance, excellent docs, easy to maintain
- **Negative**: Python async can be tricky, need async-compatible libraries
- **Mitigations**: Use `httpx` (async HTTP client), `redis.asyncio`

### Benchmarks
```
FastAPI:  ~15,000 req/s (async, uvicorn)
Flask:    ~3,000 req/s (sync, gunicorn)
Django:   ~2,500 req/s (sync, gunicorn)
```

---

## ADR-002: Use Redis for Caching

### Status
✅ Accepted

### Context
We need a caching layer to reduce latency and upstream load. Requirements:
- Sub-millisecond read latency
- Support for TTL (time-to-live)
- High availability options
- Simple key-value operations
- Cluster support for scaling

### Options Considered

| Solution | Pros | Cons |
|----------|------|------|
| **Redis** | Fast, TTL support, cluster mode, battle-tested | Memory-only by default |
| Memcached | Fast, simple | No persistence, limited data types |
| In-process cache | Zero latency | Lost on restart, not shared between replicas |
| PostgreSQL | Durable, already using | Too slow for hot path |
| DynamoDB | Managed, scalable | Latency, cost, vendor lock-in |

### Decision
**Use Redis** for the following reasons:

1. **Speed** - Sub-millisecond latency for cached reads
2. **TTL support** - Native `SETEX` for automatic expiration
3. **Data structures** - Strings, hashes, lists (future features)
4. **Clustering** - Can scale horizontally when needed
5. **Persistence** - Optional AOF/RDB for cache warming
6. **Ecosystem** - Excellent Python libraries (`redis-py`)

### Configuration Choices
```
maxmemory 128mb        # Limit memory usage
maxmemory-policy allkeys-lru  # Evict least recently used
appendonly yes         # Persistence for recovery
```

### Consequences
- **Positive**: Fast, reliable, well-understood
- **Negative**: Additional infrastructure to manage
- **Mitigations**: Use managed Redis (AWS ElastiCache, Redis Cloud) in production

### Why Not Memcached?
- No persistence (cache lost on restart)
- No TTL per-key (only global)
- No data structure support
- Redis has better Python ecosystem

---

## ADR-003: Use Nginx as Load Balancer

### Status
✅ Accepted

### Context
We need a load balancer to:
- Distribute traffic across API replicas
- Handle SSL termination
- Rate limiting
- Static file serving
- Health checks

### Options Considered

| Solution | Pros | Cons |
|----------|------|------|
| **Nginx** | Fast, battle-tested, low memory | Config learning curve |
| HAProxy | Excellent LB features | Less familiar, no static serving |
| Traefik | Auto-discovery, modern | More resource usage |
| AWS ALB | Managed, auto-scaling | Vendor lock-in, cost |
| Envoy | Service mesh ready | Complex for our needs |
| No LB (direct) | Simple | Single point of failure |

### Decision
**Use Nginx** for the following reasons:

1. **Performance** - Handles 10,000+ concurrent connections
2. **Low footprint** - ~2MB RAM per worker process
3. **Battle-tested** - Powers 30%+ of websites
4. **Feature-rich** - Rate limiting, caching, health checks
5. **Configuration** - Declarative, version-controllable
6. **SSL termination** - Native TLS support
7. **Team familiarity** - Well-known in the industry

### Configuration Choices
```nginx
upstream omniguard_cluster {
    server omniguard-api:8000;
    keepalive 32;              # Connection pooling
}

limit_req_zone $binary_remote_addr zone=api_limit:10m rate=100r/s;
```

### Consequences
- **Positive**: Rock-solid reliability, excellent performance
- **Negative**: Another component to maintain
- **Mitigations**: Use simple config, container-based deployment

### Why Not Traefik?
- More memory usage (~50MB vs ~5MB)
- Auto-discovery not needed with Docker Compose
- Nginx is simpler for our use case

---

## ADR-004: Use Prometheus + Grafana for Observability

### Status
✅ Accepted

### Context
We need observability for:
- Metrics collection (latency, error rates, throughput)
- Visualization (dashboards)
- Alerting (notify on issues)

### Options Considered

| Solution | Pros | Cons |
|----------|------|------|
| **Prometheus + Grafana** | Open source, powerful, industry standard | Self-hosted |
| Datadog | Managed, feature-rich | Expensive at scale |
| New Relic | APM, tracing | Cost, overhead |
| CloudWatch | AWS-native | Vendor lock-in |
| ELK Stack | Logs + metrics | Heavy, complex |

### Decision
**Use Prometheus + Grafana** for the following reasons:

1. **Open source** - No licensing costs
2. **Pull-based** - Simpler, no agent required
3. **PromQL** - Powerful query language
4. **Grafana** - Beautiful dashboards, alerting
5. **Ecosystem** - Exporters for everything
6. **Kubernetes-ready** - Standard for cloud-native
7. **Alertmanager** - Flexible alert routing

### Metrics Exported
```python
# Request metrics
omniguard_requests_total{method, endpoint, status_code}
omniguard_request_latency_seconds{method, endpoint}

# Cache metrics
omniguard_cache_hits_total
omniguard_cache_misses_total

# Error metrics
omniguard_errors_total{error_type, status_code}
```

### Consequences
- **Positive**: Powerful, free, portable
- **Negative**: Self-managed infrastructure
- **Mitigations**: Can migrate to managed Prometheus (Grafana Cloud, Amazon Managed Prometheus)

---

## ADR-005: Use Docker Compose for Orchestration

### Status
✅ Accepted

### Context
We need container orchestration for:
- Multi-container deployment
- Networking between services
- Scaling replicas
- Environment consistency

### Options Considered

| Solution | Pros | Cons |
|----------|------|------|
| **Docker Compose** | Simple, single-file, dev/prod parity | Single-node only |
| Kubernetes | Enterprise-grade, auto-scaling | Complex, overkill for MVP |
| Docker Swarm | Multi-node, simple | Limited ecosystem |
| Nomad | Flexible, lightweight | Less ecosystem |
| Bare metal | Full control | No isolation, hard to scale |

### Decision
**Use Docker Compose** for the following reasons:

1. **Simplicity** - Single YAML file defines entire stack
2. **Developer experience** - `docker compose up` and done
3. **Portability** - Works on any Docker host
4. **Scaling** - `--scale omniguard-api=5`
5. **Networking** - Automatic DNS between containers
6. **Path to K8s** - Easy to migrate via Kompose

### Upgrade Path
When we outgrow Docker Compose:
1. Convert to Kubernetes manifests (Kompose)
2. Or use Docker Swarm for multi-node

### Consequences
- **Positive**: Fast iteration, simple mental model
- **Negative**: Single-node limitation
- **Mitigations**: Plan for Kubernetes when >1000 RPS needed

---

## ADR-006: Use Pydantic for Validation

### Status
✅ Accepted

### Context
We need request/response validation that is:
- Type-safe
- Automatic
- Clear error messages
- JSON Schema compatible

### Decision
**Use Pydantic** (integrated with FastAPI):

```python
class DataRequest(BaseModel):
    endpoint: str = Field(..., pattern=r'^/')
    force_refresh: bool = False
    
    @field_validator('endpoint')
    def no_path_traversal(cls, v):
        if '..' in v:
            raise ValueError('Path traversal not allowed')
        return v
```

### Why Pydantic?
1. **FastAPI integration** - Automatic request parsing
2. **Type hints** - IDE autocomplete, static analysis
3. **Validation** - Declarative, readable
4. **Serialization** - JSON encode/decode for free
5. **Error messages** - Clear, actionable

### Consequences
- **Positive**: Fewer bugs, better DX, automatic docs
- **Negative**: Learning curve for complex validators
- **Mitigations**: Use built-in validators where possible

---

## ADR-007: Use JSON Structured Logging

### Status
✅ Accepted

### Context
We need logging that is:
- Machine-parseable (for log aggregation)
- Human-readable in development
- Contains structured metadata

### Decision
**Use JSON structured logging** with `python-json-logger`:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "message": "Cache HIT for endpoint: /posts",
  "service": "omniguard",
  "hostname": "omniguard-api-1",
  "endpoint": "/posts"
}
```

### Why JSON?
1. **Log aggregation** - Works with ELK, Loki, CloudWatch
2. **Searchable** - Query by any field
3. **Alerting** - Pattern matching on structured data
4. **Correlation** - Add request_id, trace_id
5. **Dashboards** - Metrics from logs

### Consequences
- **Positive**: Production-ready logging from day one
- **Negative**: Harder to read in console
- **Mitigations**: Use `jq` for pretty-printing

---

## ADR-008: 3 API Replicas as Default

### Status
✅ Accepted

### Context
How many API replicas should we run by default?

### Options

| Replicas | Pros | Cons |
|----------|------|------|
| 1 | Simple, low resources | No redundancy |
| 2 | Redundancy | No majority for leader election |
| **3** | Redundancy + majority | More resources |
| 5+ | High availability | Overkill for most cases |

### Decision
**Run 3 replicas by default**:

1. **Redundancy** - Can lose 1 replica and still serve traffic
2. **Load distribution** - Better than 2 for round-robin
3. **Resource balance** - Not overkill
4. **Industry standard** - Common for HA deployments

### Consequences
- **Positive**: Good balance of availability and cost
- **Negative**: 3x the API container resources
- **Mitigations**: Reduce to 2 for dev, increase for high-traffic production

---

## Template for New Decisions

```markdown
## ADR-XXX: [Title]

### Status
🟡 Proposed | ✅ Accepted | ❌ Rejected | 🔄 Superseded

### Context
What is the issue we're trying to solve?

### Options Considered
| Option | Pros | Cons |
|--------|------|------|

### Decision
What did we decide and why?

### Consequences
- **Positive**: 
- **Negative**: 
- **Mitigations**: 

### References
- [Link to relevant docs]
```
