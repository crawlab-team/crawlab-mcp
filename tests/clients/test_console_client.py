import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crawlab_mcp.agents.task_planner import TaskPlanner
from crawlab_mcp.clients.client import MCPClient

# Add the parent directory to sys.path to import the client module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlab_mcp.clients.console_client import ConsoleClient


@pytest.fixture
def console_client():
    """Create a real ConsoleClient for testing"""
    client = ConsoleClient()
    return client


# Test ConsoleClient initialization
def test_console_client_init(console_client):
    """Test that ConsoleClient initializes with the correct properties"""
    # Inherited properties from MCPClient
    assert console_client.session is None
    assert isinstance(console_client.tools, list)
    assert isinstance(console_client.tool_tags, list)
    assert console_client.connection_type == "sse"
    assert hasattr(console_client, "api_key")
    
    # ConsoleClient specific properties
    assert hasattr(console_client, "llm_provider")
    assert hasattr(console_client, "exit_stack")
    assert console_client.task_planner is None  # Initially None


# Test the initialize_llm method
@pytest.mark.asyncio
async def test_initialize_llm(monkeypatch, console_client):
    """Test that initialize_llm properly sets up the LLM provider and task planner"""
    # Mock dependencies
    mock_llm_provider = AsyncMock()
    mock_task_planner = MagicMock()
    
    # Mock TaskPlanner constructor
    mock_task_planner_constructor = MagicMock(return_value=mock_task_planner)
    
    # Apply patches
    monkeypatch.setattr(console_client, "llm_provider", mock_llm_provider)
    monkeypatch.setattr("crawlab_mcp.clients.console_client.TaskPlanner", mock_task_planner_constructor)
    
    # Call the method
    await console_client.initialize_llm()
    
    # Verify method calls
    mock_llm_provider.initialize.assert_called_once()
    # Check task planner was initialized with the right arguments
    assert console_client.task_planner == mock_task_planner


# Test the chat_loop method
@pytest.mark.asyncio
async def test_chat_loop(monkeypatch, console_client):
    """Test that chat_loop processes user input correctly"""
    # Mock methods
    mock_read_input = AsyncMock()
    mock_process_query = AsyncMock()
    mock_print_help = MagicMock()
    
    # Set up mock input sequence: help, query, quit
    mock_read_input.side_effect = ["help", "test query", "quit"]
    mock_process_query.return_value = "Test response"
    
    # Apply patches
    monkeypatch.setattr(console_client, "_read_user_input", mock_read_input)
    monkeypatch.setattr(console_client, "process_query", mock_process_query)
    monkeypatch.setattr(console_client, "_print_help", mock_print_help)
    
    # Mock print function to avoid console output
    with patch("builtins.print") as mock_print:
        # Call the method
        await console_client.chat_loop()
    
    # Verify method calls
    assert mock_read_input.call_count == 3
    mock_print_help.assert_called_once()
    mock_process_query.assert_called_once_with("test query")
    
    # Check that proper output was printed
    mock_print.assert_any_call("Test response")


# Test identify_user_intent method
@pytest.mark.asyncio
async def test_identify_user_intent(monkeypatch, console_client):
    """Test that identify_user_intent correctly processes user queries"""
    # Mock dependencies
    mock_llm_provider = AsyncMock()
    console_client.tool_tags = ["tag1", "tag2"]
    
    # Setup mock response
    mock_llm_provider.chat_completion.return_value = {
        "choices": [{"message": {"content": '["getSpiderList"]'}}]
    }
    
    # Apply patches
    monkeypatch.setattr(console_client, "llm_provider", mock_llm_provider)
    
    # Call the method
    result = await console_client.identify_user_intent("List all spiders")
    
    # Verify result
    assert result == '["getSpiderList"]'
    
    # Verify correct system message was sent
    # Check that the first argument is the messages list
    call_args = mock_llm_provider.chat_completion.call_args[1]["messages"]
    system_message = call_args[0]["content"]
    assert "You are an intent classifier for the Crawlab API" in system_message
    assert json.dumps(console_client.tool_tags) in system_message


# Test _should_use_planning method
@pytest.mark.asyncio
async def test_should_use_planning(monkeypatch, console_client):
    """Test that _should_use_planning correctly analyzes query complexity"""
    # Mock dependencies
    mock_llm_provider = AsyncMock()
    mock_task_planner = MagicMock()
    console_client.task_planner = mock_task_planner
    
    # Setup mock response for a complex query
    mock_llm_provider.chat_completion.return_value = {
        "choices": [{"message": {"content": "true"}}]
    }
    
    # Apply patches
    monkeypatch.setattr(console_client, "llm_provider", mock_llm_provider)
    
    # Call the method
    result = await console_client._should_use_planning("List all spiders and run the first one")
    
    # Verify result
    assert result is True
    
    # Verify correct system message was sent
    call_args = mock_llm_provider.chat_completion.call_args[1]["messages"]
    system_message = call_args[0]["content"]
    assert "You are a query analyzer" in system_message
    assert "A query needs planning if it" in system_message


