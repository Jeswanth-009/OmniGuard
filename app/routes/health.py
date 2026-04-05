"""OmniGuard routes with legacy-compatible API responses."""

from datetime import datetime, timezone
import json
import os
import socket
from threading import Lock
import time
from urllib import error as urllib_error
from urllib import request as urllib_request

from flask import Blueprint, Response, jsonify, redirect, render_template, request

from app.csv_data import CsvDatasetNotFound, csv_store
from app.database import db

health_bp = Blueprint("health", __name__)

APP_NAME = os.getenv("APP_NAME", "OmniGuard")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
UPSTREAM_URL = os.getenv("UPSTREAM_URL", "https://jsonplaceholder.typicode.com").rstrip("/")
CACHE_TTL = max(1, int(os.getenv("CACHE_TTL", "60")))
APP_START_TIME = time.time()

_cache_lock = Lock()
_cache_store: dict[str, dict[str, object]] = {}
_cache_hits = 0
_cache_misses = 0


def _external_service_url(env_name: str, default_port: int) -> str:
    configured = os.getenv(env_name, "").strip()
    if configured:
        return configured

    host = request.host.split(":", 1)[0]
    return f"http://{host}:{default_port}"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _request_id() -> str | None:
    return request.headers.get("X-Request-ID")


def _error_response(status_code: int, code: str, message: str, details: object = None):
    return (
        jsonify(
            {
                "error": True,
                "code": code,
                "message": message,
                "details": details,
                "timestamp": _iso_now(),
                "request_id": _request_id(),
            }
        ),
        status_code,
    )


def _db_health() -> dict[str, object]:
    try:
        db.execute_sql("SELECT 1")
        return {"status": "healthy", "connected": True}
    except Exception as exc:
        return {"status": "unhealthy", "connected": False, "error": str(exc)}


def _upstream_health() -> dict[str, object]:
    try:
        start = time.time()
        with urllib_request.urlopen(f"{UPSTREAM_URL}/posts/1", timeout=5) as response:
            status_code = getattr(response, "status", 200)
        elapsed_ms = (time.time() - start) * 1000
        return {
            "status": "healthy" if status_code == 200 else "degraded",
            "response_time_ms": round(elapsed_ms, 2),
            "status_code": status_code,
        }
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)}


def _cache_get(cache_key: str):
    with _cache_lock:
        entry = _cache_store.get(cache_key)
        if not entry:
            return None, None

        expires_at = float(entry["expires_at"])
        if expires_at <= time.time():
            del _cache_store[cache_key]
            return None, None

        ttl_remaining = max(0, int(expires_at - time.time()))
        return entry["data"], ttl_remaining


def _cache_set(cache_key: str, data: object, ttl: int) -> None:
    with _cache_lock:
        _cache_store[cache_key] = {
            "data": data,
            "expires_at": time.time() + ttl,
        }


def _make_data_response(payload: dict, cache_status: str, start_time: float, status_code: int = 200):
    response = jsonify(payload)
    response.status_code = status_code
    response.headers["X-Cache"] = cache_status
    response.headers["X-Response-Time"] = f"{(time.time() - start_time):.3f}s"
    response.headers["X-Served-By"] = socket.gethostname()
    return response


def _resolve_csv_dataset(dataset: str | None, endpoint: str) -> str:
    if dataset:
        return dataset.lower().strip()

    guessed = endpoint.lstrip("/").lower().strip()
    if guessed in {"users", "urls", "events"}:
        return guessed

    raise CsvDatasetNotFound(
        "For CSV source provide dataset=users|urls|events or endpoint=/users|/urls|/events"
    )


def _fetch_upstream_data(endpoint: str) -> dict:
    safe_endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"

    with urllib_request.urlopen(f"{UPSTREAM_URL}{safe_endpoint}", timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))

    normalized = payload[:10] if isinstance(payload, list) else payload
    total_items = len(payload) if isinstance(payload, list) else 1
    return {
        "source": "upstream",
        "endpoint": safe_endpoint,
        "data": normalized,
        "total_items": total_items,
    }


