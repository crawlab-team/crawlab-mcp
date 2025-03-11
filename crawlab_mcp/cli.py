#!/usr/bin/env python
"""
Crawlab MCP CLI entry point
"""

import argparse
import asyncio
import os
import sys


def main():
    """
    Main entry point for the Crawlab MCP CLI
    """
    parser = argparse.ArgumentParser(
        description="Crawlab MCP - Model Control Protocol for AI Agents", prog="crawlab_mcp-mcp"
    )

    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Server command
    server_parser = subparsers.add_parser(
        "server",
        help="Run the MCP server",
        description="Run the Crawlab MCP server to provide API access to Crawlab functionality",
    )
    server_parser.add_argument(
        "--spec",
        default="../openapi/openapi.yaml",
        help="Path to OpenAPI specification YAML file (default: ../openapi/openapi.yaml)",
    )
    server_parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind the server to (default: 127.0.0.1)"
    )
    server_parser.add_argument(
        "--port", type=int, default=9000, help="Port to listen on (default: 9000)"
    )
    server_parser.add_argument(
        "--export-schemas", metavar="FILE", help="Export tool schemas to specified JSON file"
    )
    server_parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level (default: INFO)",
    )
    server_parser.add_argument(
        "--sse",
        action="store_true",
        default=True,
        help="Use SSE transport for server communication (this is currently the only supported transport)",
    )

    # Client command
    client_parser = subparsers.add_parser("client", help="Run MCP client")
    client_parser.add_argument(
        "--server-url",
        default="http://localhost:9000/sse",
        help="URL of the MCP server to connect to (default: http://localhost:9000/sse)",
        dest="server_url",
    )
    client_parser.add_argument(
        "--auth-token", help="Authorization token for the MCP server", dest="auth_token"
    )
    client_parser.add_argument(
        "--api-key",
        help="API key for the LLM provider (can also be set via MCP_API_KEY env var)",
        dest="api_key",
    )

    # Parse arguments
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    # Handle different commands
    if args.command == "server":
        # Check if the server module is available
        try:
            from crawlab_mcp.servers.server import main as server_main

            # Override sys.argv with the right arguments for the server_main function
            sys.argv = [sys.argv[0]]
            sys.argv.extend(["--spec", args.spec])  # Always include spec
            sys.argv.extend(["--host", args.host])
            sys.argv.extend(["--port", str(args.port)])
            if args.export_schemas:
                sys.argv.extend(["--export-schemas", args.export_schemas])
            sys.argv.extend(["--log-level", args.log_level])  # Always include log level

            # Run the server
            try:
                server_main()
            except KeyboardInterrupt:
                print("\nServer stopped by user")

        except ImportError as e:
            print(f"Error importing server module: {e}")
            print("Please make sure all dependencies are installed.")
            print("You may need to install additional packages to run the server.")
            sys.exit(1)

    elif args.command == "client":
        # Check if the client module is available
        try:
            from crawlab_mcp.clients.console_client import main as client_main

            # Set environment variables if provided
            if args.auth_token:
                os.environ["MCP_AUTH_TOKEN"] = args.auth_token
            if args.api_key:
                os.environ["MCP_API_KEY"] = args.api_key

            # Override sys.argv with the right arguments for the client_main function
            sys.argv = [sys.argv[0], args.server_url]

            # Run the client
            try:
                asyncio.run(client_main())
            except KeyboardInterrupt:
                print("\nClient stopped by user")

        except ImportError as e:
            print(f"Error importing client module: {e}")
            print("Please make sure all dependencies are installed.")
            print("You may need to install additional packages to run the client.")
            sys.exit(1)


if __name__ == "__main__":
    main()
