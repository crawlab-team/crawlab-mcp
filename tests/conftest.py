import logging
import os
from unittest.mock import patch

import pytest

# Configure pytest-asyncio globally
pytest_plugins = ["pytest_asyncio"]

@pytest.fixture(autouse=True)
def disable_logging():
    """Disable logging output during tests."""
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)


@pytest.fixture
def setup_environment():
    """Set up environment variables for testing."""
    # Save original environment variables
    original_env = {}
    for key in [
        "CRAWLAB_API_BASE_URL",
        "CRAWLAB_API_TOKEN",
        "CRAWLAB_USERNAME",
        "CRAWLAB_PASSWORD",
    ]:
        original_env[key] = os.environ.get(key)

    # Set test environment variables
    os.environ["CRAWLAB_API_BASE_URL"] = "http://test.crawlab.org/api"
    os.environ["CRAWLAB_API_TOKEN"] = "test_token"
    os.environ["CRAWLAB_USERNAME"] = "test_user"
    os.environ["CRAWLAB_PASSWORD"] = "test_password"

    yield

    # Restore original environment variables
    for key, value in original_env.items():
        if value is None:
            if key in os.environ:
                del os.environ[key]
        else:
            os.environ[key] = value


@pytest.fixture
def mock_api_request():
    """Mock the api_request function to simulate API calls."""
    with patch("crawlab_mcp.utils.http.api_request") as mock_request:
        # Set up the mock to return a success response
        mock_request.return_value = {"data": {"success": True}}
        yield mock_request


@pytest.fixture
def mock_get_api_token():
    """Mock the get_api_token function to return a test token."""
    with patch("crawlab_mcp.utils.http.get_api_token") as mock_get_token:
        mock_get_token.return_value = "test_token"
        yield mock_get_token


@pytest.fixture
def mock_tools_logger():
    """Mock tools logger."""
    with patch("crawlab_mcp.utils.tools.tools_logger") as mock_logger:
        yield mock_logger
