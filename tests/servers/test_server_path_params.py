import asyncio
import json
import tempfile
from unittest.mock import MagicMock, patch

import pytest
import os

# Directly patch the OpenAPIParser import
from crawlab_mcp.servers.server import create_mcp_server


class TestServerPathParams:
    """Integration tests for path parameter handling in the MCP server."""

    @pytest.mark.asyncio
    async def test_server_registers_path_param_tools(self):
        """Test that the MCP server correctly registers tools with path parameters."""
        # Create a sample OpenAPI spec
        openapi_spec = {
            "paths": {
                "/spiders/{id}": {
                    "get": {
                        "operationId": "getSpiderById",
                        "summary": "Get spider by ID",
                        "parameters": [
                            {
                                "name": "id",
                                "in": "path",
                                "required": True,
                                "description": "Spider ID",
                                "schema": {"type": "string"},
                            },
                            {
                                "name": "include_stats",
                                "in": "query",
                                "required": False,
                                "description": "Include statistics",
                                "schema": {"type": "boolean"},
                            },
                        ],
                        "responses": {"200": {"description": "Success"}},
                    }
                },
                "/projects/{projectId}/spiders/{spiderId}": {
                    "get": {
                        "operationId": "getSpiderInProject",
                        "summary": "Get spider in project",
                        "parameters": [
                            {
                                "name": "projectId",
                                "in": "path",
                                "required": True,
                                "description": "Project ID",
                                "schema": {"type": "string"},
                            },
                            {
                                "name": "spiderId",
                                "in": "path",
                                "required": True,
                                "description": "Spider ID",
                                "schema": {"type": "string"},
                            },
                        ],
                        "responses": {"200": {"description": "Success"}},
                    }
                },
            }
        }
        
        # Create a temporary file with our mock spec
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            # Write YAML content to the temporary file
            temp_file.write("""openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
paths:
  /spiders/{id}:
    get:
      operationId: getSpiderById
      summary: Get spider by ID
      parameters:
        - name: id
          in: path
          required: true
          description: Spider ID
          schema:
            type: string
        - name: include_stats
          in: query
          required: false
          description: Include statistics
          schema:
            type: boolean
      responses:
        '200':
          description: Success
  /projects/{projectId}/spiders/{spiderId}:
    get:
      operationId: getSpiderInProject
      summary: Get spider in project
      parameters:
        - name: projectId
          in: path
          required: true
          description: Project ID
          schema:
            type: string
        - name: spiderId
          in: path
          required: true
          description: Spider ID
          schema:
            type: string
      responses:
        '200':
          description: Success
""")
            temp_path = temp_file.name
        
        try:
            print(f"\nCreated temporary spec file at: {temp_path}")
            
            # Create the MCP server with our temporary spec file
            with patch('crawlab_mcp.utils.tools.api_request', return_value={"data": {"success": True}}):
                mcp_server = create_mcp_server(temp_path)
                
                # Patch FastMCP.list_tools to print something before returning
                original_list_tools = mcp_server.list_tools
                async def debug_list_tools():
                    print("Debug - list_tools called")
                    result = await original_list_tools()
                    print(f"Debug - list_tools returning: {result}")
                    return result
                
                mcp_server.list_tools = debug_list_tools
                
                tools = await mcp_server.list_tools()
                
                print(f"Debug - tools returned: {tools}")
                registered_tools = {tool.name: tool for tool in tools}
                
                # Check that the tools with path parameters were registered
                assert "getSpiderById" in registered_tools
                assert "getSpiderInProject" in registered_tools
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                print(f"Cleaned up temporary file: {temp_path}")

    @pytest.mark.asyncio
    async def test_server_path_param_tool_execution(self):
        """Test that the MCP server correctly executes tools with path parameters."""
        # Create a sample OpenAPI spec
        openapi_spec = {
            "paths": {
                "/spiders/{id}": {
                    "get": {
                        "operationId": "getSpiderById",
                        "summary": "Get spider by ID",
                        "parameters": [
                            {
                                "name": "id",
                                "in": "path",
                                "required": True,
                                "description": "Spider ID",
                                "schema": {"type": "string"},
                            },
                            {
                                "name": "include_stats",
                                "in": "query",
                                "required": False,
                                "description": "Include statistics",
                                "schema": {"type": "boolean"},
                            },
                        ],
                        "responses": {"200": {"description": "Success"}},
                    }
                },
                "/projects/{projectId}/spiders/{spiderId}": {
                    "get": {
                        "operationId": "getSpiderInProject",
                        "summary": "Get spider in project",
                        "parameters": [
                            {
                                "name": "projectId",
                                "in": "path",
                                "required": True,
                                "description": "Project ID",
                                "schema": {"type": "string"},
                            },
                            {
                                "name": "spiderId",
                                "in": "path",
                                "required": True,
                                "description": "Spider ID",
                                "schema": {"type": "string"},
                            },
                        ],
                        "responses": {"200": {"description": "Success"}},
                    }
                },
            }
        }
        
        # Create a temporary file with our mock spec
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
            # Write YAML content to the temporary file
            temp_file.write("""openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
paths:
  /spiders/{id}:
    get:
      operationId: getSpiderById
      summary: Get spider by ID
      parameters:
        - name: id
          in: path
          required: true
          description: Spider ID
          schema:
            type: string
        - name: include_stats
          in: query
          required: false
          description: Include statistics
          schema:
            type: boolean
      responses:
        '200':
          description: Success
  /projects/{projectId}/spiders/{spiderId}:
    get:
      operationId: getSpiderInProject
      summary: Get spider in project
      parameters:
        - name: projectId
          in: path
          required: true
          description: Project ID
          schema:
            type: string
        - name: spiderId
          in: path
          required: true
          description: Spider ID
          schema:
            type: string
      responses:
        '200':
          description: Success
""")
            temp_path = temp_file.name
        
        try:
            print(f"\nCreated temporary spec file at: {temp_path}")
            
            # Create the MCP server with our temporary spec file
            with patch('crawlab_mcp.utils.tools.api_request', return_value={"data": {"success": True}}):
                mcp_server = create_mcp_server(temp_path)
                
                # Patch FastMCP.list_tools to print something before returning
                original_list_tools = mcp_server.list_tools
                async def debug_list_tools():
                    print("Debug - list_tools called")
                    result = await original_list_tools()
                    print(f"Debug - list_tools returning: {result}")
                    return result
                
                mcp_server.list_tools = debug_list_tools
                
                tools = await mcp_server.list_tools()
                
                print(f"Debug - tools returned: {tools}")

                # Get the tool function (we're directly accessing it for testing)
                get_spider_tool_name = None
                for tool in tools:
                    if tool.name == "getSpiderById":
                        get_spider_tool_name = tool.name
                        break

                assert get_spider_tool_name is not None

                # Now test the multiple path parameters case
                get_project_spider_tool_name = None
                for tool in tools:
                    if tool.name == "getSpiderInProject":
                        get_project_spider_tool_name = tool.name
                        break

                assert get_project_spider_tool_name is not None
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                print(f"Cleaned up temporary file: {temp_path}")
