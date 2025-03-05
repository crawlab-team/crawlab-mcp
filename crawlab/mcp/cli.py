#!/usr/bin/env python
"""
Crawlab MCP CLI entry point
"""
import argparse
import asyncio
import sys


def main():
    """
    Main entry point for the Crawlab MCP CLI
    """
    parser = argparse.ArgumentParser(
        description="Crawlab MCP - Model Control Protocol for AI Agents",
        prog="crawlab-mcp"
    )

    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Server command
    server_parser = subparsers.add_parser("server", help="Run MCP server")
    server_parser.add_argument("--spec", help="Path to OpenAPI specification YAML file")
    server_parser.add_argument(
        "--sse", action="store_true", default=True, help="Run server with SSE transport"
    )
    server_parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind to when using SSE (default: 127.0.0.1)"
    )
    server_parser.add_argument(
        "--port", type=int, default=8000, help="Port to listen on when using SSE (default: 8000)"
    )

    # Client command
    client_parser = subparsers.add_parser("client", help="Run MCP client")
    client_parser.add_argument(
        "--server_url",
        default="http://localhost:8000/sse",
        help="URL of the MCP server to connect to",
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
            from crawlab.mcp.servers.server import main as server_main

            # Override sys.argv with the right arguments for the server_main function
            sys.argv = [sys.argv[0]]
            if args.spec:
                sys.argv.extend(["--spec", args.spec])
            if args.sse:
                sys.argv.append("--sse")
            sys.argv.extend(["--host", args.host])
            sys.argv.extend(["--port", str(args.port)])

            # Run the server
            server_main()
        except ImportError as e:
            print(f"Error importing server module: {e}")
            print("Please make sure all dependencies are installed.")
            print("You may need to install additional packages to run the server.")
            sys.exit(1)

    elif args.command == "client":
        # Check if the client module is available
        try:
            from crawlab.mcp.clients.client import main as client_main

            # Override sys.argv with the right arguments for the client_main function
            sys.argv = [sys.argv[0], args.server_url]

            # Run the client
            asyncio.run(client_main())
        except ImportError as e:
            print(f"Error importing client module: {e}")
            print("Please make sure all dependencies are installed.")
            print("You may need to install additional packages to run the client.")
            sys.exit(1)


if __name__ == "__main__":
    main()
