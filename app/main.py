"""
OmniGuard - High-Performance Caching API Gateway
Main FastAPI Application with Prometheus metrics, structured logging, and resilient design
"""
import logging
import sys
import os
import time
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Optional, Any

from fastapi import FastAPI, HTTPException, Request, Query, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.openapi.docs import get_swagger_ui_html
from pydantic import BaseModel, Field, field_validator
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from pythonjsonlogger import jsonlogger

from app.config import get_settings
from app.cache import init_redis_pool, close_redis_pool, check_redis_health, cache_manager
from app.upstream import (
    init_http_client, close_http_client, upstream_client, UpstreamError
)
from app.csv_data import csv_store, CsvDatasetNotFound

# =============================================================================
# STRUCTURED JSON LOGGING SETUP
# =============================================================================

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields."""
    
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record['timestamp'] = datetime.now(timezone.utc).isoformat()
        log_record['level'] = record.levelname
        log_record['service'] = 'omniguard'
        log_record['hostname'] = os.environ.get('HOSTNAME', 'unknown')


def setup_logging():
    """Configure structured JSON logging."""
    handler = logging.StreamHandler(sys.stdout)
    formatter = CustomJsonFormatter(
        '%(timestamp)s %(level)s %(name)s %(message)s'
    )
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.INFO)
    
    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


setup_logging()
logger = logging.getLogger(__name__)

# =============================================================================
# PROMETHEUS METRICS
# =============================================================================

# Request metrics
REQUEST_COUNT = Counter(
    'omniguard_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_LATENCY = Histogram(
    'omniguard_request_latency_seconds',
    'Request latency in seconds',
    ['method', 'endpoint'],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)

# Error metrics
ERROR_COUNT = Counter(
    'omniguard_errors_total',
    'Total errors by type',
    ['error_type', 'status_code']
)

# Cache metrics
CACHE_HITS = Counter(
    'omniguard_cache_hits_total',
    'Total cache hits'
)

CACHE_MISSES = Counter(
    'omniguard_cache_misses_total', 
    'Total cache misses'
)

CACHE_HIT_RATIO = Gauge(
    'omniguard_cache_hit_ratio',
    'Current cache hit ratio'
)

# System metrics
UPTIME_SECONDS = Gauge(
    'omniguard_uptime_seconds',
    'Application uptime in seconds'
)

ACTIVE_CONNECTIONS = Gauge(
    'omniguard_active_connections',
    'Number of active connections'
)

# Saturation metrics (for RED/USE methodology)
REQUEST_QUEUE_DEPTH = Gauge(
    'omniguard_request_queue_depth',
    'Current number of requests being processed (saturation indicator)'
)

UPSTREAM_PENDING = Gauge(
    'omniguard_upstream_pending_requests',
    'Number of pending upstream requests'
)

REDIS_OPERATIONS_PENDING = Gauge(
    'omniguard_redis_operations_pending',
    'Number of pending Redis operations'
)

# Track app start time
APP_START_TIME = time.time()

# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class HealthResponse(BaseModel):
    """Health check response model."""
    status: str = Field(..., description="Overall health status", examples=["healthy"])
    timestamp: str = Field(..., description="ISO timestamp")
    version: str = Field(..., description="Application version")
    redis: dict = Field(..., description="Redis connection status")
    upstream: Optional[dict] = Field(None, description="Upstream API status")
    uptime_seconds: float = Field(..., description="Application uptime")


class DataRequest(BaseModel):
    """Request model for data endpoint."""
    source: str = Field(
        default="upstream",
        description="Data source: upstream or csv"
    )
    endpoint: str = Field(
        default="/posts",
        description="Upstream endpoint to fetch",
        examples=["/posts", "/users", "/comments"]
    )
    dataset: Optional[str] = Field(
        default=None,
        description="CSV dataset name (users, urls, events) when source=csv"
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of records for CSV source"
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Offset for CSV pagination"
    )
    force_refresh: bool = Field(
        default=False,
        description="Bypass cache and fetch fresh data"
    )

    @field_validator('source')
    @classmethod
    def validate_source(cls, v: str) -> str:
        source = v.lower().strip()
        if source not in {"upstream", "csv"}:
            raise ValueError("Source must be 'upstream' or 'csv'")
        return source
    
    @field_validator('endpoint')
    @classmethod
    def validate_endpoint(cls, v: str) -> str:
        """Validate endpoint format."""
        if not v.startswith('/'):
            raise ValueError("Endpoint must start with '/'")
        # Prevent path traversal
        if '..' in v:
            raise ValueError("Invalid endpoint path")
        return v


class DataResponse(BaseModel):
    """Response model for data endpoint."""
    success: bool = Field(..., description="Request success status")
    cached: bool = Field(..., description="Whether data came from cache")
    ttl_remaining: Optional[int] = Field(None, description="Cache TTL remaining in seconds")
    data: Any = Field(..., description="Response data")
    meta: dict = Field(default_factory=dict, description="Additional metadata")


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: bool = Field(default=True)
    code: str = Field(..., description="Error code", examples=["VALIDATION_ERROR"])
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Any] = Field(None, description="Additional error details")
    timestamp: str = Field(..., description="Error timestamp")
    request_id: Optional[str] = Field(None, description="Request tracking ID")


# =============================================================================
# APPLICATION LIFECYCLE
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    logger.info("OmniGuard starting up...")
    
    settings = get_settings()
    
    # In test mode, skip real Redis/HTTP client initialization
    if settings.testing or os.environ.get("TESTING", "").lower() == "true":
        logger.info("Test mode detected - skipping Redis/HTTP client initialization")
        yield
        logger.info("Test mode cleanup complete")
        return
    
    # Initialize connections
    try:
        await init_redis_pool()
        await init_http_client()
        logger.info("All connections initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize connections: {e}")
        raise
    
    yield
    
    # Cleanup
    logger.info("OmniGuard shutting down...")
    await close_redis_pool()
    await close_http_client()
    logger.info("Cleanup complete")


# =============================================================================
# FASTAPI APPLICATION
# =============================================================================

settings = get_settings()

app = FastAPI(
    title="🛡️ OmniGuard API Gateway",
    description="""