def _to_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _handle_data_request(
    source: str,
    endpoint: str,
    dataset: str | None,
    limit: int,
    offset: int,
    force_refresh: bool,
):
    global _cache_hits, _cache_misses

    start_time = time.time()
    selected_source = source.lower().strip()
    bounded_limit = max(1, min(limit, 1000))
    bounded_offset = max(0, offset)

    if not endpoint.startswith("/"):
        return _error_response(422, "HTTP_422", "Endpoint must start with '/'")
    if ".." in endpoint:
        return _error_response(422, "HTTP_422", "Invalid endpoint path")
    if selected_source not in {"upstream", "csv"}:
        return _error_response(422, "HTTP_422", "Invalid source. Use 'upstream' or 'csv'.")

    cache_key = f"data:{selected_source}:{endpoint}:{dataset or ''}:{bounded_limit}:{bounded_offset}"

    if not force_refresh:
        cached_data, _ttl_remaining = _cache_get(cache_key)
        if cached_data is not None:
            with _cache_lock:
                _cache_hits += 1

            return _make_data_response(
                {
                    "success": True,
                    "cached": True,
                    "data": cached_data,
                    "meta": {
                        "source": "cache",
                        "selected_source": selected_source,
                        "endpoint": endpoint,
                        "dataset": dataset,
                    },
                },
                cache_status="HIT",
                start_time=start_time,
            )

    with _cache_lock:
        _cache_misses += 1

    try:
        if selected_source == "csv":
            selected_dataset = _resolve_csv_dataset(dataset, endpoint)
            data = csv_store.get_dataset(
                dataset=selected_dataset,
                limit=bounded_limit,
                offset=bounded_offset,
            )
        else:
            data = _fetch_upstream_data(endpoint)
    except CsvDatasetNotFound as exc:
        return _error_response(404, "HTTP_404", str(exc))
    except urllib_error.HTTPError as exc:
        return _error_response(502, "UPSTREAM_ERROR", f"Upstream returned error: {exc.code}", str(exc))
    except Exception as exc:
        return _error_response(502, "UPSTREAM_ERROR", "Failed to fetch upstream data", str(exc))

    _cache_set(cache_key, data, CACHE_TTL)

    return _make_data_response(
        {
            "success": True,
            "cached": False,
            "ttl_remaining": CACHE_TTL,
            "data": data,
            "meta": {
                "source": selected_source,
                "endpoint": endpoint,
                "dataset": dataset,
                "cached_at": _iso_now(),
            },
        },
        cache_status="MISS",
        start_time=start_time,
    )


@health_bp.get("/")
def home():
    """Render the OmniGuard HTML dashboard page."""
    db_health = _db_health()
    upstream_health = _upstream_health()

    return render_template(
        "index.html",
        app_name=APP_NAME,
        version=APP_VERSION,
        uptime=time.time() - APP_START_TIME,
        redis_status="healthy" if db_health.get("connected") else "unhealthy",
        upstream_status=upstream_health.get("status", "unknown"),
        cache_hits=_cache_hits,
        cache_misses=_cache_misses,
        hostname=socket.gethostname(),
        grafana_url=_external_service_url("GRAFANA_URL", 3000),
        prometheus_url=_external_service_url("PROMETHEUS_URL", 9090),
    )


@health_bp.get("/health")
def health():
    """Legacy-compatible health payload."""
    db_health = _db_health()
    upstream_health = _upstream_health()
    overall = "ok"

    return jsonify(
        {
            "status": overall,
            "timestamp": _iso_now(),
            "version": APP_VERSION,
            "redis": db_health,
            "upstream": upstream_health,
            "uptime_seconds": round(time.time() - APP_START_TIME, 2),
        }
    ), 200


@health_bp.get("/docs")
def docs_alias():
    """Simple docs alias for dashboard navigation."""
    return jsonify(
        {
            "service": APP_NAME,
            "message": "Flask docs route placeholder. Refer to README for API usage.",
            "endpoints": [
                "/",
                "/health",
                "/api/data",
                "/api/stats",
                "/api/csv/datasets",
                "/grafana",
                "/prometheus",
            ],
        }
    ), 200


