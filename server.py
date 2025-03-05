#!/usr/bin/env python3
"""Crawlab MCP Server

This server provides AI applications with access to Crawlab functionality
through the Model Context Protocol (MCP).
"""

import argparse

# Add these imports at the top
# Import the OpenAPI parser
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from openapi import OpenAPIParser
from utils import create_tool_function

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
    mcp = FastMCP("Crawlab")

    # If no spec path provided, return the server with just the resources
    if not spec_path:
        print("No OpenAPI spec provided. Only basic resources will be available.")
        return mcp

    # Parse the OpenAPI spec
    print(f"Parsing OpenAPI spec: {spec_path}")
    parser = OpenAPIParser(spec_path)
    if not parser.parse():
        print("Failed to parse OpenAPI spec. Only basic resources will be available.")
        return mcp

    resolved_spec = parser.get_resolved_spec()

    # Track registered tools for listing
    registered_tools = {}

    # Register tools based on OpenAPI spec
    for path, path_item in resolved_spec.get("paths", {}).items():
        for method, operation in path_item.items():
            # Skip if not a valid HTTP method
            if method.lower() not in ["get", "post", "put", "delete", "patch"]:
                continue

            # Skip if no operationId
            if "operationId" not in operation:
                print(f"Warning: Operation {method.upper()} {path} has no operationId. Skipping.")
                continue

            tool_tags = operation.get("tags", [])
            if not tool_tags or len(tool_tags) == 0:
                continue
            tool_name = f"{tool_tags[0]}/{operation['operationId']}"
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

                param_dict[param_name] = (python_type, default_val, param_description)

            # Process request body if present
            if "requestBody" in operation and "content" in operation["requestBody"]:
                # Typically looking for application/json content
                content_types = operation["requestBody"]["content"]
                if (
                    "application/json" in content_types
                    and "schema" in content_types["application/json"]
                ):
                    body_schema = content_types["application/json"]["schema"]

                    # Extract properties from request body schema
                    if "properties" in body_schema:
                        for prop_name, prop_schema in body_schema["properties"].items():
                            prop_type = prop_schema.get("type", "string")
                            prop_required = prop_name in body_schema.get("required", [])
                            prop_description = prop_schema.get("description", "")

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

                            param_dict[prop_name] = (
                                python_type,
                                default_val,
                                prop_description,
                            )

            # Create the tool function
            tool_function = create_tool_function(tool_name, method, path, param_dict)

            # Add the tool to the MCP server
            mcp.add_tool(tool_function, tool_name, description)

            # Register the tool with MCP
            print(f"Registered tool: {tool_name}")

    def list_tags():
        """List all available tags/endpoint groups in the API.

        Returns:
            dict: A dictionary with a list of available tags and their descriptions, including tools under each tag.
        """
        tags_dict = {}

        # Extract tags from the top-level OpenAPI spec
        for tag_info in resolved_spec.get("tags", []):
            tag_name = tag_info.get("name", "")
            tags_dict[tag_name] = {"description": tag_info.get("description", ""), "tools": []}

        # If no tags are defined in the spec, initialize from operations
        if not tags_dict:
            for path, path_item in resolved_spec.get("paths", {}).items():
                for method, operation in path_item.items():
                    if method.lower() not in ["get", "post", "put", "delete", "patch"]:
                        continue

                    operation_tags = operation.get("tags", [])
                    for tag in operation_tags:
                        if tag not in tags_dict:
                            tags_dict[tag] = {
                                "description": f"Operations tagged with {tag}",
                                "tools": [],
                            }

        # Populate tools under each tag
        for path, path_item in resolved_spec.get("paths", {}).items():
            for method, operation in path_item.items():
                if method.lower() not in ["get", "post", "put", "delete", "patch"]:
                    continue

                operation_tags = operation.get("tags", [])
                operation_id = operation.get("operationId")
                summary = operation.get("summary", "")

                if operation_id:
                    tool_info = {
                        "name": operation_id,
                        "method": method.upper(),
                        "summary": summary,
                    }

                    # Add tool to each tag it belongs to
                    for tag in operation_tags:
                        if tag in tags_dict:
                            tags_dict[tag]["tools"].append(tool_info)

        # Convert to list format for return
        tags_list = [
            {"name": name, "description": info["description"], "tools": info["tools"]}
            for name, info in tags_dict.items()
        ]

        return {"tags": tags_list}

    # Add the list_tags tool to the MCP server
    mcp.add_tool(list_tags, "list_tags", "List available API tags/endpoint groups")

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

    mcp_server.settings.host = host
    mcp_server.settings.port = port

    mcp_server.run("sse")

    # Get the server URL
    server_url = f"http://{host}:{port}"
    print(f"Starting MCP server with SSE transport at: {server_url}")
    print(f"Use this URL with your client: {server_url}")

    return server_url


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Crawlab MCP Server")
    parser.add_argument("--spec", help="Path to OpenAPI specification YAML file")
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
    args = parser.parse_args()

    # Create MCP server with tools from OpenAPI spec if provided
    mcp = create_mcp_server(args.spec)

    # Start the MCP server
    if args.sse:
        # Run with SSE transport
        print("Starting MCP server with SSE transport...")
        run_with_sse(mcp, host=args.host, port=args.port)
    else:
        # Run with standard stdio transport
        print("Starting MCP server with stdio transport...")
        mcp.run()


if __name__ == "__main__":
    main()