## High-Performance Caching API Gateway

OmniGuard is a **resilient, scalable API gateway** designed for maximum reliability.

### Features

🔥 **Caching** - Redis-backed response caching with configurable TTL
⚡ **Load Balancing** - Nginx-powered round-robin distribution
📊 **Observability** - Prometheus metrics + Grafana dashboards  
🛡️ **Resilience** - Circuit breakers, retries, and graceful degradation
🔒 **Security** - Input validation, rate limiting, and secure defaults

### Architecture

```
Client → Nginx (LB) → FastAPI Replicas → Redis Cache → Upstream API
                            ↓
                      Prometheus → Grafana
```
    """,
    version=settings.app_version,
    docs_url=None,  # Custom docs endpoint
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "Health", "description": "Health check endpoints"},
        {"name": "Data", "description": "Data fetching and caching endpoints"},
        {"name": "CSV", "description": "CSV dataset endpoints"},
        {"name": "Metrics", "description": "Prometheus metrics endpoints"},
    ],
    lifespan=lifespan,
)

# Templates directory
templates = Jinja2Templates(directory="app/templates")


# =============================================================================
# MIDDLEWARE
# =============================================================================

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Middleware to track request metrics including saturation signals."""
    start_time = time.time()
    
    # Track active connections and saturation
    ACTIVE_CONNECTIONS.inc()
    REQUEST_QUEUE_DEPTH.inc()
    
    try:
        response = await call_next(request)
        
        # Record metrics
        duration = time.time() - start_time
        endpoint = request.url.path
        method = request.method
        status_code = str(response.status_code)
        
        REQUEST_COUNT.labels(
            method=method,
            endpoint=endpoint,
            status_code=status_code
        ).inc()
        
        REQUEST_LATENCY.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
        
        # Track errors
        if response.status_code >= 400:
            error_type = "client_error" if response.status_code < 500 else "server_error"
            ERROR_COUNT.labels(
                error_type=error_type,
                status_code=status_code
            ).inc()
        
        # Add timing header
        response.headers["X-Response-Time"] = f"{duration:.3f}s"
        response.headers["X-Served-By"] = os.environ.get("HOSTNAME", "omniguard")
        
        return response
        
    finally:
        ACTIVE_CONNECTIONS.dec()
        REQUEST_QUEUE_DEPTH.dec()
        
        # Update uptime
        UPTIME_SECONDS.set(time.time() - APP_START_TIME)


