"""
Crawlab Model Control Protocol (MCP) - A framework for AI agents
"""

__version__ = "0.7.0"

# Import the main CLI function at runtime to avoid circular imports
def get_cli_main():
    from crawlab.mcp.cli import main as cli_main
    return cli_main