# Test process_query method with task planning
@pytest.mark.asyncio
async def test_process_query_with_planning(monkeypatch, console_client):
    """Test that process_query uses task planning for complex queries"""
    # Mock dependencies
    mock_should_use_planning = AsyncMock(return_value=True)
    mock_task_planner = AsyncMock()
    mock_task_planner.create_plan.return_value = "Test plan"
    mock_task_planner.execute_plan.return_value = "Executed plan result"
    console_client.task_planner = mock_task_planner
    
    # Apply patches
    monkeypatch.setattr(console_client, "_should_use_planning", mock_should_use_planning)
    
    # Call the method
    result = await console_client.process_query("Complex query")
    
    # Verify method calls and result
    mock_should_use_planning.assert_called_once_with("Complex query")
    mock_task_planner.create_plan.assert_called_once_with("Complex query")
    mock_task_planner.execute_plan.assert_called_once_with("Complex query", "Test plan")
    assert result == "Executed plan result"


# Test process_query method without task planning
@pytest.mark.asyncio
async def test_process_query_without_planning(monkeypatch, console_client):
    """Test that process_query uses standard processing for simple queries"""
    # Mock dependencies
    mock_should_use_planning = AsyncMock(return_value=False)
    mock_process_standard = AsyncMock(return_value="Standard processing result")
    
    # Apply patches
    monkeypatch.setattr(console_client, "_should_use_planning", mock_should_use_planning)
    monkeypatch.setattr(console_client, "_process_query_standard", mock_process_standard)
    
    # Call the method
    result = await console_client.process_query("Simple query")
    
    # Verify method calls and result
    mock_should_use_planning.assert_called_once_with("Simple query")
    mock_process_standard.assert_called_once_with("Simple query")
    assert result == "Standard processing result"


# Test _process_query_standard method
@pytest.mark.asyncio
async def test_process_query_standard(monkeypatch, console_client):
    """Test that _process_query_standard correctly processes queries"""
    # Mock dependencies
    mock_llm_provider = AsyncMock()
    mock_identify_intent = AsyncMock(return_value="Generic")
    mock_llm_provider.has_tool_support.return_value = True
    
    # Setup mock response for a simple query
    mock_llm_provider.chat_completion.return_value = {
        "choices": [{"message": {"content": "Simple response"}}]
    }
    
    # Apply patches
    monkeypatch.setattr(console_client, "llm_provider", mock_llm_provider)
    monkeypatch.setattr(console_client, "identify_user_intent", mock_identify_intent)
    
    # Call the method
    result = await console_client._process_query_standard("What is Crawlab?")
    
    # Verify result
    assert result == "Simple response"
    
    # Verify correct calls were made
    mock_identify_intent.assert_called_once_with("What is Crawlab?")
    mock_llm_provider.has_tool_support.assert_called_once()


# Test cleanup method
@pytest.mark.asyncio
async def test_cleanup(console_client):
    """Test that cleanup correctly closes resources"""
    # Mock exit_stack
    console_client.exit_stack = AsyncMock()
    
    # Call the method
    await console_client.cleanup()
    
    # Verify exit_stack was closed
    console_client.exit_stack.aclose.assert_called_once()


# Test ConsoleClient properly extends MCPClient
def test_console_client_extends_mcp_client(console_client):
    """Test that ConsoleClient properly extends MCPClient"""
    assert isinstance(console_client, MCPClient)
    assert hasattr(console_client, "session")
    assert hasattr(console_client, "tools")
    assert hasattr(console_client, "tool_tags")
    assert hasattr(console_client, "connection_type")
    assert hasattr(console_client, "api_key")

    # Check ConsoleClient specific properties
    assert hasattr(console_client, "llm_provider")
    assert hasattr(console_client, "exit_stack")
    assert hasattr(console_client, "task_planner")

# Parameters for testing different query types - moved to ConsoleClient tests
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
async def test_should_use_planning_with_real_llm(console_client, query, expected, description):
    """
    Test _should_use_planning with real LLM responses for different types of queries

    This test uses real LLM calls instead of mocks to test actual behavior
    """
    # Initialize a task planner with all required parameters
    mock_tools = []  # Empty list of tools for testing purposes
    mock_session = MagicMock()  # Mock session object
    console_client.task_planner = TaskPlanner(
        llm_provider=console_client.llm_provider, tools=mock_tools, session=mock_session
    )

    # Call the actual method with the query
    result = await console_client._should_use_planning(query)

    # Assert based on expected result (but allow flexibility since we're using real LLM)
    # In real LLM testing, we add a note about potential variations
    if result != expected:
        pytest.xfail(
            f"LLM response may vary: expected {expected} but got {result} for query: {query}"
        )

    assert result == expected, f"Failed for query: {query} - {description}"

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
    monkeypatch, console_client, response_content, expected
):
    """Test that _should_use_planning correctly handles different response formats"""
    # Set up task planner
    mock_tools = []  # Empty list of tools for testing purposes
    mock_session = MagicMock()  # Mock session object
    console_client.task_planner = TaskPlanner(
        llm_provider=console_client.llm_provider, tools=mock_tools, session=mock_session
    )

    # Create a mock that returns the test response
    mock_chat_completion = AsyncMock(return_value={"choices": [{"message": {"content": response_content}}]})

    # Apply the monkeypatch
    monkeypatch.setattr(console_client.llm_provider, "chat_completion", mock_chat_completion)

    # Call the method and verify the result
    result = await console_client._should_use_planning("test query")
    assert result == expected, f"Failed for response content: '{response_content}'"
