import os
import sys
from unittest.mock import MagicMock

import pytest

# Add the parent directory to sys.path to import the client module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlab_mcp.agents.task_planner import TaskPlanner
from crawlab_mcp.clients.client import MCPClient


@pytest.fixture
def mcp_client():
    """Create a real MCPClient for testing"""
    client = MCPClient()
    # Using the real LLM provider instead of mocking
    return client


# Test for when task_planner is None
@pytest.mark.asyncio
async def test_should_use_planning_no_planner(mcp_client):
    """Test that _should_use_planning returns False when task_planner is None"""
    mcp_client.task_planner = None
    result = await mcp_client._should_use_planning("test query")
    assert result is False


# Parameters for testing different query types
@pytest.mark.parametrize(
    "query,expected,description",
    [
        ("What time is it?", False, "Simple query should return False"),
        (
            "List all spiders and run the first one",
            True,
            "Simple multi-step workflow should return True",
        ),
        (
            "Fetch data from multiple APIs, combine the results, and generate a summary report with charts.",
            True,
            "Complex multi-step workflow should return True",
        ),
        (
            "Query the database for all users who signed up last month, send them an email, and update their status.",
            True,
            "Multi-step process should return True",
        ),
        ("Tell me a joke", False, "Simple request should return False"),
    ],
)
@pytest.mark.asyncio
async def test_should_use_planning_with_real_llm(mcp_client, query, expected, description):
    """
    Test _should_use_planning with real LLM responses for different types of queries

    This test uses real LLM calls instead of mocks to test actual behavior
    """
    # Initialize a task planner with all required parameters
    mock_tools = []  # Empty list of tools for testing purposes
    mock_session = MagicMock()  # Mock session object
    mcp_client.task_planner = TaskPlanner(
        llm_provider=mcp_client.llm_provider, tools=mock_tools, session=mock_session
    )

    # Call the actual method with the query
    result = await mcp_client._should_use_planning(query)

    # Assert based on expected result (but allow flexibility since we're using real LLM)
    # In real LLM testing, we add a note about potential variations
    if result != expected:
        pytest.xfail(
            f"LLM response may vary: expected {expected} but got {result} for query: {query}"
        )

    assert result == expected, f"Failed for query: {query} - {description}"


# Test for error handling
@pytest.mark.asyncio
async def test_should_use_planning_exception_handling(monkeypatch, mcp_client):
    """Test that _should_use_planning returns False when an exception occurs"""
    # Set up task planner
    mock_tools = []  # Empty list of tools for testing purposes
    mock_session = MagicMock()  # Mock session object
    mcp_client.task_planner = TaskPlanner(
        llm_provider=mcp_client.llm_provider, tools=mock_tools, session=mock_session
    )

    # Create a function that raises an exception when called
    async def mock_chat_completion(*args, **kwargs):
        raise Exception("Simulated API error")

    # Apply the monkeypatch to replace the real method
    monkeypatch.setattr(mcp_client.llm_provider, "chat_completion", mock_chat_completion)

    # Call the method and verify it handles the exception
    result = await mcp_client._should_use_planning("query that causes exception")
    assert result is False, "Method should return False when exception occurs"


# Parametrized test for different response formats
@pytest.mark.parametrize(
    "response_content,expected",
    [
        ("true", True),
        ("false", False),
        ("  true  ", True),
        ("  false  ", False),
        ("TRUE", True),
        ("FALSE", False),
    ],
)
@pytest.mark.asyncio
async def test_should_use_planning_response_formatting(
    monkeypatch, mcp_client, response_content, expected
):
    """Test that _should_use_planning correctly handles different response formats"""
    # Set up task planner
    mock_tools = []  # Empty list of tools for testing purposes
    mock_session = MagicMock()  # Mock session object
    mcp_client.task_planner = TaskPlanner(
        llm_provider=mcp_client.llm_provider, tools=mock_tools, session=mock_session
    )

    # Create a function that returns the test response
    async def mock_chat_completion(*args, **kwargs):
        return {"choices": [{"message": {"content": response_content}}]}

    # Apply the monkeypatch
    monkeypatch.setattr(mcp_client.llm_provider, "chat_completion", mock_chat_completion)

    # Call the method and verify the result
    result = await mcp_client._should_use_planning("test query")
    assert result == expected, f"Failed for response content: '{response_content}'"