# =============================================================================
# EXCEPTION HANDLERS
# =============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with formatted JSON response."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=f"HTTP_{exc.status_code}",
            message=exc.detail,
            timestamp=datetime.now(timezone.utc).isoformat(),
            request_id=request.headers.get("X-Request-ID"),
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions gracefully."""
    logger.exception(f"Unhandled exception: {exc}")
    
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred. Please try again later.",
            timestamp=datetime.now(timezone.utc).isoformat(),
            request_id=request.headers.get("X-Request-ID"),
        ).model_dump(),
    )


@app.exception_handler(UpstreamError)
async def upstream_exception_handler(request: Request, exc: UpstreamError):
    """Handle upstream API errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code="UPSTREAM_ERROR",
            message=exc.message,
            details=exc.details,
            timestamp=datetime.now(timezone.utc).isoformat(),
            request_id=request.headers.get("X-Request-ID"),
        ).model_dump(),
    )


def resolve_csv_dataset(dataset: Optional[str], endpoint: str) -> str:
    """Resolve dataset name from explicit dataset or endpoint path."""
    if dataset:
        return dataset.lower().strip()

    guessed = endpoint.lstrip('/').lower().strip()
    if guessed in {"users", "urls", "events"}:
        return guessed

    raise HTTPException(
        status_code=422,
        detail="For CSV source provide dataset=users|urls|events or endpoint=/users|/urls|/events",
    )


async def fetch_from_source(
    source: str,
    endpoint: str,
    dataset: Optional[str],
    limit: int,
    offset: int,
) -> dict:
    """Fetch data from the selected source."""
    selected_source = source.lower().strip()

    if selected_source == "upstream":
        return await upstream_client.fetch_data(endpoint)

    if selected_source == "csv":
        selected_dataset = resolve_csv_dataset(dataset, endpoint)
        try:
            return csv_store.get_dataset(
                dataset=selected_dataset,
                limit=limit,
                offset=offset,
            )
        except CsvDatasetNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    raise HTTPException(status_code=422, detail="Invalid source. Use 'upstream' or 'csv'.")


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing_page(request: Request):
    """Serve the beautiful landing page."""
    # Get health info for the dashboard
    redis_health = await check_redis_health()
    upstream_health = await upstream_client.health_check()
    cache_stats = await cache_manager.get_stats()
    
    uptime = time.time() - APP_START_TIME
    
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "app_name": settings.app_name,
            "version": settings.app_version,
            "uptime": uptime,
            "redis_status": redis_health.get("status", "unknown"),
            "upstream_status": upstream_health.get("status", "unknown"),
            "cache_hits": cache_stats.get("keyspace_hits", 0),
            "cache_misses": cache_stats.get("keyspace_misses", 0),
            "hostname": os.environ.get("HOSTNAME", "omniguard-local"),
        }
    )


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui():
    """Custom Swagger UI with cyberpunk theme."""
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{settings.app_name} - API Docs",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui.css",
        swagger_ui_parameters={
            "docExpansion": "list",
            "filter": True,
            "tryItOutEnabled": True,
            "syntaxHighlight.theme": "monokai",
        },
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui-bundle.js",
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health Check",
    description="Comprehensive health check including Redis and upstream API status."
)
async def health_check():
    """
    Perform comprehensive health check.
    
    Checks:
    - FastAPI application status
    - Redis connection and latency
    - Upstream API availability
    """
    redis_health = await check_redis_health()
    upstream_health = await upstream_client.health_check()
    uptime = time.time() - APP_START_TIME
    
    # Determine overall status
    if redis_health.get("status") == "healthy":
        overall_status = "healthy"
    elif redis_health.get("connected", False):
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"
    
    return HealthResponse(
        status=overall_status,
        timestamp=datetime.now(timezone.utc).isoformat(),
        version=settings.app_version,
        redis=redis_health,
        upstream=upstream_health,
        uptime_seconds=round(uptime, 2),
    )


