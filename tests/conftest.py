"""
OmniGuard Test Configuration
Pytest fixtures and configuration
"""
import pytest
import os
import sys

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Set test environment variables BEFORE any imports
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = "6379"
os.environ["ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "true"
os.environ["TESTING"] = "true"  # Enables test mode in lifespan


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use default event loop policy for async tests."""
    import asyncio
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture(autouse=True)
def reset_metrics():
    """Reset Prometheus metrics between tests."""
    yield
    # Metrics reset handled automatically by test isolation


@pytest.fixture
def sample_post_data():
    """Sample post data for testing."""
    return {
        "id": 1,
        "userId": 1,
        "title": "Test Post Title",
        "body": "This is a test post body content."
    }


@pytest.fixture
def sample_upstream_response():
    """Sample upstream API response."""
    return {
        "source": "upstream",
        "endpoint": "/posts",
        "data": [
            {"id": 1, "userId": 1, "title": "Post 1", "body": "Body 1"},
            {"id": 2, "userId": 1, "title": "Post 2", "body": "Body 2"},
        ],
        "total_items": 2
    }


@pytest.fixture
def sample_cached_response():
    """Sample cached response."""
    return {
        "source": "cache",
        "endpoint": "/posts",
        "data": [{"id": 1, "title": "Cached Post"}],
        "total_items": 1
    }
