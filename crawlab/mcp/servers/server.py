#!/usr/bin/env python3
"""Crawlab MCP Server

This server provides AI applications with access to Crawlab functionality
through the Model Context Protocol (MCP).
"""

import argparse
import logging
import os
import sys
import time
from typing import Dict, Any, Optional

# Add these imports at the top
# Import the OpenAPI parser
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from crawlab.mcp.parsers.openapi import OpenAPIParser
from crawlab.mcp.utils.tools import create_tool_function, list_tags

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Create a detailed logger for API execution
api_logger = logging.getLogger("crawlab.api")
api_logger.setLevel(logging.DEBUG)

# Load environment variables
load_dotenv()


def create_mcp_server(spec_path=None) -> FastMCP:
    """Create an MCP server with tools generated from OpenAPI spec

    Args:
        spec_path (str): Path to the OpenAPI YAML file

    Returns:
        FastMCP: Configured MCP server
    """
    # Create an MCP server
    logger.info("Creating MCP server")
    mcp = FastMCP("Crawlab")

    # If no spec path provided, return the server with just the resources
    if not spec_path:
        logger.warning("No OpenAPI spec provided. Only basic resources will be available.")
        return mcp

    # Parse the OpenAPI spec
    logger.info(f"Parsing OpenAPI spec: {spec_path}")
    start_time = time.time()
    
    parser = OpenAPIParser(spec_path)
    if not parser.parse():
        logger.error("Failed to parse OpenAPI spec. Only basic resources will be available.")
        return mcp

    resolved_spec = parser.get_resolved_spec()
    
    parse_time = time.time() - start_time
    logger.info(f"OpenAPI spec parsed in {parse_time:.2f} seconds")
    
    # Log some basic info about the API spec
    paths = resolved_spec.get("paths", {})
    logger.info(f"Found {len(paths)} API paths in the spec")

    # Track registered tools for listing
    registered_tools = {}

    # Register tools based on OpenAPI spec
    logger.info("Registering tools based on OpenAPI spec")
    tool_count = 0
    
    for path, path_item in resolved_spec.get("paths", {}).items():
        for method, operation in path_item.items():
            # Skip if not a valid HTTP method
            if method.lower() not in ["get", "post", "put", "delete", "patch"]:
                continue

            # Skip if no operationId
            if "operationId" not in operation:
                logger.warning(f"Operation {method.upper()} {path} has no operationId. Skipping.")
                continue

            tool_name = operation["operationId"]
            description = operation.get("summary", "") or operation.get("description", "")

            # Store the tool info for list_tools
            registered_tools[tool_name] = {
                "name": tool_name,
                "description": description,
            }

            # Simple type conversion from OpenAPI to Python types
            type_mapping = {
                "string": str,
                "integer": int,
                "number": float,
                "boolean": bool,
                "array": list,
                "object": dict,
            }

            # Extract parameters
            parameters = operation.get("parameters", [])
            param_dict = {}

            # Process path parameters and query parameters
            for param in parameters:
                param_name = param.get("name")
                param_required = param.get("required", False)
                param_schema = param.get("schema", {})
                param_description = param.get("description", "")
                param_type = param_schema.get("type", "string")

                python_type = type_mapping.get(param_type, str)

                # Default value for optional parameters
                default_val = None
                if not param_required:
                    if param_type == "string":
                        default_val = ""
                    elif param_type == "array":
                        default_val = []
                    elif param_type == "object":
                        default_val = {}
                    elif param_type == "boolean":
                        default_val = False
                    elif param_type in ["integer", "number"]:
                        default_val = 0

                # Add parameter to the dictionary
                param_dict[param_name] = (python_type, default_val, param_description)

            # Process request body if present
            request_body = operation.get("requestBody", {})
            if request_body:
                content = request_body.get("content", {})
                json_content = content.get("application/json", {})
                if json_content:
                    schema = json_content.get("schema", {})
                    properties = schema.get("properties", {})
                    required = schema.get("required", [])

                    for prop_name, prop_schema in properties.items():
                        prop_type = prop_schema.get("type", "string")
                        prop_description = prop_schema.get("description", "")
                        prop_required = prop_name in required

                        python_type = type_mapping.get(prop_type, str)

                        # Default value for optional parameters
                        default_val = None
                        if not prop_required:
                            if prop_type == "string":
                                default_val = ""
                            elif prop_type == "array":
                                default_val = []
                            elif prop_type == "object":
                                default_val = {}
                            elif prop_type == "boolean":
                                default_val = False
                            elif prop_type in ["integer", "number"]:
                                default_val = 0

                        # Add parameter to the dictionary
                        param_dict[prop_name] = (python_type, default_val, prop_description)

            # Create and register the tool function
            tool_function = create_tool_function(tool_name, method, path, param_dict)
            
            # Wrap the tool function to add logging
            def create_logged_tool(func, tool_name, method, path):
                async def logged_tool(*args, **kwargs):
                    api_logger.info(f"Executing tool: {tool_name} ({method.upper()} {path})")
                    api_logger.debug(f"Tool parameters: {kwargs}")
                    
                    start_time = time.time()
                    try:
                        result = await func(*args, **kwargs)
                        execution_time = time.time() - start_time
                        api_logger.info(f"Tool {tool_name} executed successfully in {execution_time:.2f} seconds")
                        
                        # Log result summary (truncate if too large)
                        result_str = str(result)
                        if len(result_str) > 200:
                            api_logger.debug(f"Result (truncated): {result_str[:197]}...")
                        else:
                            api_logger.debug(f"Result: {result_str}")
                            
                        return result
                    except Exception as e:
                        execution_time = time.time() - start_time
                        api_logger.error(f"Tool {tool_name} failed after {execution_time:.2f} seconds: {str(e)}", exc_info=True)
                        raise
                
                return logged_tool
            
            logged_tool = create_logged_tool(tool_function, tool_name, method, path)
            
            # Register the tool with MCP
            mcp.add_tool(logged_tool, tool_name, description)
            tool_count += 1
            logger.info(f"Registered tool: {tool_name} ({method.upper()} {path})")

    logger.info(f"Successfully registered {tool_count} tools from OpenAPI spec")

    # Add the list_tags tool to the MCP server
    logger.info("Adding list_tags utility tool")
    
    # Wrap the list_tags tool with logging
    original_list_tags = list_tags(resolved_spec)
    
    async def logged_list_tags(*args, **kwargs):
        api_logger.info("Executing tool: list_tags")
        start_time = time.time()
        try:
            result = await original_list_tags(*args, **kwargs)
            execution_time = time.time() - start_time
            api_logger.info(f"Tool list_tags executed successfully in {execution_time:.2f} seconds")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            api_logger.error(f"Tool list_tags failed after {execution_time:.2f} seconds: {str(e)}", exc_info=True)
            raise
    
    mcp.add_tool(logged_list_tags, "list_tags", "List available API tags/endpoint groups")
    logger.info("list_tags tool registered successfully")

    return mcp