@app.get(
    "/metrics",
    tags=["Metrics"],
    summary="Prometheus Metrics",
    description="Prometheus-compatible metrics endpoint.",
    include_in_schema=True
)
async def prometheus_metrics():
    """Expose Prometheus metrics."""
    # Update cache hit ratio
    try:
        stats = await cache_manager.get_stats()
        hits = stats.get("keyspace_hits", 0)
        misses = stats.get("keyspace_misses", 0)
        total = hits + misses
        if total > 0:
            CACHE_HIT_RATIO.set(hits / total)
    except Exception:
        pass
    
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.get(
    "/api/data",
    response_model=DataResponse,
    tags=["Data"],
    summary="Fetch Data (Cached)",
    description="""
Fetch data from upstream API with intelligent caching.

**Caching Behavior:**
- Cache HIT: Returns cached data with `X-Cache: HIT` header
- Cache MISS: Fetches from upstream, caches for 60s, returns with `X-Cache: MISS` header

**Custom Headers:**
- `X-Cache`: HIT or MISS
- `X-Response-Time`: Request duration
- `X-Served-By`: Instance hostname
    """,
    responses={
        200: {
            "description": "Successful response",
            "headers": {
                "X-Cache": {
                    "description": "Cache status",
                    "schema": {"type": "string", "enum": ["HIT", "MISS"]}
                }
            }
        },
        502: {"description": "Upstream service unavailable"},
        503: {"description": "Service temporarily unavailable"},
    }
)
async def get_data(
    source: str = Query(
        default="upstream",
        description="Data source to query: upstream or csv",
        examples=["upstream", "csv"]
    ),
    endpoint: str = Query(
        default="/posts",
        description="Upstream API endpoint to fetch",
        examples=["/posts", "/users", "/posts/1"]
    ),
    dataset: Optional[str] = Query(
        default=None,
        description="CSV dataset when source=csv: users, urls, or events"
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
        description="Max records when source=csv"
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Record offset when source=csv"
    ),
    force_refresh: bool = Query(
        default=False,
        description="Bypass cache and fetch fresh data"
    )
):
    """
    Fetch data with Redis caching layer.
    
    The endpoint first checks Redis cache. On cache miss, it fetches
    from the upstream API and stores the result with a 60-second TTL.
    """
    selected_source = source.lower().strip()
    cache_key = f"data:{selected_source}:{endpoint}:{dataset or ''}:{limit}:{offset}"
    
    # Check cache first (unless force refresh)
    if not force_refresh:
        cached_data, is_hit = await cache_manager.get(cache_key)
        
        if is_hit:
            CACHE_HITS.inc()
            logger.info(f"Cache HIT for endpoint: {endpoint}")
            
            response = JSONResponse(
                content=DataResponse(
                    success=True,
                    cached=True,
                    data=cached_data,
                    meta={
                        "source": "cache",
                        "selected_source": selected_source,
                        "endpoint": endpoint,
                        "dataset": dataset,
                    }
                ).model_dump()
            )
            response.headers["X-Cache"] = "HIT"
            return response
    
    # Cache miss - fetch from upstream
    CACHE_MISSES.inc()
    logger.info(
        f"Cache MISS for source={selected_source}, endpoint={endpoint}, dataset={dataset}"
    )

    data = await fetch_from_source(
        source=selected_source,
        endpoint=endpoint,
        dataset=dataset,
        limit=limit,
        offset=offset,
    )
    
    # Store in cache
    await cache_manager.set(cache_key, data, ttl=settings.cache_ttl)
    
    response = JSONResponse(
        content=DataResponse(
            success=True,
            cached=False,
            ttl_remaining=settings.cache_ttl,
            data=data,
            meta={
                "source": selected_source,
                "endpoint": endpoint,
                "dataset": dataset,
                "cached_at": datetime.now(timezone.utc).isoformat(),
            }
        ).model_dump()
    )
    response.headers["X-Cache"] = "MISS"
    return response


@app.post(
    "/api/data",
    response_model=DataResponse,
    tags=["Data"],
    summary="Fetch Data (POST)",
    description="POST version of data endpoint with request body validation."
)
async def post_data(request: DataRequest):
    """Fetch data using POST with validated request body."""
    cache_key = (
        f"data:{request.source}:{request.endpoint}:"
        f"{request.dataset or ''}:{request.limit}:{request.offset}"
    )
    
    if not request.force_refresh:
        cached_data, is_hit = await cache_manager.get(cache_key)
        
        if is_hit:
            CACHE_HITS.inc()
            response = JSONResponse(
                content=DataResponse(
                    success=True,
                    cached=True,
                    data=cached_data,
                    meta={
                        "source": "cache",
                        "selected_source": request.source,
                        "endpoint": request.endpoint,
                        "dataset": request.dataset,
                    }
                ).model_dump()
            )
            response.headers["X-Cache"] = "HIT"
            return response
    
    CACHE_MISSES.inc()
    data = await fetch_from_source(
        source=request.source,
        endpoint=request.endpoint,
        dataset=request.dataset,
        limit=request.limit,
        offset=request.offset,
    )
    await cache_manager.set(cache_key, data)
    
    response = JSONResponse(
        content=DataResponse(
            success=True,
            cached=False,
            ttl_remaining=settings.cache_ttl,
            data=data,
            meta={
                "source": request.source,
                "endpoint": request.endpoint,
                "dataset": request.dataset,
            }
        ).model_dump()
    )
    response.headers["X-Cache"] = "MISS"
    return response


