"""
OmniGuard Upstream API Module
Handles communication with the upstream/backend API services
"""
import httpx
import logging
from typing import Optional, Any
import asyncio
from functools import wraps

from app.config import get_settings

logger = logging.getLogger(__name__)

# Global HTTP client
_http_client: Optional[httpx.AsyncClient] = None


async def init_http_client() -> None:
    """Initialize async HTTP client with connection pooling."""
    global _http_client
    settings = get_settings()
    
    _http_client = httpx.AsyncClient(
        base_url=settings.upstream_url,
        timeout=httpx.Timeout(
            connect=5.0,
            read=settings.upstream_timeout,
            write=10.0,
            pool=5.0
        ),
        limits=httpx.Limits(
            max_connections=100,
            max_keepalive_connections=20,
            keepalive_expiry=30
        ),
        headers={
            "User-Agent": f"OmniGuard/{settings.app_version}",
            "Accept": "application/json",
        }
    )
    logger.info("HTTP client initialized successfully")


async def close_http_client() -> None:
    """Close HTTP client."""
    global _http_client
    if _http_client:
        await _http_client.aclose()
        _http_client = None
    logger.info("HTTP client closed")


def get_http_client() -> httpx.AsyncClient:
    """Get HTTP client instance."""
    if _http_client is None:
        raise RuntimeError("HTTP client not initialized. Call init_http_client() first.")
    return _http_client


class UpstreamError(Exception):
    """Custom exception for upstream API errors."""
    
    def __init__(self, message: str, status_code: int = 500, details: Any = None):
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)


def retry_with_backoff(max_retries: int = 3, base_delay: float = 0.5):
    """Decorator for retrying failed requests with exponential backoff."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except (httpx.TimeoutException, httpx.ConnectError) as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(
                            f"Upstream request failed (attempt {attempt + 1}/{max_retries}), "
                            f"retrying in {delay}s: {e}"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"All {max_retries} retry attempts failed: {e}")
                        
            raise UpstreamError(
                message="Upstream service unavailable after retries",
                status_code=503,
                details=str(last_exception)
            )
        return wrapper
    return decorator


class UpstreamClient:
    """Client for interacting with upstream API services."""
    
    def __init__(self):
        self.settings = get_settings()
    
    @retry_with_backoff(max_retries=3)
    async def fetch_data(self, endpoint: str = "/posts") -> dict:
        """
        Fetch data from upstream API.
        
        Args:
            endpoint: API endpoint to fetch from
            
        Returns:
            JSON response data
            
        Raises:
            UpstreamError: If request fails
        """
        client = get_http_client()
        
        try:
            logger.info(f"Fetching data from upstream: {endpoint}")
            response = await client.get(endpoint)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Successfully fetched data from upstream: {endpoint}")
            
            return {
                "source": "upstream",
                "endpoint": endpoint,
                "data": data[:10] if isinstance(data, list) else data,  # Limit list results
                "total_items": len(data) if isinstance(data, list) else 1,
            }
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Upstream HTTP error: {e.response.status_code}")
            raise UpstreamError(
                message=f"Upstream returned error: {e.response.status_code}",
                status_code=e.response.status_code,
                details=e.response.text[:500] if e.response.text else None
            )
        except httpx.RequestError as e:
            logger.error(f"Upstream request error: {e}")
            raise UpstreamError(
                message="Failed to connect to upstream service",
                status_code=502,
                details=str(e)
            )
    
    @retry_with_backoff(max_retries=3)
    async def fetch_post(self, post_id: int) -> dict:
        """Fetch a single post by ID."""
        client = get_http_client()
        
        try:
            response = await client.get(f"/posts/{post_id}")
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise UpstreamError(
                    message=f"Post {post_id} not found",
                    status_code=404
                )
            raise UpstreamError(
                message=f"Upstream error: {e.response.status_code}",
                status_code=e.response.status_code
            )
    
    @retry_with_backoff(max_retries=2)
    async def fetch_users(self) -> list:
        """Fetch users list."""
        client = get_http_client()
        response = await client.get("/users")
        response.raise_for_status()
        return response.json()
    
    async def health_check(self) -> dict:
        """Check upstream API health."""
        try:
            client = get_http_client()
            response = await client.get("/posts/1")
            return {
                "status": "healthy" if response.status_code == 200 else "degraded",
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "status_code": response.status_code,
            }
        except Exception as e:
            logger.error(f"Upstream health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
            }


# Singleton instance
upstream_client = UpstreamClient()
