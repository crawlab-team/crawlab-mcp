import asyncio
import json
import logging
import os
import sys
import time
from contextlib import AsyncExitStack
from typing import Any, Dict
from urllib.parse import urlparse

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.sse import sse_client

load_dotenv()  # load environment variables from .env

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create a detailed logger for MCP communication
mcp_logger = logging.getLogger("mcp.communication")
mcp_logger.setLevel(logging.DEBUG)


class MCPClient:
    def __init__(self):
        # Initialize core properties
        self.session = None
        self.tools = []
        self.tool_tags = []  # Renamed from tags
        self.connection_type = "sse"  # Default to SSE connection type
        
        # Get MCP API key
        self.api_key = os.getenv("MCP_API_KEY", None)

    async def connect_to_server(self, server_url: str, headers: Dict[str, Any] = None):
        """Connect to an MCP server

        Args:
            server_url: URL of the MCP server endpoint
            headers: Optional headers to include in the request
        """
        logger.info(f"Connecting to MCP server at {server_url}")
        start_time = time.time()

        # Validate URL format
        parsed_url = urlparse(server_url)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            logger.error(f"Invalid server URL format: {server_url}")
            raise ValueError(f"Invalid server URL: {server_url}")

        # Set default headers if none provided
        if headers is None:
            headers = {}

        logger.debug(f"Connection headers: {headers}")

        # Create an exit stack for this connection
        exit_stack = AsyncExitStack()

        try:
            # Connect using SSE transport
            if self.connection_type == "sse":
                logger.info("Using SSE transport for server connection")
                # Fix: sse_client returns a tuple of (read_stream, write_stream)
                read_stream, write_stream = await exit_stack.enter_async_context(
                    sse_client(server_url, headers=headers)
                )
                logger.debug("SSE streams established")

                # Set up the session properly with the read and write streams
                logger.debug("Creating ClientSession with SSE streams")
                self.session = await exit_stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )

                # Initialize the session
                logger.debug("Initializing session")
                await self.session.initialize()

                logger.info("SSE connection established successfully")
            else:
                logger.error(f"Unsupported connection type: {self.connection_type}")
                raise ValueError(f"Unsupported connection type: {self.connection_type}")

            # Fetch available tools from the server
            logger.info("Fetching available tools from server")
            tools_response = await self.session.list_tools()
            self.tools = tools_response.tools

            tool_names = [tool.name for tool in self.tools]
            logger.info(f"Received {len(self.tools)} tools from server")
            logger.debug(f"Available tools: {tool_names}")

            # Fetch available tags from the server
            logger.info("Fetching available tags from server")
            tags_response = await self.session.call_tool("list_tags")

            # Parse the tags response correctly
            try:
                # Handle the case where the response might be structured differently
                if hasattr(tags_response, "content") and isinstance(tags_response.content, str):
                    content_data = json.loads(tags_response.content)
                    if isinstance(content_data, dict) and "tags" in content_data:
                        self.tool_tags = content_data["tags"]
                    else:
                        self.tool_tags = content_data
                elif (
                    hasattr(tags_response, "content")
                    and isinstance(tags_response.content, list)
                    and len(tags_response.content) > 0
                ):
                    # Handle case where content is a list of message objects
                    text_content = tags_response.content[0].text
                    content_data = json.loads(text_content)
                    self.tool_tags = content_data.get("tags", [])
                else:
                    # Fallback to empty list if we can't parse the response
                    logger.warning("Couldn't parse tags response format, using empty tags list")
                    self.tool_tags = []
            except Exception as e:
                logger.error(f"Error parsing tags response: {str(e)}", exc_info=True)
                self.tool_tags = []

            logger.info(f"Received {len(self.tool_tags)} tags from server")
            logger.debug(f"Available tags: {self.tool_tags}")

            connection_time = time.time() - start_time
            logger.info(f"Server connection completed in {connection_time:.2f} seconds")
            
            # Return the exit stack for cleanup by the caller
            return exit_stack
        except Exception as e:
            logger.error(f"Failed to connect to server: {str(e)}", exc_info=True)
            await exit_stack.aclose()
            raise
