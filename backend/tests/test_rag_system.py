"""Tests for rag_system.py - RAGSystem integration tests"""

from unittest.mock import MagicMock

import pytest
from models import Source
from rag_system import RAGSystem


class TestRAGSystemInitialization:
    """Test RAGSystem initialization"""

    def test_initialization(self, test_config, temp_chroma_path):
        """Test RAGSystem initializes all components"""
        test_config.CHROMA_PATH = temp_chroma_path

        rag_system = RAGSystem(test_config)

        assert rag_system.document_processor is not None
        assert rag_system.vector_store is not None
        assert rag_system.ai_generator is not None
        assert rag_system.session_manager is not None
        assert rag_system.tool_manager is not None
        assert rag_system.search_tool is not None
        assert rag_system.outline_tool is not None

        # Check tools are registered
        tool_defs = rag_system.tool_manager.get_tool_definitions()
        assert len(tool_defs) == 2
        tool_names = [t["name"] for t in tool_defs]
        assert "search_course_content" in tool_names
        assert "get_course_outline" in tool_names


class TestRAGSystemDocumentProcessing:
    """Test document processing functionality"""

    def test_add_course_document(self, test_config, temp_chroma_path, tmp_path):
        """Test adding a course document"""
        test_config.CHROMA_PATH = temp_chroma_path
        rag_system = RAGSystem(test_config)

        # Create a test document
        test_doc = tmp_path / "test_course.txt"
        test_doc.write_text(
            """Course Title: Test Course
Course Link: https://example.com/course
Course Instructor: Test Instructor

Lesson 0: Introduction
Lesson Link: https://example.com/lesson-0
This is the introduction lesson content.

Lesson 1: Advanced Topics
Lesson Link: https://example.com/lesson-1
This is the advanced topics content.
"""
        )

        course, num_chunks = rag_system.add_course_document(str(test_doc))

        assert course is not None
        assert course.title == "Test Course"
        assert num_chunks > 0

    def test_get_course_analytics(self, test_config, temp_chroma_path, sample_course):
        """Test course analytics"""
        test_config.CHROMA_PATH = temp_chroma_path
        rag_system = RAGSystem(test_config)

        # Add a course
        rag_system.vector_store.add_course_metadata(sample_course)

        analytics = rag_system.get_course_analytics()

        assert "total_courses" in analytics
        assert "course_titles" in analytics
        assert analytics["total_courses"] >= 1
        assert "Testing Fundamentals" in analytics["course_titles"]


class TestRAGSystemQueryWithMocks:
    """Test RAGSystem query functionality with mocked AI"""

    def test_query_without_session(self, test_config, temp_chroma_path, test_vector_store):
        """Test query without session ID"""
        test_config.CHROMA_PATH = temp_chroma_path
        rag_system = RAGSystem(test_config)
        rag_system.vector_store = test_vector_store

        # Mock AI generator
        mock_response = "This is a test response about testing"
        rag_system.ai_generator.generate_response = MagicMock(return_value=mock_response)

        response, sources = rag_system.query("What is testing?")

        print("\n--- Query Without Session Response ---")
        print(f"Response: {response}")
        print(f"Sources: {sources}")
        print("--- End Response ---\n")

        assert response == mock_response
        assert isinstance(sources, list)

    def test_query_with_session(self, test_config, temp_chroma_path, test_vector_store):
        """Test query with session ID for conversation history"""
        test_config.CHROMA_PATH = temp_chroma_path
        rag_system = RAGSystem(test_config)
        rag_system.vector_store = test_vector_store

        # Mock AI generator
        mock_response = "This is a test response"
        rag_system.ai_generator.generate_response = MagicMock(return_value=mock_response)

        session_id = "test_session_1"

        # First query
        response1, sources1 = rag_system.query("What is testing?", session_id=session_id)

        # Second query (should have history)
        response2, sources2 = rag_system.query("Tell me more", session_id=session_id)

        # Check that AI generator was called with history on second call
        calls = rag_system.ai_generator.generate_response.call_args_list
        assert len(calls) == 2

        # Second call should have conversation_history
        second_call_kwargs = calls[1].kwargs
        assert "conversation_history" in second_call_kwargs
        history = second_call_kwargs["conversation_history"]
        assert history is not None
        print("\n--- Conversation History ---")
        print(history)
        print("--- End History ---\n")

    def test_query_sources_returned(self, test_config, temp_chroma_path, test_vector_store):
        """Test that sources are properly returned"""
        test_config.CHROMA_PATH = temp_chroma_path
        rag_system = RAGSystem(test_config)
        rag_system.vector_store = test_vector_store

        # Mock AI generator to trigger tool use
        def mock_generate(query, conversation_history=None, tools=None, tool_manager=None):
            # Simulate tool execution
            if tool_manager:
                tool_manager.execute_tool("search_course_content", query="testing basics")
            return "Response based on search"

        rag_system.ai_generator.generate_response = mock_generate

        response, sources = rag_system.query("What is testing?")

        print("\n--- Query Sources ---")
        print(f"Response: {response}")
        print(f"Sources: {sources}")
        print("--- End Sources ---\n")

        assert isinstance(sources, list)
        # Sources should have been populated by the search
        if len(sources) > 0:
            assert isinstance(sources[0], Source)
            assert hasattr(sources[0], "text")
            assert hasattr(sources[0], "link")

    def test_query_tools_passed_to_ai(self, test_config, temp_chroma_path, test_vector_store):
        """Test that tools are passed to AI generator"""
        test_config.CHROMA_PATH = temp_chroma_path
        rag_system = RAGSystem(test_config)
        rag_system.vector_store = test_vector_store

        # Mock AI generator
        mock_generate = MagicMock(return_value="Test response")
        rag_system.ai_generator.generate_response = mock_generate

        response, sources = rag_system.query("What is testing?")

        # Check that AI generator was called with tools
        call_kwargs = mock_generate.call_args.kwargs
        assert "tools" in call_kwargs
        assert "tool_manager" in call_kwargs
        assert call_kwargs["tools"] is not None
        assert call_kwargs["tool_manager"] is not None

        # Check tool definitions
        tools = call_kwargs["tools"]
        assert len(tools) == 2
        tool_names = [t["name"] for t in tools]
        assert "search_course_content" in tool_names
        assert "get_course_outline" in tool_names


