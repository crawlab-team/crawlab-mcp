#!/usr/bin/env python3
"""Crawlab MCP Server

This server provides AI applications with access to Crawlab functionality
through the Model Context Protocol (MCP).
"""

import argparse
import logging
import os
import re
import sys
import time
from typing import Any, Dict, Literal

# Add these imports at the top
# Import the OpenAPI parser
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from crawlab_mcp.parsers.openapi import OpenAPIParser
from crawlab_mcp.utils.tools import (
    create_tool_function,
    export_tool_schemas,
    extract_openapi_parameters,
    get_tool_schemas_function,
    list_parameter_info,
    list_tags,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Create a detailed logger for API execution
api_logger = logging.getLogger("crawlab_mcp.api")
api_logger.setLevel(logging.DEBUG)

# Load environment variables
load_dotenv()


def create_mcp_server(spec_path) -> FastMCP:
    """Create and configure the FastMCP server with tools from the OpenAPI spec.

    Args:
        spec_path: Path to the OpenAPI spec file.

    Returns:
        Configured FastMCP server instance
    """
    # Use default spec path if none provided
    if not spec_path or not os.path.exists(spec_path):
        logger.warning(f"OpenAPI spec not found at {spec_path}. No API tools will be registered.")
        spec_path = None

    # Create the MCP server
    mcp = FastMCP()

    # Setup API tools if spec is available
    if spec_path:
        # Parse the spec using OpenAPIParser
        parser = OpenAPIParser(spec_path)
        if not parser.parse():
            logger.error(f"Failed to parse OpenAPI spec at {spec_path}")
            return mcp

        # Get the resolved spec
        spec = parser.get_resolved_spec()

        # Extract operations and register as tools
        tool_count = 0
        registered_tools = {}

        # Add tools from the OpenAPI spec
        for path, path_item in spec.get("paths", {}).items():
            for method, operation in path_item.items():
                if method not in ["get", "post", "put", "delete", "patch"]:
                    continue

                # Skip operations marked with x-exclude-from-tools
                if operation.get("x-exclude-from-tools"):
                    continue

                # Build the operation ID and description
                operation_id = operation.get("operationId")
                if not operation_id:
                    # Generate an operationId if not provided
                    operation_id = (
                        f"{method}_{path.replace('/', '_').replace('{', '').replace('}', '')}"
                    )
                    logger.warning(
                        f"No operationId for {method.upper()} {path}, using {operation_id}"
                    )

                # Clean up the operation ID to be a valid Python identifier
                tool_name = re.sub(r"[^a-zA-Z0-9_]", "_", operation_id)

                # Get the operation description
                description = operation.get("summary", "") or operation.get("description", "")
                if not description:
                    description = f"{method.upper()} {path}"

                # Skip duplicate tool names
                if tool_name in registered_tools:
                    logger.warning(
                        f"Duplicate tool name {tool_name}, skipping {method.upper()} {path}"
                    )
                    continue

                # Store reference to the registered tool
                registered_tools[tool_name] = {
                    "method": method,
                    "path": path,
                    "operation": operation,
                }

                # Extract parameters from the operation
                param_dict = extract_openapi_parameters(operation)

                # Create and register the tool function
                tool_function = create_tool_function(tool_name, method, path, param_dict)

                # Register the tool with MCP
                mcp.add_tool(tool_function, tool_name, description)
                tool_count += 1
                logger.info(f"Registered tool: {tool_name} ({method.upper()} {path})")

        logger.info(f"Successfully registered {tool_count} tools from OpenAPI spec")

        # Add the list_tags tool to the MCP server
        logger.info("Adding list_tags utility tool")
        tags_tool = list_tags(spec)
        mcp.add_tool(tags_tool, "list_tags", "List all tags in the API")

        # Add the get_tool_schemas tool
        logger.info("Adding get_tool_schemas utility tool")
        get_schemas_tool = get_tool_schemas_function(registered_tools)
        mcp.add_tool(get_schemas_tool, "get_tool_schemas", "Get JSON schemas for available tools")

        # Add the new list_parameter_info tool
        logger.info("Adding list_parameter_info utility tool")
        param_info_tool = list_parameter_info(registered_tools)
        mcp.add_tool(
            param_info_tool,
            "list_parameter_info",
            "Get detailed information about required parameters and enum values for tools",
        )

    # Done
    return mcp


# Add this new function to run the server with SSE transport
def run_with_sse(mcp_server: FastMCP, host="127.0.0.1", port=9000):
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
    if hasattr(mcp_server, "on_client_connect"):
        mcp_server.on_client_connect = on_client_connect

    if hasattr(mcp_server, "on_client_disconnect"):
        mcp_server.on_client_disconnect = on_client_disconnect

    def hello(mandatory: str, param: Literal["hello", "world"] = "hello") -> Dict[str, Any]:
        """
        A simple tool that returns a message.
        """

    mcp_server.add_tool(hello, "hello")

    mcp_server.run("sse")

    # Get the server URL
    server_url = f"http://{host}:{port}"
    logger.info(f"MCP server running at: {server_url}")
    logger.info(f"Use this URL with your client: {server_url}")

    return server_url


def main():
    """Main entry point for the MCP server."""
    # Parse command line arguments
    args = parse_command_line_arguments()

    # Configure logging
    configure_logging(args.log_level)

    # Check if the OpenAPI spec file exists
    validate_spec_file(args.spec)

    # Create MCP server and get registered tools
    mcp_server = create_and_initialize_server(args.spec)

    # Run with SSE transport
    run_with_sse(mcp_server, host=args.host, port=args.port)


def parse_command_line_arguments():
    """Parse command line arguments for the server."""
    parser = argparse.ArgumentParser(description="Crawlab MCP Server")
    parser.add_argument(
        "--spec",
        default="crawlab-openapi/openapi.yaml",
        help="Path to OpenAPI specification YAML file",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument(
        "--export-schemas",
        help="Export tool schemas to specified JSON file",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level",
    )

    return parser.parse_args()


def configure_logging(log_level_str):
    """Configure logging with the specified level."""
    log_level = getattr(logging, log_level_str)
    logging.getLogger().setLevel(log_level)
    logger.setLevel(log_level)
    api_logger.setLevel(log_level)

    logger.info(f"Starting Crawlab MCP Server with log level: {log_level_str}")


def validate_spec_file(spec_path):
    """Validate that the OpenAPI spec file exists."""
    if not os.path.exists(spec_path):
        logger.error(f"OpenAPI spec file not found: {spec_path}")
        logger.error("Please provide a valid path to the OpenAPI specification file.")
        sys.exit(1)


def create_and_initialize_server(spec_path):
    """Create and initialize the MCP server with the OpenAPI spec."""
    start_time = time.time()
    mcp_server = create_mcp_server(spec_path)
    server_init_time = time.time() - start_time
    logger.info(f"MCP server created in {server_init_time:.2f} seconds")
    return mcp_server


def export_schemas(registered_tools, output_file):
    """Export tool schemas to a file."""
    # Get all tool schemas
    tools_data = {"tools": list(registered_tools.values())}

    # Export to file
    export_tool_schemas(tools_data, output_file)
    logger.info(f"Tool schemas exported to {output_file}")


if __name__ == "__main__":
    main()
