#!/usr/bin/env python3
"""
Test script for demonstrating OpenAPI to inputSchema conversion.

This script loads a sample OpenAPI spec and generates the inputSchema for each operation,
displaying the result in JSON format.
"""

import json
import os
import sys

from crawlab_mcp.parsers.openapi import OpenAPIParser
from crawlab_mcp.utils.tools import create_input_schema_from_openapi


def main():
    """Main function that processes an OpenAPI spec and prints schemas."""
    # Use the default OpenAPI spec path or a command-line argument
    spec_path = sys.argv[1] if len(sys.argv) > 1 else "crawlab_mcp-openapi/openapi.yaml"

    if not os.path.exists(spec_path):
        print(f"Error: OpenAPI spec file not found: {spec_path}")
        print("Please provide a valid path to the OpenAPI specification file.")
        return 1

    print(f"Parsing OpenAPI spec: {spec_path}")

    # Parse the OpenAPI spec
    parser = OpenAPIParser(spec_path)
    if not parser.parse():
        print("Error: Failed to parse OpenAPI spec.")
        return 1

    # Get the resolved spec
    resolved_spec = parser.get_resolved_spec()

    # Create a dictionary to store all tool schemas
    all_tools = []

    # Process each path and operation
    for path, path_item in resolved_spec.get("paths", {}).items():
        for method, operation in path_item.items():
            if method.lower() not in ["get", "post", "put", "delete", "patch"]:
                continue

            if "operationId" not in operation:
                print(f"Warning: Operation {method.upper()} {path} has no operationId. Skipping.")
                continue

            # Get the operation ID
            operation_id = operation["operationId"]

            # Generate the input schema
            tool_schema = create_input_schema_from_openapi(operation_id, operation, method, path)

            # Add to the list of all tools
            all_tools.append(tool_schema)

    # Print example tool schema for demonstration
    if all_tools:
        print("\nExample Tool Schema:")
        print(json.dumps(all_tools[0], indent=2))

        print(f"\nTotal tools processed: {len(all_tools)}")

        # Optionally export all tools to a file
        if len(sys.argv) > 2:
            output_file = sys.argv[2]
            with open(output_file, "w") as f:
                json.dump({"tools": all_tools}, f, indent=2)
            print(f"All tool schemas exported to {output_file}")
    else:
        print("No tools found in the spec.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
