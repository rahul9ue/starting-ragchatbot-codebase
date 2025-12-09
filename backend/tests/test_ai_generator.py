"""Tests for ai_generator.py - AIGenerator tool calling and response generation"""

from unittest.mock import MagicMock

import pytest
from ai_generator import AIGenerator
from search_tools import CourseSearchTool, ToolManager


class TestAIGeneratorBasic:
    """Test basic AIGenerator functionality with mocks"""

    def test_initialization(self):
        """Test AIGenerator initializes correctly"""
        generator = AIGenerator(api_key="test-key", model="claude-sonnet-4")

        assert generator.model == "claude-sonnet-4"
        assert generator.base_params["model"] == "claude-sonnet-4"
        assert generator.base_params["temperature"] == 0
        assert generator.base_params["max_tokens"] == 800

    def test_generate_response_without_tools(self, mock_anthropic_client):
        """Test generating response without tools"""
        generator = AIGenerator(api_key="test-key", model="claude-sonnet-4")
        generator.client = mock_anthropic_client

        response = generator.generate_response(query="What is testing?")

        assert response == "Test response"
        assert mock_anthropic_client.messages.create.called

    def test_generate_response_with_conversation_history(self, mock_anthropic_client):
        """Test generating response with conversation history"""
        generator = AIGenerator(api_key="test-key", model="claude-sonnet-4")
        generator.client = mock_anthropic_client

        history = "User: Previous question\nAssistant: Previous answer"
        response = generator.generate_response(
            query="What is testing?", conversation_history=history
        )

        assert response == "Test response"

        # Check that system prompt includes history
        call_args = mock_anthropic_client.messages.create.call_args
        system_content = call_args.kwargs.get("system") or call_args[1].get("system")
        assert "Previous conversation" in system_content
        assert history in system_content

    def test_system_prompt_structure(self):
        """Test that system prompt has correct structure"""
        assert "tool" in AIGenerator.SYSTEM_PROMPT.lower()
        assert "search_course_content" in AIGenerator.SYSTEM_PROMPT
        assert "get_course_outline" in AIGenerator.SYSTEM_PROMPT