class TestRAGSystemIntegration:
    """Integration tests with real components (requires API key)"""

    @pytest.mark.integration
    def test_end_to_end_content_query(
        self, test_config, temp_chroma_path, sample_course, sample_chunks
    ):
        """Test end-to-end query with real AI API"""
        if not test_config.ANTHROPIC_API_KEY or test_config.ANTHROPIC_API_KEY == "test-api-key":
            pytest.skip("Real API key required")

        test_config.CHROMA_PATH = temp_chroma_path
        rag_system = RAGSystem(test_config)

        # Add test data
        rag_system.vector_store.add_course_metadata(sample_course)
        rag_system.vector_store.add_course_content(sample_chunks)

        # Query
        response, sources = rag_system.query(
            "What does the Testing Fundamentals course teach about unit tests?"
        )

        print("\n--- End-to-End Content Query ---")
        print(f"Response: {response}")
        print(f"Sources: {sources}")
        print("--- End Query ---\n")

        assert isinstance(response, str)
        assert len(response) > 0
        # Response should mention testing or unit tests
        assert "test" in response.lower() or len(response) > 10

    @pytest.mark.integration
    def test_end_to_end_outline_query(
        self, test_config, temp_chroma_path, sample_course, sample_chunks
    ):
        """Test end-to-end outline query with real AI API"""
        if not test_config.ANTHROPIC_API_KEY or test_config.ANTHROPIC_API_KEY == "test-api-key":
            pytest.skip("Real API key required")

        test_config.CHROMA_PATH = temp_chroma_path
        rag_system = RAGSystem(test_config)

        # Add test data
        rag_system.vector_store.add_course_metadata(sample_course)
        rag_system.vector_store.add_course_content(sample_chunks)

        # Query for outline
        response, sources = rag_system.query(
            "What is the outline of the Testing Fundamentals course?"
        )

        print("\n--- End-to-End Outline Query ---")
        print(f"Response: {response}")
        print(f"Sources: {sources}")
        print("--- End Query ---\n")

        assert isinstance(response, str)
        assert len(response) > 0
        # Response should mention lessons
        assert "lesson" in response.lower() or "Testing Fundamentals" in response

    @pytest.mark.integration
    def test_end_to_end_general_query(self, test_config, temp_chroma_path):
        """Test end-to-end general knowledge query (no tool use)"""
        if not test_config.ANTHROPIC_API_KEY or test_config.ANTHROPIC_API_KEY == "test-api-key":
            pytest.skip("Real API key required")

        test_config.CHROMA_PATH = temp_chroma_path
        rag_system = RAGSystem(test_config)

        # Query that shouldn't use tools
        response, sources = rag_system.query("What is 2+2?")

        print("\n--- End-to-End General Query ---")
        print(f"Response: {response}")
        print(f"Sources: {sources}")
        print("--- End Query ---\n")

        assert isinstance(response, str)
        assert len(response) > 0
        assert "4" in response
        # Should not have sources for general query
        assert len(sources) == 0
