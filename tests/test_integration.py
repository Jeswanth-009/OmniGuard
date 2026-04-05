"""
OmniGuard Integration Tests
End-to-end tests for the complete system
"""
import pytest
import os
import asyncio
import uuid
from unittest.mock import AsyncMock, patch, MagicMock

# Set test environment BEFORE any app imports
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = "6379"
os.environ["ENVIRONMENT"] = "test"
os.environ["TESTING"] = "true"

from httpx import AsyncClient, ASGITransport
import fakeredis.aioredis


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def unique_test_id():
    """Generate unique test ID for cache key isolation."""
    return str(uuid.uuid4())[:8]


class TestFullRequestCycle:
    """Integration tests for complete request cycles."""
    
    @pytest.fixture
    def fake_redis(self):
        """Create fresh fake Redis for testing (ensures isolation)."""
        return fakeredis.aioredis.FakeRedis(decode_responses=True)
    
    @pytest.fixture
    async def clean_fake_redis(self, fake_redis):
        """Provide a clean fake Redis, flushed before each test."""
        await fake_redis.flushall()
        yield fake_redis
        await fake_redis.flushall()
    
    @pytest.mark.asyncio
    async def test_full_cache_cycle(self, clean_fake_redis, unique_test_id):
        """Test complete cache miss -> store -> hit cycle."""
        with patch('app.cache._client', clean_fake_redis):
            with patch('app.cache._pool', MagicMock()):
                from app.main import app
                
                transport = ASGITransport(app=app)
                
                # Use unique endpoint to avoid cross-test cache pollution
                unique_endpoint = f"/posts-{unique_test_id}"
                
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    # Mock upstream for first request (cache miss)
                    with patch('app.upstream.upstream_client.fetch_data', new_callable=AsyncMock) as mock_fetch:
                        mock_fetch.return_value = {
                            "source": "upstream",
                            "endpoint": unique_endpoint,
                            "data": [{"id": 1, "title": "Test Post"}],
                            "total_items": 1
                        }
                        
                        # First request should be cache MISS
                        response1 = await client.get(f"/api/data?endpoint={unique_endpoint}")
                        assert response1.status_code == 200
                        assert response1.headers.get("X-Cache") == "MISS"
                        
                        # Verify upstream was called
                        mock_fetch.assert_called_once()
                    
                    # Second request should be cache HIT
                    response2 = await client.get(f"/api/data?endpoint={unique_endpoint}")
                    assert response2.status_code == 200
                    assert response2.headers.get("X-Cache") == "HIT"
    
    @pytest.mark.asyncio
    async def test_health_check_integration(self, clean_fake_redis):
        """Test health check with real Redis mock."""
        with patch('app.cache._client', clean_fake_redis):
            with patch('app.cache._pool', MagicMock()):
                with patch('app.upstream.upstream_client.health_check', new_callable=AsyncMock) as mock_upstream:
                    mock_upstream.return_value = {"status": "healthy", "response_time_ms": 25}
                    
                    from app.main import app
                    
                    transport = ASGITransport(app=app)
                    
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        response = await client.get("/health")
                        
                        assert response.status_code == 200
                        data = response.json()
                        assert data["status"] in ["healthy", "degraded", "unhealthy"]
                        assert "redis" in data
                        assert "upstream" in data
                        assert "uptime_seconds" in data
    
    @pytest.mark.asyncio
    async def test_metrics_contain_all_required_metrics(self, clean_fake_redis):
        """Test that metrics endpoint includes all required Prometheus metrics."""
        with patch('app.cache._client', clean_fake_redis):
            with patch('app.cache._pool', MagicMock()):
                from app.main import app
                
                transport = ASGITransport(app=app)
                
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/metrics")
                    
                    assert response.status_code == 200
                    content = response.text
                    
                    # Verify all required metrics are present
                    required_metrics = [
                        "omniguard_requests_total",
                        "omniguard_request_latency_seconds",
                        "omniguard_errors_total",
                        "omniguard_cache_hits_total",
                        "omniguard_cache_misses_total",
                        "omniguard_uptime_seconds",
                    ]
                    
                    for metric in required_metrics:
                        assert metric in content, f"Missing metric: {metric}"