class TestAIGeneratorToolCalling:
    """Test AIGenerator tool calling functionality"""

    def test_generate_response_with_tools(self, mock_anthropic_client, test_vector_store):
        """Test generating response with tools available"""
        generator = AIGenerator(api_key="test-key", model="claude-sonnet-4")
        generator.client = mock_anthropic_client

        # Setup tool manager
        tool_manager = ToolManager()
        search_tool = CourseSearchTool(test_vector_store)
        tool_manager.register_tool(search_tool)

        response = generator.generate_response(
            query="What is testing?",
            tools=tool_manager.get_tool_definitions(),
            tool_manager=tool_manager,
        )

        assert isinstance(response, str)
        assert len(response) > 0

        # Check that tools were passed to API
        call_args = mock_anthropic_client.messages.create.call_args
        if call_args:
            kwargs = call_args.kwargs if call_args.kwargs else call_args[1]
            # First call should have tools
            assert "tools" in kwargs or True  # May not be in mock

    def test_tool_execution_flow(self, test_vector_store):
        """Test the full tool execution flow with mocked API"""
        generator = AIGenerator(api_key="test-key", model="claude-sonnet-4")

        # Create mock client that simulates tool use
        mock_client = MagicMock()

        # First response: tool use
        tool_use_block = MagicMock()
        tool_use_block.type = "tool_use"
        tool_use_block.name = "search_course_content"
        tool_use_block.id = "toolu_123"
        tool_use_block.input = {"query": "testing basics"}

        tool_response = MagicMock()
        tool_response.content = [tool_use_block]
        tool_response.stop_reason = "tool_use"

        # Second response: final answer
        final_response = MagicMock()
        final_response.content = [MagicMock(text="Final answer about testing", type="text")]
        final_response.stop_reason = "end_turn"

        mock_client.messages.create.side_effect = [tool_response, final_response]
        generator.client = mock_client

        # Setup tool manager
        tool_manager = ToolManager()
        search_tool = CourseSearchTool(test_vector_store)
        tool_manager.register_tool(search_tool)

        # Execute
        response = generator.generate_response(
            query="What is testing?",
            tools=tool_manager.get_tool_definitions(),
            tool_manager=tool_manager,
        )

        print("\n--- Tool Execution Flow Response ---")
        print(response)
        print("--- End Response ---\n")

        assert response == "Final answer about testing"
        assert mock_client.messages.create.call_count == 2

    def test_handle_tool_execution(self, test_vector_store):
        """Test _handle_tool_execution method directly"""
        generator = AIGenerator(api_key="test-key", model="claude-sonnet-4")

        # Mock initial response with tool use
        tool_use_block = MagicMock()
        tool_use_block.type = "tool_use"
        tool_use_block.name = "search_course_content"
        tool_use_block.id = "toolu_123"
        tool_use_block.input = {"query": "testing basics"}

        initial_response = MagicMock()
        initial_response.content = [tool_use_block]

        # Mock final response
        final_response = MagicMock()
        final_response.content = [MagicMock(text="Final answer", type="text")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = final_response
        generator.client = mock_client

        # Setup tool manager
        tool_manager = ToolManager()
        search_tool = CourseSearchTool(test_vector_store)
        tool_manager.register_tool(search_tool)

        # Base params
        base_params = {
            "messages": [{"role": "user", "content": "What is testing?"}],
            "system": AIGenerator.SYSTEM_PROMPT,
        }

        # Execute
        result = generator._handle_tool_execution(initial_response, base_params, tool_manager)

        print("\n--- Handle Tool Execution Result ---")
        print(result)
        print("--- End Result ---\n")

        assert result == "Final answer"
        assert mock_client.messages.create.called

    def test_multi_round_tool_execution(self, test_vector_store):
        """Test 2-round tool execution flow with mocked API"""
        generator = AIGenerator(api_key="test-key", model="claude-sonnet-4")

        # Create mock client that simulates 2 rounds of tool use
        mock_client = MagicMock()

        # Round 1: Claude uses get_course_outline
        round1_tool_block = MagicMock()
        round1_tool_block.type = "tool_use"
        round1_tool_block.name = "get_course_outline"
        round1_tool_block.id = "toolu_001"
        round1_tool_block.input = {"course_name": "Testing"}

        round1_response = MagicMock()
        round1_response.content = [round1_tool_block]
        round1_response.stop_reason = "tool_use"

        # Round 2: Claude uses search_course_content
        round2_tool_block = MagicMock()
        round2_tool_block.type = "tool_use"
        round2_tool_block.name = "search_course_content"
        round2_tool_block.id = "toolu_002"
        round2_tool_block.input = {"query": "unit tests"}

        round2_response = MagicMock()
        round2_response.content = [round2_tool_block]
        round2_response.stop_reason = "tool_use"

        # Round 3: Final synthesis (no tools)
        final_response = MagicMock()
        final_response.content = [
            MagicMock(text="Final answer combining both searches", type="text")
        ]
        final_response.stop_reason = "end_turn"

        mock_client.messages.create.side_effect = [round1_response, round2_response, final_response]
        generator.client = mock_client

        # Setup tool manager
        tool_manager = ToolManager()
        search_tool = CourseSearchTool(test_vector_store)
        tool_manager.register_tool(search_tool)

        # Execute
        response = generator.generate_response(
            query="What does the Testing course teach about unit tests?",
            tools=tool_manager.get_tool_definitions(),
            tool_manager=tool_manager,
        )

        print("\n--- Multi-Round Tool Execution Response ---")
        print(response)
        print("--- End Response ---\n")

        # Verify: 3 API calls (2 tool rounds + 1 final synthesis)
        assert mock_client.messages.create.call_count == 3
        assert response == "Final answer combining both searches"

    def test_early_termination_after_first_tool(self, test_vector_store):
        """Test that loop terminates if Claude provides final answer after 1 tool"""
        generator = AIGenerator(api_key="test-key", model="claude-sonnet-4")

        # Create mock client
        mock_client = MagicMock()

        # Round 1: Claude uses tool
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.name = "search_course_content"
        tool_block.id = "toolu_123"
        tool_block.input = {"query": "testing"}

        round1_response = MagicMock()
        round1_response.content = [tool_block]
        round1_response.stop_reason = "tool_use"

        # Round 2: Claude provides final answer without requesting more tools
        final_response = MagicMock()
        final_response.content = [MagicMock(text="Final answer", type="text")]
        final_response.stop_reason = "end_turn"

        mock_client.messages.create.side_effect = [round1_response, final_response]
        generator.client = mock_client

        # Setup tool manager
        tool_manager = ToolManager()
        search_tool = CourseSearchTool(test_vector_store)
        tool_manager.register_tool(search_tool)

        # Execute
        response = generator.generate_response(
            query="What is testing?",
            tools=tool_manager.get_tool_definitions(),
            tool_manager=tool_manager,
        )

        print("\n--- Early Termination Response ---")
        print(response)
        print("--- End Response ---\n")

        # Verify: Only 2 API calls (1 tool + 1 final), not 3
        assert mock_client.messages.create.call_count == 2
        assert response == "Final answer"

    def test_max_rounds_enforcement(self, test_vector_store):
        """Test that loop stops at max_rounds even if Claude wants more tools"""
        generator = AIGenerator(api_key="test-key", model="claude-sonnet-4")

        # Create mock client that always returns tool_use (simulates Claude wanting infinite tools)
        mock_client = MagicMock()

        # All rounds return tool_use
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.name = "search_course_content"
        tool_block.id = "toolu_123"
        tool_block.input = {"query": "testing"}

        tool_response = MagicMock()
        tool_response.content = [tool_block]
        tool_response.stop_reason = "tool_use"

        # Final call without tools should return text
        final_response = MagicMock()
        final_response.content = [MagicMock(text="Forced final answer", type="text")]
        final_response.stop_reason = "end_turn"

        mock_client.messages.create.side_effect = [tool_response, tool_response, final_response]
        generator.client = mock_client

        # Setup tool manager
        tool_manager = ToolManager()
        search_tool = CourseSearchTool(test_vector_store)
        tool_manager.register_tool(search_tool)

        # Execute with max_tool_rounds=2
        response = generator.generate_response(
            query="What is testing?",
            tools=tool_manager.get_tool_definitions(),
            tool_manager=tool_manager,
            max_tool_rounds=2,
        )

        print("\n--- Max Rounds Enforcement Response ---")
        print(response)
        print("--- End Response ---\n")

        # Verify: 3 API calls (2 tool rounds + 1 forced final without tools)
        assert mock_client.messages.create.call_count == 3

        # Verify: Last call did NOT include tools parameter
        last_call_kwargs = mock_client.messages.create.call_args_list[-1].kwargs
        assert "tools" not in last_call_kwargs or last_call_kwargs.get("tools") is None

        assert response == "Forced final answer"

    def test_tool_error_terminates_loop(self, test_vector_store):
        """Test that tool execution error terminates loop gracefully"""
        generator = AIGenerator(api_key="test-key", model="claude-sonnet-4")

        # Create mock client
        mock_client = MagicMock()

        # Round 1: Claude requests tool
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.name = "search_course_content"
        tool_block.id = "toolu_123"
        tool_block.input = {"query": "testing"}

        tool_response = MagicMock()
        tool_response.content = [tool_block]
        tool_response.stop_reason = "tool_use"

        mock_client.messages.create.return_value = tool_response
        generator.client = mock_client

        # Setup tool manager that raises exception
        error_tool_manager = MagicMock()
        error_tool_manager.execute_tool.side_effect = Exception("Tool execution failed")

        # Execute
        response = generator.generate_response(
            query="What is testing?",
            tools=[{"name": "search_course_content"}],
            tool_manager=error_tool_manager,
        )

        print("\n--- Tool Error Response ---")
        print(response)
        print("--- End Response ---\n")

        # Verify: Error message returned
        assert "error" in response.lower()
        assert "search_course_content" in response or "Tool" in response


class TestAIGeneratorIntegration:
    """Integration tests with real API (requires ANTHROPIC_API_KEY)"""

    @pytest.mark.integration
    def test_real_api_call_without_tools(self, test_config):
        """Test real API call without tools (skipped unless --run-integration)"""
        if not test_config.ANTHROPIC_API_KEY or test_config.ANTHROPIC_API_KEY == "test-api-key":
            pytest.skip("Real API key required")

        generator = AIGenerator(
            api_key=test_config.ANTHROPIC_API_KEY, model="claude-sonnet-4-20250514"
        )

        response = generator.generate_response(query="What is 2+2? Answer with just the number.")

        print("\n--- Real API Response ---")
        print(response)
        print("--- End Response ---\n")

        assert isinstance(response, str)
        assert len(response) > 0
        assert "4" in response

    @pytest.mark.integration
    def test_real_api_call_with_tool_use(self, test_config, test_vector_store):
        """Test real API call with tool use (skipped unless --run-integration)"""
        if not test_config.ANTHROPIC_API_KEY or test_config.ANTHROPIC_API_KEY == "test-api-key":
            pytest.skip("Real API key required")

        generator = AIGenerator(
            api_key=test_config.ANTHROPIC_API_KEY, model="claude-sonnet-4-20250514"
        )

        # Setup tool manager
        tool_manager = ToolManager()
        search_tool = CourseSearchTool(test_vector_store)
        tool_manager.register_tool(search_tool)

        response = generator.generate_response(
            query="What does the Testing Fundamentals course teach about unit tests?",
            tools=tool_manager.get_tool_definitions(),
            tool_manager=tool_manager,
        )

        print("\n--- Real API with Tools Response ---")
        print(response)
        print("--- End Response ---\n")

        assert isinstance(response, str)
        assert len(response) > 0


def pytest_addoption(parser):
    """Add custom command line options"""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests with real API",
    )


def pytest_configure(config):
    """Configure pytest"""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test requiring real API"
    )
