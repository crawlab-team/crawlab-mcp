import json
import logging
import time
from typing import Any, Dict, List, Tuple


class TaskPlanner:
    """
    Responsible for planning and executing a sequence of tasks to fulfill complex user queries.
    Uses Chain of Thought and ReAct-style planning to break down complex queries into steps.
    """

    def __init__(self, llm_provider, tools, session):
        self.llm_provider = llm_provider
        self.tools = tools
        self.session = session
        self.logger = logging.getLogger("mcp.planner")
        self.logger.setLevel(logging.DEBUG)

    async def create_plan(self, query: str) -> Dict[str, Any]:
        """
        Create a plan to fulfill the user query by breaking it down into steps.
        Returns a structured plan with steps, required tools, and reasoning.
        """
        self.logger.info("Creating execution plan for query")

        system_message = {
            "role": "system",
            "content": """You are a sophisticated planning agent for the Crawlab API.
Given a user query, your task is to:
1. Break down the query into logical steps that need to be executed sequentially
2. For each step, identify the specific tools needed from the available API
3. Provide a clear reasoning for each step
4. Return a structured JSON plan

Available API tools: {tool_names}

The plan should have this structure:
{{
  "thought": "Your detailed analysis of the query and overall approach",
  "steps": [
    {{
      "description": "Clear description of this step",
      "reasoning": "Why this step is necessary",
      "tools": ["tool1", "tool2"] or [] if no tools needed,
      "requires_previous_step_result": true/false
    }},
    ...more steps...
  ]
}}

Always use a step-by-step approach, especially for complex queries that require multiple API calls or data processing steps.""",
        }

        # Format the system message with available tools
        tool_names = [tool.name for tool in self.tools]
        system_message["content"] = system_message["content"].format(
            tool_names=", ".join(tool_names)
        )

        user_message = {"role": "user", "content": query}

        # Call the LLM to create a plan
        try:
            response = await self.llm_provider.chat_completion(
                messages=[system_message, user_message],
                temperature=0.2,  # Low but not zero to allow some creativity
            )

            plan_text = response["choices"][0]["message"]["content"].strip()

            # Extract the JSON plan from the response
            # First try to parse the entire response as JSON
            try:
                plan = json.loads(plan_text)
            except json.JSONDecodeError:
                # If that fails, try to extract JSON from markdown code blocks
                import re

                json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", plan_text)
                if json_match:
                    try:
                        plan = json.loads(json_match.group(1))
                    except json.JSONDecodeError:
                        raise ValueError("Could not parse plan JSON from LLM response")
                else:
                    raise ValueError("Could not extract JSON plan from LLM response")

            self.logger.info(f"Created plan with {len(plan.get('steps', []))} steps")
            self.logger.debug(f"Plan: {json.dumps(plan, indent=2)}")

            return plan

        except Exception as e:
            self.logger.error(f"Error creating plan: {str(e)}", exc_info=True)
            # Return a minimal default plan on error
            return {
                "thought": f"Error creating plan: {str(e)}",
                "steps": [
                    {
                        "description": "Process query directly without planning",
                        "reasoning": "Error occurred during planning",
                        "tools": [],
                        "requires_previous_step_result": False,
                    }
                ],
            }

    async def execute_plan(self, query: str, plan: Dict[str, Any]) -> str:
        """
        Execute the plan by processing each step sequentially.
        Returns the final response that addresses the user's query.
        """
        self.logger.info(f"Executing plan with {len(plan.get('steps', []))} steps")

        # Initialize variables to track execution
        steps = plan.get("steps", [])
        messages = [{"role": "user", "content": query}]
        final_text = []
        step_results = []  # Store results from each step for potential use in subsequent steps

        # Add the plan thought as context
        if "thought" in plan:
            messages.append({"role": "assistant", "content": f"Planning: {plan['thought']}"})

        # Execute each step in the plan
        for i, step in enumerate(steps):
            step_num = i + 1
            self.logger.info(f"Executing step {step_num}/{len(steps)}: {step['description']}")

            # Prepare context for this step
            step_context = f"Step {step_num}: {step['description']}\nReasoning: {step['reasoning']}"

            # Add the step context to messages
            messages.append({"role": "assistant", "content": step_context})

            # Add previous step results to context if required
            if step.get("requires_previous_step_result", False) and step_results:
                prev_results = "\n\n".join(
                    [f"Result from step {j + 1}: {result}" for j, result in enumerate(step_results)]
                )
                messages.append(
                    {"role": "assistant", "content": f"Previous results:\n{prev_results}"}
                )

            # Prepare tools for this step
            step_tools = step.get("tools", [])
            if step_tools:
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
                    if tool.name in step_tools
                ]
                tool_choice = "auto"
            else:
                available_tools = None
                tool_choice = "none"

            # Call the LLM for this step
            step_start_time = time.time()
            try:
                response = await self.llm_provider.chat_completion(
                    messages=messages,
                    tools=available_tools,
                    tool_choice=tool_choice,
                )

                response_message = response["choices"][0]["message"]
                content = response_message.get("content") or ""

                # Process tool calls if present
                tool_results = []
                if response_message.get("tool_calls"):
                    # Process tool calls using a helper method
                    step_text, tool_outputs = await self._process_tool_calls(
                        response_message, messages.copy()
                    )
                    final_text.append(f"[Step {step_num}] {step['description']}")
                    final_text.extend(step_text)

                    # Combine all tool outputs for this step
                    step_result = "\n".join(tool_outputs)
                else:
                    # No tool calls, just use the content
                    final_text.append(f"[Step {step_num}] {step['description']}")
                    final_text.append(content)
                    step_result = content

                # Store the result of this step
                step_results.append(step_result)

                # Update messages with the step's outcome
                messages.append({"role": "assistant", "content": step_result})

                step_time = time.time() - step_start_time
                self.logger.info(f"Step {step_num} completed in {step_time:.2f} seconds")

            except Exception as e:
                error_msg = f"Error executing step {step_num}: {str(e)}"
                self.logger.error(error_msg, exc_info=True)
                final_text.append(f"[Step {step_num} Error] {error_msg}")
                messages.append(
                    {"role": "assistant", "content": f"Error in step {step_num}: {str(e)}"}
                )

        # Generate final summary response
        self.logger.info("Generating final response")
        summary_message = {
            "role": "system",
            "content": """You are the final summarizer. Based on all the steps executed and their results, 
            provide a comprehensive and cohesive answer to the user's original query. 
            Focus on clarity and completeness.""",
        }

        try:
            final_response = await self.llm_provider.chat_completion(
                messages=messages + [summary_message],
                temperature=0.3,  # Slightly higher temp for more natural summary
            )

            summary = final_response["choices"][0]["message"]["content"]
            final_text.append("\n--- Summary ---")
            final_text.append(summary)

        except Exception as e:
            error_msg = f"Error generating summary: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            final_text.append(f"[Summary Error] {error_msg}")

        return "\n\n".join(final_text)

    async def _process_tool_calls(
        self, response_message: Dict[str, Any], current_messages: List[Dict[str, Any]]
    ) -> Tuple[List[str], List[str]]:
        """
        Process tool calls from the LLM response and return the results.
        Returns a tuple of (text_for_user, tool_outputs)
        """
        tool_calls = response_message["tool_calls"]
        text_parts = []
        tool_outputs = []

        for tool_call in tool_calls:
            try:
                function_name = tool_call["function"]["name"]
                function_args = json.loads(tool_call["function"]["arguments"])

                self.logger.info(f"Calling tool: {function_name}")
                self.logger.debug(f"Tool arguments: {json.dumps(function_args)}")

                # Execute the tool call
                result = await self.session.call_tool(function_name, function_args)

                text_parts.append(f"[Tool Call] {function_name}({json.dumps(function_args)})")
                text_parts.append(f"[Tool Result] {result.content}")
                tool_outputs.append(f"{function_name} result: {result.content}")

                # Add tool call and result to messages
                current_messages.append(
                    {
                        "role": "assistant",
                        "content": response_message.get("content"),
                        "tool_calls": [tool_call],  # Just this tool call
                    }
                )
                current_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": result.content,
                    }
                )

                # Get interpretative response from LLM
                interpret_response = await self.llm_provider.chat_completion(
                    messages=current_messages
                )

                interpretation = interpret_response["choices"][0]["message"].get("content", "")
                if interpretation:
                    text_parts.append(f"[Interpretation] {interpretation}")
                    tool_outputs.append(f"Interpretation: {interpretation}")

            except Exception as e:
                error_msg = f"Error with tool {tool_call.get('function', {}).get('name', 'unknown')}: {str(e)}"
                self.logger.error(error_msg, exc_info=True)
                text_parts.append(f"[Tool Error] {error_msg}")
                tool_outputs.append(f"Error: {error_msg}")

        return text_parts, tool_outputs
