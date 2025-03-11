import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest
import time

# Add the parent directory to sys.path to import the client module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlab_mcp.clients.client import MCPClient


@pytest.fixture
def mcp_client():
    """Create a real MCPClient for testing"""
    client = MCPClient()
    return client


# Test MCPClient core properties
def test_mcp_client_init(mcp_client):
    """Test that MCPClient initializes with the correct core properties"""
    assert mcp_client.session is None
    assert isinstance(mcp_client.tools, list)
    assert isinstance(mcp_client.tool_tags, list)
    assert mcp_client.connection_type == "sse"
    assert hasattr(mcp_client, "api_key")

# Test connection method returns an exit stack
@pytest.mark.asyncio
async def test_connect_to_server_returns_exit_stack(monkeypatch, mcp_client):
    """Test that connect_to_server returns an exit stack for resource management"""
    # Mock dependencies
    mock_read_stream = AsyncMock()
    mock_write_stream = AsyncMock()
    mock_session = AsyncMock()
    mock_exit_stack = AsyncMock()
    mock_client_session = AsyncMock()

    # Mock the AsyncExitStack
    mock_exit_stack.enter_async_context.side_effect = [
        (mock_read_stream, mock_write_stream),
        mock_session
    ]

    # Setup mock responses
    mock_session.list_tools.return_value = MagicMock(tools=[])
    mock_session.call_tool.return_value = MagicMock(
        content='{"tags": []}'
    )

    # Apply patches
    monkeypatch.setattr("crawlab_mcp.clients.client.AsyncExitStack", lambda: mock_exit_stack)
    monkeypatch.setattr("crawlab_mcp.clients.client.ClientSession", lambda *args: mock_client_session)
    monkeypatch.setattr("crawlab_mcp.clients.client.sse_client", AsyncMock(
        return_value=(mock_read_stream, mock_write_stream)))

    # Call the method
    result = await mcp_client.connect_to_server("http://test-server.com")

    # Verify result is the exit stack
    assert result == mock_exit_stack

@pytest.mark.asyncio
async def test_real_connection_to_server(mcp_client):
    """Test a real connection to the MCP server.
    
    This test starts a real MCP server using the CLI module and then
    connects to it with a real client.
    """
    import asyncio
    import contextlib
    import multiprocessing
    import os
    import tempfile
    
    from crawlab_mcp.servers.server import create_mcp_server, run_with_sse
    
    # Generate a random port number to avoid conflicts
    import random
    port = random.randint(20000, 30000)
    host = "127.0.0.1"
    
    # Use a temp file for the openapi spec
    # If this fails, we can use a fixed path from the repo
    try:
        # Create a temporary file for a minimal OpenAPI spec
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yaml') as f:
            spec_file = f.name
            f.write("""
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
paths:
  /test:
    get:
      operationId: test
      summary: Test endpoint
      responses:
        '200':
          description: Success
            """)
    except Exception as e:
        # If temp file creation fails, use a default spec from the repo
        print(f"Failed to create temp spec file: {e}")
        # Look for spec file in common locations
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        spec_file = os.path.join(repo_root, "openapi", "openapi.yaml")
        if not os.path.exists(spec_file):
            spec_file = os.path.join(repo_root, "..", "openapi", "openapi.yaml")
    
    # Define server process function to run in another process
    def run_server(host, port, spec_path):
        try:
            # Create and run the server
            mcp_server = create_mcp_server(spec_path)
            run_with_sse(mcp_server, host=host, port=port)
        except KeyboardInterrupt:
            print("Server stopped by Ctrl+C")
        except Exception as e:
            print(f"Server error: {e}")
    
    # Start server in a separate process
    server_process = multiprocessing.Process(
        target=run_server,
        args=(host, port, spec_file),
        daemon=True  # Automatically terminate when parent process exits
    )
    
    try:
        # Start the server
        server_process.start()
        
        # Wait for server to start
        print(f"Waiting for server to start on {host}:{port}...")
        for _ in range(10):
            await asyncio.sleep(0.5)
            try:
                # Try connecting to see if server is up
                reader, writer = await asyncio.open_connection(host, port)
                writer.close()
                await writer.wait_closed()
                print(f"Server started on {host}:{port}")
                break
            except (ConnectionRefusedError, OSError):
                continue
        else:
            raise RuntimeError(f"Failed to connect to server on {host}:{port}")
        
        # Connect to the real server
        server_url = f"http://{host}:{port}/sse"
        exit_stack = await mcp_client.connect_to_server(server_url)
        
        try:
            # Verify client is properly initialized
            assert mcp_client.session is not None, "Session should be established"
            assert hasattr(mcp_client.session, "initialize"), "Session should have initialize method"
            
            # Verify tools are loaded
            assert isinstance(mcp_client.tools, list), "Tools should be a list"
            
            # Verify tags are loaded
            assert isinstance(mcp_client.tool_tags, list), "Tool tags should be a list"
            
            # Test list_tools operation to confirm the connection is working
            tools_response = await mcp_client.session.list_tools()
            assert hasattr(tools_response, "tools"), "Should get tools response"
            
            print(f"Connection successful, found {len(mcp_client.tools)} tools")
        finally:
            # Clean up client resources
            await exit_stack.aclose()
    
    finally:
        # Clean up the server process
        if server_process.is_alive():
            print("Stopping server...")
            # Use both SIGTERM and then SIGKILL if needed
            server_process.terminate()
            
            # Give it a moment to terminate gracefully
            for _ in range(5):
                if not server_process.is_alive():
                    break
                time.sleep(0.2)
            
            # If still alive, force kill
            if server_process.is_alive():
                print("Server didn't terminate gracefully, killing...")
                server_process.kill()
                server_process.join(timeout=1)
            
            # Don't wait indefinitely - just detach if still running
            if server_process.is_alive():
                print("WARNING: Server process couldn't be terminated properly")
                # Setting daemon=True earlier should ensure it's killed on exit
        
        # Remove temp file if created
        if spec_file and os.path.exists(spec_file) and spec_file.endswith('.yaml'):
            try:
                os.unlink(spec_file)
            except OSError:
                pass

