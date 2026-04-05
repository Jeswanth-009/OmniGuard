"""
OmniGuard Redis Cache Module
High-performance caching layer with connection pooling and health checks
"""
import redis.asyncio as redis
from redis.asyncio import ConnectionPool, Redis
from typing import Optional, Any
import json
import logging
from contextlib import asynccontextmanager

from app.config import get_settings

logger = logging.getLogger(__name__)

# Global connection pool
_pool: Optional[ConnectionPool] = None
_client: Optional[Redis] = None


async def init_redis_pool() -> None:
    """Initialize Redis connection pool."""
    global _pool, _client
    settings = get_settings()
    
    try:
        _pool = ConnectionPool(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password,
            decode_responses=True,
            max_connections=20,
            socket_timeout=settings.redis_timeout,
            socket_connect_timeout=settings.redis_timeout,
            retry_on_timeout=True,
        )
        _client = Redis(connection_pool=_pool)
        
        # Test connection
        await _client.ping()
        logger.info("Redis connection pool initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Redis pool: {e}")
        raise


async def close_redis_pool() -> None:
    """Close Redis connection pool."""
    global _pool, _client
    if _client:
        await _client.close()
        _client = None
    if _pool:
        await _pool.disconnect()
        _pool = None
    logger.info("Redis connection pool closed")


def get_redis_client() -> Redis:
    """Get Redis client instance."""
    if _client is None:
        raise RuntimeError("Redis client not initialized. Call init_redis_pool() first.")
    return _client


async def check_redis_health() -> dict:
    """Check Redis connection health."""
    try:
        client = get_redis_client()
        await client.ping()
        info = await client.info("server")
        return {
            "status": "healthy",
            "connected": True,
            "redis_version": info.get("redis_version", "unknown"),
        }
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(e),
        }


class CacheManager:
    """Redis cache manager with automatic serialization."""
    
    def __init__(self):
        self.settings = get_settings()
        self.prefix = self.settings.cache_prefix
        self.default_ttl = self.settings.cache_ttl
    
    def _make_key(self, key: str) -> str:
        """Create prefixed cache key."""
        return f"{self.prefix}{key}"
    
    async def get(self, key: str) -> tuple[Optional[Any], bool]:
        """
        Get value from cache.
        
        Returns:
            Tuple of (value, is_hit) where is_hit indicates cache hit/miss
        """
        try:
            client = get_redis_client()
            full_key = self._make_key(key)
            value = await client.get(full_key)
            
            if value is not None:
                logger.debug(f"Cache HIT for key: {key}")
                return json.loads(value), True
            
            logger.debug(f"Cache MISS for key: {key}")
            return None, False
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to decode cached value for {key}: {e}")
            return None, False
        except Exception as e:
            logger.error(f"Cache get error for {key}: {e}")
            return None, False
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache with TTL.
        
        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time-to-live in seconds (defaults to config value)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            client = get_redis_client()
            full_key = self._make_key(key)
            ttl = ttl or self.default_ttl
            
            serialized = json.dumps(value)
            await client.setex(full_key, ttl, serialized)
            
            logger.debug(f"Cache SET for key: {key} with TTL: {ttl}s")
            return True
            
        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        try:
            client = get_redis_client()
            full_key = self._make_key(key)
            await client.delete(full_key)
            logger.debug(f"Cache DELETE for key: {key}")
            return True
        except Exception as e:
            logger.error(f"Cache delete error for {key}: {e}")
            return False
    
    async def get_stats(self) -> dict:
        """Get cache statistics."""
        try:
            client = get_redis_client()
            info = await client.info("stats")
            memory = await client.info("memory")
            
            return {
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "total_commands": info.get("total_commands_processed", 0),
                "used_memory_human": memory.get("used_memory_human", "N/A"),
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {}


# Singleton instance
cache_manager = CacheManager()
