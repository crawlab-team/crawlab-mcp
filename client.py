import asyncio
import json
import logging
import os
from contextlib import AsyncExitStack
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.sse import sse_client
from openai import AzureOpenAI

load_dotenv()  # load environment variables from .env

logger = logging.getLogger(__name__)


class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.stdio = None
        self.write = None
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.connection_type = "sse"  # Default connection type is now SSE

        # Initialize Azure OpenAI client with API key from environment variables
        self.openai = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2023-05-15"),
        )

    async def connect_to_server(self, server_url: str, headers: Dict[str, Any] = None):
        """Connect to an MCP server

        Args:
            server_url: URL of the MCP server endpoint
            headers: Optional headers to include in the request
        """
        logger.info(f"Connecting to MCP server at {server_url}")

        # Validate URL format
        parsed_url = urlparse(server_url)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            raise ValueError(f"Invalid server URL: {server_url}")

        # Set default headers if none provided
        if headers is None:
            headers = {}

        # Create SSE connection
        read_stream, write_stream = await self.exit_stack.enter_async_context(
            sse_client(server_url, headers=headers)
        )

        # Set up the session
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )

        # Initialize the session
        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        tools = response.tools

        # List available tags
        response = await self.session.call_tool("list_tags")
        print(json.dumps(json.loads(response.content[0].text)["tags"], indent=2))

        logger.info(f"Connected to server with tools: {[tool.name for tool in tools]}")
        print("\nConnected to server with tools:", [tool.name for tool in tools])

        return self.session

    async def process_query(self, query: str) -> str:
        """Process a query using Azure OpenAI and available tools"""
        messages = [{"role": "user", "content": query}]

        response = await self.session.list_tools()
        available_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema,
                },
            }
            for tool in response.tools
        ]

        # Initial Azure OpenAI API call
        model_name = os.getenv("AZURE_OPENAI_MODEL_NAME")
        response = self.openai.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=available_tools,
            tool_choice="auto",
        )

        # Process response and handle tool calls
        tool_results = []
        final_text = []

        response_message = response.choices[0].message
        final_text.append(response_message.content or "")

        if response_message.tool_calls:
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_args = tool_call.function.arguments

                # Execute tool call
                result = await self.session.call_tool(function_name, function_args)
                tool_results.append({"call": function_name, "result": result})
                final_text.append(f"[Calling tool {function_name} with args {function_args}]")

                # Continue conversation with tool results
                messages.append(
                    {
                        "role": "assistant",
                        "content": response_message.content,
                        "tool_calls": response_message.tool_calls,
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result.content,
                    }
                )

                # Get next response from OpenAI
                response = self.openai.chat.completions.create(
                    model=model_name,
                    messages=messages,
                )

                final_text.append(response.choices[0].message.content)

        return "\n".join(final_text)

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == "quit":
                    break

                response = await self.process_query(query)
                print("\n" + response)

            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()


async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <server_url>")
        sys.exit(1)

    client = MCPClient()
    try:
        # Use the server URL from command line arguments
        server_url = sys.argv[1]

        # Optional: You could add custom headers through environment variables
        headers = {}
        if os.getenv("MCP_AUTH_TOKEN"):
            headers["Authorization"] = f"Bearer {os.getenv('MCP_AUTH_TOKEN')}"

        await client.connect_to_server(server_url, headers)
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    import sys

    asyncio.run(main())
