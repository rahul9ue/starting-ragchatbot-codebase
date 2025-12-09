from typing import Any

import anthropic


class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    # Maximum number of sequential tool calling rounds
    MAX_TOOL_ROUNDS = 2

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to comprehensive tools for course information.

Tool Usage Guidelines:
- **search_course_content**: Use for questions about specific course content or detailed educational materials
- **get_course_outline**: Use for questions about course structure, lesson list, or course overview
- **Multi-round tool usage**: You may use up to 2 tool calls per query to:
  * First discover course information (get_course_outline), then search content (search_course_content)
  * Search multiple courses to compare information
  * Refine searches with additional context
- **Strategic tool usage**: Only use additional tool calls when they add significant value
- Synthesize all tool results into coherent, accurate responses
- If tool yields no results, state this clearly without offering alternatives

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without using tools
- **Course content questions**: Use search_course_content tool first, then answer
- **Course outline/structure questions**: Use get_course_outline tool to provide the course title, course link, and complete lesson list with lesson numbers and titles
- **Complex queries**: Consider using get_course_outline first to verify course details, then search_course_content for specific content
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, tool usage explanations, or question-type analysis
 - Do not mention "based on the search results" or "using the tool" or "in the first/second search"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        # Pre-build base API parameters
        self.base_params = {"model": self.model, "temperature": 0, "max_tokens": 800}

    def generate_response(
        self,
        query: str,
        conversation_history: str | None = None,
        tools: list | None = None,
        tool_manager=None,
        max_tool_rounds: int | None = None,
    ) -> str:
        """
        Generate AI response with multi-round tool usage support.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools
            max_tool_rounds: Override default MAX_TOOL_ROUNDS (default: 2)

        Returns:
            Generated response as string
        """
        max_rounds = max_tool_rounds if max_tool_rounds is not None else self.MAX_TOOL_ROUNDS

        # Build system prompt with conversation history
        system_content = self._build_system_prompt(conversation_history)

        # Initialize message array
        messages = [{"role": "user", "content": query}]

        # Execute tool loop if tools are available
        if tools and tool_manager:
            return self._execute_tool_loop(
                messages, system_content, tools, tool_manager, max_rounds
            )
        else:
            # No tools available - direct response
            response = self._make_api_call(messages, system_content, tools=None)
            return self._extract_text_response(response)

    def _build_system_prompt(self, conversation_history: str | None) -> str:
        """Build system prompt with conversation history if available."""
        if conversation_history:
            return f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
        return self.SYSTEM_PROMPT

    def _make_api_call(self, messages: list, system_content: str, tools: list | None):
        """Make API call to Claude with consistent parameters."""
        api_params = {**self.base_params, "messages": messages, "system": system_content}

        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}

        return self.client.messages.create(**api_params)

    def _execute_tool_loop(
        self, messages: list, system_content: str, tools: list, tool_manager, max_rounds: int
    ) -> str:
        """
        Execute the multi-round tool calling loop.

        Supports up to max_rounds sequential tool calls, terminating early if:
        - Claude provides a final text response (stop_reason != "tool_use")
        - Tool execution fails
        - Max rounds reached

        Args:
            messages: Conversation messages array
            system_content: System prompt with history
            tools: Tool definitions
            tool_manager: Tool executor
            max_rounds: Maximum tool rounds allowed

        Returns:
            Final response text
        """
        for round_num in range(1, max_rounds + 1):
            # Make API call with tools available
            response = self._make_api_call(messages, system_content, tools)

            # TERMINATION CHECK #1: Claude provided final answer
            if response.stop_reason != "tool_use":
                return self._extract_text_response(response)

            # Add Claude's tool request to conversation
            messages.append({"role": "assistant", "content": response.content})

            # Execute tool(s)
            tool_results = self._execute_all_tools(response, tool_manager)

            # TERMINATION CHECK #2: Tool execution error
            if tool_results.get("error"):
                return self._format_tool_error(tool_results["error"])

            # Add tool results to conversation
            messages.append({"role": "user", "content": tool_results["results"]})

            # TERMINATION CHECK #3: Max rounds reached
            if round_num >= max_rounds:
                break

        # Final synthesis call without tools
        final_response = self._make_api_call(messages, system_content, tools=None)
        return self._extract_text_response(final_response)

    def _execute_all_tools(self, response, tool_manager) -> dict:
        """
        Execute all tool calls in response and return structured results.

        Returns:
            Dict with keys:
            - results: List of tool_result dicts for API
            - error: Error message if any tool failed, None otherwise
        """
        tool_results = []

        for content_block in response.content:
            if content_block.type == "tool_use":
                try:
                    tool_output = tool_manager.execute_tool(
                        content_block.name, **content_block.input
                    )

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": tool_output,
                        }
                    )

                except Exception as e:
                    error_msg = f"Tool {content_block.name} failed: {str(e)}"
                    return {"results": [], "error": error_msg}

        return {"results": tool_results, "error": None}

    def _extract_text_response(self, response) -> str:
        """Extract text from Claude response, handling various content structures."""
        if not response.content:
            return "I apologize, but I encountered an issue processing your request."

        text_parts = []
        for block in response.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)

        return " ".join(text_parts) if text_parts else "No response generated."

    def _format_tool_error(self, error: str) -> str:
        """Format tool error for user display."""
        return f"I encountered an error while searching the course materials: {error}"

    def _handle_tool_execution(self, initial_response, base_params: dict[str, Any], tool_manager):
        """
        Handle execution of tool calls and get follow-up response.

        Args:
            initial_response: The response containing tool use requests
            base_params: Base API parameters
            tool_manager: Manager to execute tools

        Returns:
            Final response text after tool execution
        """
        # Start with existing messages
        messages = base_params["messages"].copy()

        # Add AI's tool use response
        messages.append({"role": "assistant", "content": initial_response.content})

        # Execute all tool calls and collect results
        tool_results = []
        for content_block in initial_response.content:
            if content_block.type == "tool_use":
                tool_result = tool_manager.execute_tool(content_block.name, **content_block.input)

                tool_results.append(
                    {"type": "tool_result", "tool_use_id": content_block.id, "content": tool_result}
                )

        # Add tool results as single message
        if tool_results:
            messages.append({"role": "user", "content": tool_results})

        # Prepare final API call without tools
        final_params = {**self.base_params, "messages": messages, "system": base_params["system"]}

        # Get final response
        final_response = self.client.messages.create(**final_params)

        # Handle different response content structures
        if not final_response.content:
            return "I apologize, but I encountered an issue processing your request."

        # Extract text from content blocks
        text_parts = []
        for block in final_response.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)

        return " ".join(text_parts) if text_parts else "No response generated."