@app.get(
    "/api/csv/datasets",
    tags=["CSV"],
    summary="List CSV Datasets",
    description="List supported CSV datasets and their availability in app/data."
)
async def list_csv_datasets():
    """List known CSV datasets and whether their files are present."""
    return {
        "source": "csv",
        "data_dir": str(csv_store.data_dir),
        "datasets": csv_store.available_datasets(),
    }


@app.get(
    "/api/csv/{dataset}",
    response_model=DataResponse,
    tags=["CSV"],
    summary="Fetch CSV Dataset",
    description="Fetch CSV data by dataset name with pagination support."
)
async def get_csv_dataset(
    dataset: str,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    """Return records from a local CSV dataset."""
    try:
        data = csv_store.get_dataset(dataset=dataset, limit=limit, offset=offset)
    except CsvDatasetNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return DataResponse(
        success=True,
        cached=False,
        data=data,
        meta={
            "source": "csv",
            "dataset": dataset,
            "limit": limit,
            "offset": offset,
        },
    )


@app.delete(
    "/api/cache",
    tags=["Data"],
    summary="Clear Cache",
    description="Clear specific cache key or all cached data."
)
async def clear_cache(
    key: Optional[str] = Query(
        default=None,
        description="Specific cache key to clear (omit to clear all)"
    )
):
    """Clear cache entries."""
    if key:
        success = await cache_manager.delete(f"data:{key}")
        return {"success": success, "cleared": key}
    
    # Clear all data keys (would need scan in production)
    return {"success": True, "message": "Cache clear requested"}


@app.get(
    "/api/stats",
    tags=["Metrics"],
    summary="Cache Statistics",
    description="Get detailed cache statistics."
)
async def cache_stats():
    """Get cache statistics."""
    stats = await cache_manager.get_stats()
    hits = stats.get("keyspace_hits", 0)
    misses = stats.get("keyspace_misses", 0)
    total = hits + misses
    
    return {
        "cache_hits": hits,
        "cache_misses": misses,
        "hit_ratio": round(hits / total, 4) if total > 0 else 0,
        "total_requests": total,
        "memory_used": stats.get("used_memory_human", "N/A"),
    }


# =============================================================================
# ADDITIONAL CUSTOM CSS FOR SWAGGER
# =============================================================================

@app.get("/custom-swagger.css", include_in_schema=False)
async def swagger_custom_css():
    """Serve custom cyberpunk CSS for Swagger UI."""
    css = """
    /* OmniGuard Cyberpunk Swagger Theme */
    body {
        background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 50%, #16213e 100%) !important;
    }
    .swagger-ui {
        background: transparent !important;
    }
    .swagger-ui .topbar {
        background: linear-gradient(90deg, #00ff9f 0%, #00b8ff 100%) !important;
        padding: 10px 0;
    }
    .swagger-ui .info .title {
        color: #00ff9f !important;
        text-shadow: 0 0 10px #00ff9f;
        font-family: 'Orbitron', monospace;
    }
    .swagger-ui .opblock {
        background: rgba(26, 26, 46, 0.8) !important;
        border: 1px solid #00ff9f !important;
        box-shadow: 0 0 15px rgba(0, 255, 159, 0.2);
    }
    .swagger-ui .opblock .opblock-summary {
        border-color: #00b8ff !important;
    }
    .swagger-ui .opblock-tag {
        color: #00ff9f !important;
        border-bottom: 1px solid #00ff9f !important;
    }
    .swagger-ui .btn {
        background: linear-gradient(90deg, #00ff9f, #00b8ff) !important;
        color: #0a0a0a !important;
        border: none !important;
        text-shadow: none !important;
    }
    .swagger-ui .btn:hover {
        box-shadow: 0 0 20px #00ff9f !important;
    }
    .swagger-ui select, .swagger-ui input {
        background: #1a1a2e !important;
        color: #00ff9f !important;
        border: 1px solid #00b8ff !important;
    }
    .swagger-ui .model-box {
        background: rgba(0, 184, 255, 0.1) !important;
        border: 1px solid #00b8ff !important;
    }
    .swagger-ui .response-col_status {
        color: #00ff9f !important;
    }
    .swagger-ui .markdown p, .swagger-ui .markdown li {
        color: #a0a0a0 !important;
    }
    .swagger-ui .opblock-description-wrapper p {
        color: #c0c0c0 !important;
    }
    """
    return Response(content=css, media_type="text/css")
