import asyncio
import json
import logging
import os
import sys
import time
from contextlib import AsyncExitStack

from ..agents.task_planner import TaskPlanner
from ..llm_providers import create_llm_provider
from .client import MCPClient

# Configure logging
logger = logging.getLogger(__name__)


class ConsoleClient(MCPClient):
    """
    A client that extends MCPClient to provide console interaction functionality.
    This class handles the interactive chat loop, user input/output, and LLM-based processing.
    """
    
    def __init__(self):
        super().__init__()
        # Initialize LLM-related properties
        self.llm_provider = None
        self.exit_stack = AsyncExitStack()
        self.task_planner = None  # Will be initialized after connecting
        
        # Initialize LLM provider
        logger.info("Initializing LLM provider")
        self.llm_provider = create_llm_provider()
        logger.info(f"Using LLM provider: {type(self.llm_provider).__name__}")
    
    async def connect_to_server(self, server_url, headers=None):
        """
        Connect to the MCP server and initialize the LLM and task planner.
        Extends the MCPClient connect_to_server method.
        """
        connection_stack = await super().connect_to_server(server_url, headers)
        
        # Add the connection stack to our exit stack
        await self.exit_stack.enter_async_context(connection_stack)
        
        # Initialize LLM provider
        await self.initialize_llm()
        
        return True
    
    async def initialize_llm(self):
        """Initialize the LLM provider and task planner"""
        logger.info("Initializing LLM provider")
        await self.llm_provider.initialize()
        
        # Initialize task planner with the tools and session
        self.task_planner = TaskPlanner(self.llm_provider, self.tools, self.session)
        logger.info("Task planner initialized")

    async def chat_loop(self):
        """Run an interactive chat loop with the user"""
        logger.info("Starting interactive chat loop")
        print("Welcome to the Crawlab MCP client!")
        print("Type 'exit' or 'quit' to end the conversation.")
        print("Type 'help' for a list of available commands.")
        print("\nThis client now features advanced task planning for complex queries!")
        print(
            "Complex queries that require multiple steps will be automatically broken down into a plan."
        )

        while True:
            try:
                # Get user input
                user_input = await self._read_user_input()

                # Check for exit commands
                if user_input.lower() in ["exit", "quit"]:
                    print("Exiting chat...")
                    break

                # Handle help command
                if user_input.lower() == "help":
                    self._print_help()
                    continue

                # Process the query
                response = await self.process_query(user_input)

                # Print response with formatting
                print("\n" + "-" * 80)
                print(response)
                print("-" * 80 + "\n")

            except asyncio.CancelledError:
                logger.info("Chat loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in chat loop: {str(e)}", exc_info=True)
                print(f"An error occurred: {str(e)}")

    @staticmethod
    def _print_help():
        """Print help information for the user"""
        print("\n" + "-" * 80)
        print("CRAWLAB MCP CLIENT HELP")
        print("-" * 80)
        print("Available commands:")
        print("  help - Show this help message")
        print("  exit/quit - Exit the client")
        print("\nQuery Processing Features:")
        print("  - Simple queries: Direct processing with appropriate tools")
        print("  - Complex queries: Automatic task planning and step-by-step execution")
        print("  - The system will automatically determine whether to use task planning")
        print("\nExample complex queries:")
        print("  - Find all spiders with status 'Running' and show their statistics")
        print("  - Compare memory usage between all nodes and identify the one with highest load")
        print("  - Get all tasks for project 'X' and calculate average runtime")
        print("-" * 80 + "\n")

    @staticmethod
    async def _read_user_input():
        """Read user input asynchronously"""
        # Create a future to hold the result
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        # Define a function to get input and set the future result
        def get_input():
            try:
                user_input = input("> ")
                loop.call_soon_threadsafe(future.set_result, user_input)
            except Exception as e:
                logger.error(f"Error getting user input: {str(e)}", exc_info=True)
                loop.call_soon_threadsafe(future.set_exception, e)

        # Run the input function in a thread
        await loop.run_in_executor(None, get_input)

        # Wait for the result
        try:
            return await future
        except Exception as e:
            logger.error(f"Error in user input: {str(e)}")
            return f"An error occurred: {str(e)}"
    
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
Your task is to determine whether and what tools would be useful for answering the user's query.
You should only use tools available in the API. 
If no tools are needed or not exist in the available tools, respond with "Generic".

Available tools:
{json.dumps([t.model_dump() for t in self.tool_items])}

If the query requires using the API, respond with a JSON array of tool names that would be helpful.
If the query is generic and doesn't require API access, respond with "Generic".

Example 1:
User: "List all spiders in the system"
You: ["GET_spiders"]

Example 2:
User: "How many nodes are available?"
You: ["GET_nodes"]