# Add this new function to run the server with SSE transport
def run_with_sse(mcp_server: FastMCP, host="127.0.0.1", port=8000):
    """
    Run the MCP server using SSE transport over HTTP

    Args:
        mcp_server: The MCP server instance
        host: Host to bind to
        port: Port to listen on

    Returns:
        The server URL that clients should connect to
    """
    logger.info(f"Starting MCP server with SSE transport on {host}:{port}")

    mcp_server.settings.host = host
    mcp_server.settings.port = port

    # Add a connection event handler to log client connections
    def on_client_connect(client_id: str):
        logger.info(f"Client connected: {client_id}")
    
    def on_client_disconnect(client_id: str):
        logger.info(f"Client disconnected: {client_id}")
    
    # Register event handlers if the FastMCP class supports them
    if hasattr(mcp_server, 'on_client_connect'):
        mcp_server.on_client_connect = on_client_connect
    
    if hasattr(mcp_server, 'on_client_disconnect'):
        mcp_server.on_client_disconnect = on_client_disconnect

    mcp_server.run("sse")

    # Get the server URL
    server_url = f"http://{host}:{port}"
    logger.info(f"MCP server running at: {server_url}")
    logger.info(f"Use this URL with your client: {server_url}")

    return server_url


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Crawlab MCP Server")
    parser.add_argument(
        "--spec",
        default="crawlab-openapi/openapi.yaml",
        help="Path to OpenAPI specification YAML file",
    )
    # Add new arguments for SSE mode
    parser.add_argument(
        "--sse", action="store_true", help="Run server with SSE transport", default=True
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind to when using SSE (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to listen on when using SSE (default: 8000)"
    )
    parser.add_argument(
        "--log-level", 
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level"
    )

    args = parser.parse_args()
    
    # Set log level based on argument
    log_level = getattr(logging, args.log_level)
    logging.getLogger().setLevel(log_level)
    logger.setLevel(log_level)
    api_logger.setLevel(log_level)
    
    logger.info(f"Starting Crawlab MCP Server with log level: {args.log_level}")
    
    # Check if the OpenAPI spec file exists
    if not os.path.exists(args.spec):
        logger.error(f"OpenAPI spec file not found: {args.spec}")
        logger.error("Please provide a valid path to the OpenAPI specification file.")
        sys.exit(1)

    # Create the MCP server
    start_time = time.time()
    mcp_server = create_mcp_server(args.spec)
    server_init_time = time.time() - start_time
    logger.info(f"MCP server created in {server_init_time:.2f} seconds")

    # Run the server with SSE transport
    if args.sse:
        run_with_sse(mcp_server, args.host, args.port)
    else:
        logger.error("Only SSE transport is currently supported")
        sys.exit(1)


if __name__ == "__main__":
    main()