class TestLoadBalancingSimulation:
    """Test load balancing behavior simulation."""
    
    @pytest.fixture
    def fake_redis(self):
        return fakeredis.aioredis.FakeRedis(decode_responses=True)
    
    @pytest.fixture
    async def clean_fake_redis(self, fake_redis):
        """Provide a clean fake Redis, flushed before each test."""
        await fake_redis.flushall()
        yield fake_redis
        await fake_redis.flushall()
    
    @pytest.mark.asyncio
    async def test_multiple_concurrent_requests(self, clean_fake_redis, unique_test_id):
        """Test handling multiple concurrent requests."""
        with patch('app.cache._client', clean_fake_redis):
            with patch('app.cache._pool', MagicMock()):
                with patch('app.upstream.upstream_client.fetch_data', new_callable=AsyncMock) as mock_fetch:
                    # Use unique endpoint for test isolation
                    unique_endpoint = f"/posts-concurrent-{unique_test_id}"
                    mock_fetch.return_value = {
                        "source": "upstream",
                        "endpoint": unique_endpoint,
                        "data": [{"id": 1}],
                        "total_items": 1
                    }
                    
                    from app.main import app
                    
                    transport = ASGITransport(app=app)
                    
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        # Send 10 concurrent requests
                        tasks = [
                            client.get(f"/api/data?endpoint={unique_endpoint}")
                            for _ in range(10)
                        ]
                        responses = await asyncio.gather(*tasks)
                        
                        # All should succeed
                        for resp in responses:
                            assert resp.status_code == 200
                        
                        # First request causes cache miss, rest should be hits
                        cache_misses = sum(1 for r in responses if r.headers.get("X-Cache") == "MISS")
                        cache_hits = sum(1 for r in responses if r.headers.get("X-Cache") == "HIT")
                        
                        # Due to concurrency, multiple misses are possible
                        assert cache_misses >= 1
                        assert cache_hits + cache_misses == 10


class TestResiliency:
    """Test system resilience to failures."""
    
    @pytest.fixture
    def fake_redis(self):
        return fakeredis.aioredis.FakeRedis(decode_responses=True)
    
    @pytest.fixture
    async def clean_fake_redis(self, fake_redis):
        """Provide a clean fake Redis, flushed before each test."""
        await fake_redis.flushall()
        yield fake_redis
        await fake_redis.flushall()
    
    @pytest.mark.asyncio
    async def test_upstream_failure_handling(self, clean_fake_redis, unique_test_id):
        """Test handling of upstream API failures."""
        from app.upstream import UpstreamError
        
        with patch('app.cache._client', clean_fake_redis):
            with patch('app.cache._pool', MagicMock()):
                with patch('app.upstream.upstream_client.fetch_data', new_callable=AsyncMock) as mock_fetch:
                    mock_fetch.side_effect = UpstreamError("Connection refused", 502)
                    
                    from app.main import app
                    
                    transport = ASGITransport(app=app)
                    
                    # Use unique endpoint
                    unique_endpoint = f"/posts-fail-{unique_test_id}"
                    
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        response = await client.get(f"/api/data?endpoint={unique_endpoint}")
                        
                        # Should return error, not crash
                        assert response.status_code == 502
                        data = response.json()
                        assert "error" in data or "code" in data
    
    @pytest.mark.asyncio
    async def test_malformed_input_handling(self, clean_fake_redis):
        """Test handling of malformed input."""
        with patch('app.cache._client', clean_fake_redis):
            with patch('app.cache._pool', MagicMock()):
                from app.main import app
                
                transport = ASGITransport(app=app)
                
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    # Test invalid JSON body
                    response = await client.post(
                        "/api/data",
                        content="not valid json",
                        headers={"Content-Type": "application/json"}
                    )
                    
                    assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_cache_clear_endpoint(self, clean_fake_redis):
        """Test cache clearing functionality."""
        with patch('app.cache._client', clean_fake_redis):
            with patch('app.cache._pool', MagicMock()):
                from app.main import app
                
                transport = ASGITransport(app=app)
                
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.delete("/api/cache")
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert "success" in data


class TestDocumentation:
    """Test API documentation endpoints."""
    
    @pytest.fixture
    def fake_redis(self):
        return fakeredis.aioredis.FakeRedis(decode_responses=True)
    
    @pytest.mark.asyncio
    async def test_swagger_docs_available(self, fake_redis):
        """Test Swagger documentation is accessible."""
        with patch('app.cache._client', fake_redis):
            with patch('app.cache._pool', MagicMock()):
                from app.main import app
                
                transport = ASGITransport(app=app)
                
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/docs")
                    
                    assert response.status_code == 200
                    assert "text/html" in response.headers.get("content-type", "")
    
    @pytest.mark.asyncio
    async def test_openapi_schema_available(self, fake_redis):
        """Test OpenAPI schema is accessible."""
        with patch('app.cache._client', fake_redis):
            with patch('app.cache._pool', MagicMock()):
                from app.main import app
                
                transport = ASGITransport(app=app)
                
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/openapi.json")
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert "openapi" in data
                    assert "paths" in data
                    assert "/health" in data["paths"]
                    assert "/api/data" in data["paths"]
    
    @pytest.mark.asyncio
    async def test_redoc_available(self, fake_redis):
        """Test ReDoc documentation is accessible."""
        with patch('app.cache._client', fake_redis):
            with patch('app.cache._pool', MagicMock()):
                from app.main import app
                
                transport = ASGITransport(app=app)
                
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get("/redoc")
                    
                    assert response.status_code == 200