Example 3:
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
        """Process a query using LLM and available tools with task planning for complex queries"""
        logger.info("Processing user query")

        # Check if task planning is available and should be used
        use_planning = await self._should_use_planning(query)

        if use_planning and self.task_planner is not None:
            logger.info("Using task planning for complex query")
            try:
                # Create a plan for the query
                plan = await self.task_planner.create_plan(query)

                # Execute the plan
                return await self.task_planner.execute_plan(query, plan)
            except Exception as e:
                logger.error(f"Error in task planning: {str(e)}", exc_info=True)
                # Fall back to standard processing if planning fails
                logger.info("Falling back to standard processing due to planning error")
                return await self._process_query_standard(query)
        else:
            logger.info("Using standard query processing")
            return await self._process_query_standard(query)

    async def _should_use_planning(self, query: str) -> bool:
        """Determine if a query is complex enough to warrant task planning"""
        # If planner isn't initialized, can't use planning
        if self.task_planner is None:
            return False

        system_message = {
            "role": "system",
            "content": """You are a query analyzer. Your job is to determine if a user query needs a multi-step task planning approach. 
            
            A query needs planning if it:
            1. Requires multiple sequential API calls (even simple ones like 'list X and then do Y with the results')
            2. Needs to process data from one step to use in another step (e.g., finding an item in a list and then performing an action with it)
            3. Has multiple distinct sub-tasks that logically build on each other (e.g., get information, then use that information)
            4. Involves comparing or combining data from different sources
            5. Requires conditional logic based on intermediate results
            
            Examples that need planning:
            - "List all spiders and run the first one" (requires listing spiders, then selecting one, then running it)
            - "Show me the user with the most orders" (requires fetching users, fetching orders, correlating them, finding maximum)
            
            Respond with only "true" if the query requires multiple steps or processing results from one step in another, or "false" if it can be handled by a single tool call or response.""",
        }

        user_message = {"role": "user", "content": query}

        try:
            response = await self.llm_provider.chat_completion(
                messages=[system_message, user_message],
                temperature=0,
            )

            result = response["choices"][0]["message"]["content"].strip().lower()
            is_complex = result == "true"

            logger.info(f"Query complexity analysis: {is_complex}")
            return is_complex
        except Exception as e:
            logger.error(f"Error determining query complexity: {str(e)}")
            return False  # Default to standard processing on error

    async def _process_query_standard(self, query: str) -> str:
        """Original query processing method without task planning"""
        logger.info("Using standard query processing")
        start_time = time.time()

        # Add system message to explain parameter information tools
        messages = [
            {
                "role": "system",
                "content": (
                    "You have access to tools that provide information about required parameters and enum values. "
                    "If you need to understand what parameters are required or what enum values are available for a tool, "
                    "you can use the list_parameter_info tool. To get schemas for all tools, use get_tool_schemas."
                ),
            },
            {"role": "user", "content": query},
        ]

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

                # Get detailed schema information for selected tools
                detailed_tools = []
                for tool in self.tools:
                    if tool.name in tools:
                        # Try to get detailed schema information if available
                        schema = tool.inputSchema
                        print(tool)

                        # Ensure the schema has proper "required" fields and enum information
                        if isinstance(schema, dict) and schema.get("properties"):
                            # If schema has required fields, ensure they're properly highlighted
                            # Otherwise, AI models might not understand which fields are required
                            if "required" in schema:
                                for req_field in schema["required"]:
                                    if req_field in schema.get("properties", {}):
                                        prop = schema["properties"][req_field]
                                        # Explicitly mark required fields in description
                                        desc = prop.get("description", "")
                                        if not desc.startswith("[REQUIRED]"):
                                            prop["description"] = f"[REQUIRED] {desc}"

                        # Prepare the tool definition with enhanced schema
                        print(schema)
                        detailed_tools.append(
                            {
                                "type": "function",
                                "function": {
                                    "name": tool.name,
                                    "description": tool.description,
                                    "parameters": schema,
                                },
                            }
                        )

                available_tools = detailed_tools
                logger.debug(
                    f"Prepared {len(available_tools)} tools for LLM with enhanced schema information"
                )
                tool_choice = "auto"
            except (json.JSONDecodeError, ValueError):
                # If intent isn't valid JSON or if there's any error, fall back to no tools
                logger.warning(f"Failed to parse tools from intent: {intent}")
                available_tools = None
                tool_choice = "none"

        # Initial LLM API call
        logger.info(
            f"Making initial LLM API call with {len(available_tools) if available_tools else 0} tools"
        )
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

                    logger.info(f"Processing tool call {i + 1}/{len(tool_calls)}: {function_name}")
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
    
    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()


async def main():
    """
    Main entry point for the console client interface.
    This runs an interactive console session with the MCP server.
    """
    # Create a console client instance
    client = ConsoleClient()
    try:
        # Check for command line arguments
        if len(sys.argv) < 2:
            print("Usage: python -m crawlab_mcp.clients.console_client <server_url>")
            sys.exit(1)
            
        server_url = sys.argv[1]

        # Optional: You could add custom headers through environment variables
        headers = {}
        if os.getenv("MCP_AUTH_TOKEN"):
            headers["Authorization"] = f"Bearer {os.getenv('MCP_AUTH_TOKEN')}"

        # Connect to the server and start the chat loop
        print(f"Connecting to MCP server at {server_url}...")
        await client.connect_to_server(server_url, headers)
        await client.chat_loop()
    except Exception as e:
        print(f"Error: {str(e)}")
        logger.error(f"Error in main: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        # Clean up resources
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main()) 