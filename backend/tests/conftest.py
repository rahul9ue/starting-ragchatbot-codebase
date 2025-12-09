"""Shared test fixtures for RAG chatbot tests"""

import os
import shutil
import sys
import tempfile
from unittest.mock import MagicMock

import pytest

# Add parent directory to path to import backend modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from models import Course, CourseChunk, Lesson
from vector_store import VectorStore


@pytest.fixture
def temp_chroma_path():
    """Create a temporary directory for ChromaDB during tests"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup after test
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_course():
    """Create a sample course for testing"""
    lessons = [
        Lesson(
            lesson_number=0,
            title="Introduction to Testing",
            lesson_link="https://example.com/lesson-0",
        ),
        Lesson(
            lesson_number=1,
            title="Advanced Testing Strategies",
            lesson_link="https://example.com/lesson-1",
        ),
        Lesson(
            lesson_number=2, title="Test Automation", lesson_link="https://example.com/lesson-2"
        ),
    ]

    return Course(
        title="Testing Fundamentals",
        instructor="Dr. Test",
        course_link="https://example.com/course",
        lessons=lessons,
    )


@pytest.fixture
def sample_chunks(sample_course):
    """Create sample course chunks for testing"""
    # Define lesson contents separately (not stored in Lesson model)
    lesson_contents = {
        0: "This is lesson 0 about testing basics. We cover unit tests and integration tests.",
        1: "This is lesson 1 about advanced testing. We cover mocking and fixtures.",
        2: "This is lesson 2 about test automation. We cover CI/CD and automated testing pipelines.",
    }

    chunks = []
    for lesson in sample_course.lessons:
        # Create chunks from lesson content
        lesson_content = lesson_contents.get(lesson.lesson_number, "Default content")
        content = (
            f"Course {sample_course.title} Lesson {lesson.lesson_number} content: {lesson_content}"
        )
        chunk = CourseChunk(
            course_title=sample_course.title,
            lesson_number=lesson.lesson_number,
            chunk_index=lesson.lesson_number,  # Simple index for testing
            content=content,
        )
        chunks.append(chunk)
    return chunks


@pytest.fixture
def test_vector_store(temp_chroma_path, sample_course, sample_chunks):
    """Create a VectorStore with test data"""
    store = VectorStore(
        chroma_path=temp_chroma_path, embedding_model="all-MiniLM-L6-v2", max_results=5
    )

    # Add course metadata
    store.add_course_metadata(sample_course)

    # Add course content chunks
    store.add_course_content(sample_chunks)

    return store


@pytest.fixture
def mock_anthropic_client():
    """Create a mock Anthropic client for testing"""
    mock_client = MagicMock()

    # Mock successful text response
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Test response", type="text")]
    mock_response.stop_reason = "end_turn"

    mock_client.messages.create.return_value = mock_response

    return mock_client


@pytest.fixture
def mock_anthropic_client_with_tool_use():
    """Create a mock Anthropic client that returns tool_use responses"""
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
    final_response.content = [
        MagicMock(text="Here is the answer based on search results", type="text")
    ]
    final_response.stop_reason = "end_turn"

    # Configure mock to return different responses on subsequent calls
    mock_client.messages.create.side_effect = [tool_response, final_response]

    return mock_client


@pytest.fixture
def test_config():
    """Create a test configuration"""
    config = Config()
    config.ANTHROPIC_API_KEY = "test-api-key"
    return config
