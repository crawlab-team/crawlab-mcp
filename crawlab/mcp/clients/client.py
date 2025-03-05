import sys
import asyncio
import json
import logging
import os
import time
from contextlib import AsyncExitStack
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.sse import sse_client

from ..llm_providers import create_llm_provider

load_dotenv()  # load environment variables from .env

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Create a detailed logger for MCP communication
mcp_logger = logging.getLogger("mcp.communication")
mcp_logger.setLevel(logging.DEBUG)


class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.stdio = None
        self.write = None
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.connection_type = "sse"  # Default connection type is now SSE
        self.tags = []
        self.tools = []

        # Initialize LLM provider
        logger.info("Initializing LLM provider")
        self.llm_provider = create_llm_provider()
        logger.info(f"Using LLM provider: {type(self.llm_provider).__name__}")

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

        try:
            # Connect using SSE transport
            if self.connection_type == "sse":
                logger.info("Using SSE transport for server connection")
                # Fix: sse_client returns a tuple of (read_stream, write_stream)
                read_stream, write_stream = await self.exit_stack.enter_async_context(
                    sse_client(server_url, headers=headers)
                )
                logger.debug("SSE streams established")
                
                # Set up the session properly with the read and write streams
                logger.debug("Creating ClientSession with SSE streams")
                self.session = await self.exit_stack.enter_async_context(
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
            tags_response = await self.session.call_tool("list_tags", {})
            
            # Parse the tags response correctly
            try:
                # Handle the case where the response might be structured differently
                if hasattr(tags_response, 'content') and isinstance(tags_response.content, str):
                    content_data = json.loads(tags_response.content)
                    if isinstance(content_data, dict) and "tags" in content_data:
                        self.tags = content_data["tags"]
                    else:
                        self.tags = content_data
                elif hasattr(tags_response, 'content') and isinstance(tags_response.content, list) and len(tags_response.content) > 0:
                    # Handle case where content is a list of message objects
                    text_content = tags_response.content[0].text
                    content_data = json.loads(text_content)
                    self.tags = content_data.get("tags", [])
                else:
                    # Fallback to empty list if we can't parse the response
                    logger.warning("Couldn't parse tags response format, using empty tags list")
                    self.tags = []
            except Exception as e:
                logger.error(f"Error parsing tags response: {str(e)}", exc_info=True)
                self.tags = []
                
            logger.info(f"Received {len(self.tags)} tags from server")
            logger.debug(f"Available tags: {self.tags}")
            
            # Initialize the LLM provider
            logger.info("Initializing LLM provider")
            await self.llm_provider.initialize()
            
            connection_time = time.time() - start_time
            logger.info(f"Server connection completed in {connection_time:.2f} seconds")
        except Exception as e:
            logger.error(f"Failed to connect to server: {str(e)}", exc_info=True)
            raise

    async def identify_user_intent(self, user_query: str) -> str:
        """Identify user intent to determine which tools to use"""
        logger.info("Identifying user intent")
        start_time = time.time()
        
        # Log the user query (but mask any sensitive information)
        masked_query = user_query
        if len(masked_query) > 100:
            masked_query = masked_query[:97] + "..."
        logger.debug(f"Processing user query: {masked_query}")

        # Create a system message that instructs the LLM to identify intent
        system_message = {
            "role": "system",
            "content": f"""You are an intent classifier for the Crawlab API.
Your task is to determine which API endpoints would be useful for answering the user's query.
Available API tags: {', '.join(self.tags)}

If the query requires using the API, respond with a JSON array of tool names that would be helpful.
If the query is generic and doesn't require API access, respond with "Generic".

Example 1:
User: "List all spiders in the system"
You: ["list_spiders"]

Example 2:
User: "What is the capital of France?"
You: "Generic"
""",
        }

        # Create a user message with the query
        user_message = {"role": "user", "content": user_query}

        # Call the LLM to identify intent
        logger.debug("Sending intent classification request to LLM")
        try:
            response = await self.llm_provider.chat_completion(
                messages=[system_message, user_message],
                temperature=0,  # Use low temperature for more deterministic results
            )
            
            intent = response["choices"][0]["message"]["content"].strip()
            logger.info(f"Intent identified: {intent}")
            
            intent_time = time.time() - start_time
            logger.debug(f"Intent identification completed in {intent_time:.2f} seconds")
            
            return intent
        except Exception as e:
            logger.error(f"Error identifying intent: {str(e)}", exc_info=True)
            # Default to generic intent on error
            return "Generic"

    async def process_query(self, query: str) -> str:
        """Process a query using LLM and available tools"""
        logger.info("Processing user query")
        start_time = time.time()
        
        messages = [{"role": "user", "content": query}]

        # Check if the provider supports tool calling
        has_tool_support = self.llm_provider.has_tool_support()
        logger.info(f"LLM provider tool support: {has_tool_support}")

        # Identify user intent
        intent = await self.identify_user_intent(query)
        logger.info(f"Identified intent: {intent}")

        if intent == "Generic" or not has_tool_support:
            logger.info("Using generic mode without tools")
            available_tools = None
            tool_choice = "none"
        else:
            try:
                tools = json.loads(intent)
                logger.info(f"Selected tools based on intent: {tools}")
                
                available_tools = [
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.inputSchema,
                        },
                    }
                    for tool in self.tools
                    if tool.name in tools
                ]
                
                logger.debug(f"Prepared {len(available_tools)} tools for LLM")
                tool_choice = "auto"
            except (json.JSONDecodeError, ValueError):
                # If intent isn't valid JSON or if there's any error, fall back to no tools
                logger.warning(f"Failed to parse tools from intent: {intent}")
                available_tools = None
                tool_choice = "none"

        # Initial LLM API call
        logger.info(f"Making initial LLM API call with {len(available_tools) if available_tools else 0} tools")
        llm_start_time = time.time()
        
        response = await self.llm_provider.chat_completion(
            messages=messages,
            tools=available_tools,
            tool_choice=tool_choice,
        )
        
        llm_time = time.time() - llm_start_time
        logger.debug(f"Initial LLM response received in {llm_time:.2f} seconds")

        # Process response and handle tool calls
        tool_results = []
        final_text = []

        response_message = response["choices"][0]["message"]
        content = response_message.get("content") or ""
        final_text.append(content)
        
        logger.debug(f"LLM response content length: {len(content)} characters")

        # Check if the response has tool calls and handle them if present
        if response_message.get("tool_calls"):
            tool_calls = response_message["tool_calls"]
            logger.info(f"LLM requested {len(tool_calls)} tool calls")
            
            for i, tool_call in enumerate(tool_calls):
                try:
                    function_name = tool_call["function"]["name"]
                    function_args = json.loads(tool_call["function"]["arguments"])
                    
                    logger.info(f"Processing tool call {i+1}/{len(tool_calls)}: {function_name}")
                    logger.debug(f"Tool arguments: {json.dumps(function_args)}")

                    # Execute tool call
                    tool_start_time = time.time()
                    logger.info(f"Executing tool: {function_name}")
                    
                    result = await self.session.call_tool(function_name, function_args)
                    
                    tool_time = time.time() - tool_start_time
                    logger.info(f"Tool {function_name} executed in {tool_time:.2f} seconds")
                    
                    # Log result summary (truncate if too large)
                    result_content = result.content
                    if len(result_content) > 200:
                        logger.debug(f"Tool result (truncated): {result_content[:197]}...")
                    else:
                        logger.debug(f"Tool result: {result_content}")
                    
                    tool_results.append({"call": function_name, "result": result})
                    final_text.append(f"[Calling tool {function_name} with args {function_args}]")

                    # Continue conversation with tool results
                    logger.debug("Adding tool results to conversation")
                    messages.append(
                        {
                            "role": "assistant",
                            "content": response_message.get("content"),
                            "tool_calls": response_message["tool_calls"],
                        }
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": result.content,
                        }
                    )

                    # Get next response from LLM
                    logger.info("Getting follow-up response from LLM with tool results")
                    follow_up_start = time.time()
                    
                    response = await self.llm_provider.chat_completion(messages=messages)
                    
                    follow_up_time = time.time() - follow_up_start
                    logger.debug(f"Follow-up LLM response received in {follow_up_time:.2f} seconds")
                    
                    final_text.append(response["choices"][0]["message"].get("content", ""))
                except Exception as e:
                    error_msg = f"Error executing tool {tool_call.get('function', {}).get('name', 'unknown')}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    final_text.append(f"[{error_msg}]")

                    # Add error message to conversation to let the LLM know there was an issue
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.get("id", "unknown"),
                            "content": f"Error: {str(e)}",
                        }
                    )

        total_time = time.time() - start_time
        logger.info(f"Query processing completed in {total_time:.2f} seconds")
        
        # Join all text parts with newlines
        return "\n".join(final_text)

    async def chat_loop(self):
        """Run an interactive chat loop with the user"""
        logger.info("Starting interactive chat loop")
        
        print("Welcome to the Crawlab MCP Client!")
        print("Type 'exit' or 'quit' to end the session.")
        print("Enter your query:")

        while True:
            try:
                # Get user input
                user_input = input("> ")
                if user_input.lower() in ["exit", "quit"]:
                    logger.info("User requested to exit chat loop")
                    break

                # Process the query
                logger.info("User submitted a new query")
                start_time = time.time()
                
                response = await self.process_query(user_input)
                
                processing_time = time.time() - start_time
                logger.info(f"Query processed in {processing_time:.2f} seconds")
                
                # Print the response
                print("\nResponse:")
                print(response)
                print()
            except KeyboardInterrupt:
                logger.info("Chat loop interrupted by user (KeyboardInterrupt)")
                break
            except Exception as e:
                logger.error(f"Error in chat loop: {str(e)}", exc_info=True)
                print(f"Error: {str(e)}")

        logger.info("Chat loop ended")

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()


async def main():
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