@health_bp.get("/grafana")
def grafana_redirect():
    """Redirect to Grafana UI using configured URL or current host."""
    return redirect(_external_service_url("GRAFANA_URL", 3000), code=302)


@health_bp.get("/prometheus")
def prometheus_redirect():
    """Redirect to Prometheus UI using configured URL or current host."""
    return redirect(_external_service_url("PROMETHEUS_URL", 9090), code=302)


@health_bp.get("/metrics")
def metrics():
    """Basic Prometheus-style metrics for dashboard navigation compatibility."""
    total_requests = _cache_hits + _cache_misses
    metrics_text = (
        "# HELP omniguard_cache_hits_total Total cache hits\n"
        "# TYPE omniguard_cache_hits_total counter\n"
        f"omniguard_cache_hits_total {_cache_hits}\n"
        "# HELP omniguard_cache_misses_total Total cache misses\n"
        "# TYPE omniguard_cache_misses_total counter\n"
        f"omniguard_cache_misses_total {_cache_misses}\n"
        "# HELP omniguard_requests_total Total requests tracked by cache layer\n"
        "# TYPE omniguard_requests_total counter\n"
        f"omniguard_requests_total {total_requests}\n"
    )
    return Response(metrics_text, mimetype="text/plain; version=0.0.4")


@health_bp.get("/api/csv/datasets")
def list_csv_datasets():
    """List available CSV datasets."""
    return jsonify(
        {
            "source": "csv",
            "data_dir": str(csv_store.data_dir),
            "datasets": csv_store.available_datasets(),
        }
    ), 200


@health_bp.get("/api/csv/<dataset>")
def get_csv_dataset(dataset: str):
    """Fetch CSV rows for a named dataset."""
    limit = request.args.get("limit", default=100, type=int)
    offset = request.args.get("offset", default=0, type=int)

    try:
        data = csv_store.get_dataset(dataset=dataset, limit=limit, offset=offset)
    except CsvDatasetNotFound as exc:
        return _error_response(404, "HTTP_404", str(exc))

    return jsonify(
        {
            "success": True,
            "cached": False,
            "data": data,
            "meta": {
                "source": "csv",
                "dataset": dataset,
                "limit": max(1, min(limit, 1000)),
                "offset": max(0, offset),
            },
        }
    ), 200


@health_bp.get("/api/data")
def get_data():
    """Legacy-compatible GET /api/data endpoint."""
    source = request.args.get("source", default="upstream", type=str)
    endpoint = request.args.get("endpoint", default="/posts", type=str)
    dataset = request.args.get("dataset", default=None, type=str)
    limit = request.args.get("limit", default=100, type=int)
    offset = request.args.get("offset", default=0, type=int)
    force_refresh = _to_bool(request.args.get("force_refresh", default=False))

    return _handle_data_request(source, endpoint, dataset, limit, offset, force_refresh)


@health_bp.post("/api/data")
def post_data():
    """Legacy-compatible POST /api/data endpoint."""
    payload = request.get_json(silent=True)
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        return _error_response(422, "HTTP_422", "Invalid JSON body")

    source = str(payload.get("source", "upstream"))
    endpoint = str(payload.get("endpoint", "/posts"))
    dataset = payload.get("dataset")
    dataset = str(dataset) if dataset is not None else None
    limit = _to_int(payload.get("limit", 100), 100)
    offset = _to_int(payload.get("offset", 0), 0)
    force_refresh = _to_bool(payload.get("force_refresh", False))

    return _handle_data_request(source, endpoint, dataset, limit, offset, force_refresh)


@health_bp.get("/api/stats")
def stats():
    """Legacy-compatible cache stats response."""
    total = _cache_hits + _cache_misses
    hit_ratio = round((_cache_hits / total), 4) if total > 0 else 0

    return jsonify(
        {
            "cache_hits": _cache_hits,
            "cache_misses": _cache_misses,
            "hit_ratio": hit_ratio,
            "total_requests": total,
            "memory_used": "N/A",
        }
    ), 200
