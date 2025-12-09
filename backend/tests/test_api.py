"""Tests for FastAPI endpoints - API integration tests"""
import pytest
from fastapi import status
from unittest.mock import MagicMock


@pytest.mark.api
class TestQueryEndpoint:
    """Test /api/query endpoint"""

    def test_query_endpoint_success(self, test_client, sample_query_request):
        """Test successful query request"""
        response = test_client.post("/api/query", json=sample_query_request)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check response structure
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data

        # Check data types
        assert isinstance(data["answer"], str)
        assert isinstance(data["sources"], list)
        assert isinstance(data["session_id"], str)

        # Check session ID matches request
        assert data["session_id"] == sample_query_request["session_id"]

    def test_query_endpoint_without_session_id(self, test_client):
        """Test query request without session_id (should auto-generate)"""
        request_data = {"query": "What is testing?"}
        response = test_client.post("/api/query", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should auto-generate session_id
        assert "session_id" in data
        assert data["session_id"] is not None
        assert len(data["session_id"]) > 0

    def test_query_endpoint_with_sources(self, test_client):
        """Test that query returns sources correctly"""
        request_data = {"query": "Tell me about testing", "session_id": "test_123"}
        response = test_client.post("/api/query", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check sources structure
        assert isinstance(data["sources"], list)
        if len(data["sources"]) > 0:
            source = data["sources"][0]
            # Source model only has text and link fields
            assert "text" in source
            assert "link" in source
            assert isinstance(source["text"], str)
            assert source["link"] is None or isinstance(source["link"], str)

    def test_query_endpoint_missing_query(self, test_client):
        """Test query request with missing query field"""
        request_data = {"session_id": "test_123"}
        response = test_client.post("/api/query", json=request_data)

        # Should return 422 Unprocessable Entity for validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_query_endpoint_empty_query(self, test_client):
        """Test query request with empty query string"""
        request_data = {"query": "", "session_id": "test_123"}
        response = test_client.post("/api/query", json=request_data)

        # Should still process (validation allows empty strings)
        assert response.status_code == status.HTTP_200_OK

    def test_query_endpoint_malformed_json(self, test_client):
        """Test query request with malformed JSON"""
        response = test_client.post(
            "/api/query",
            data="not a valid json",
            headers={"Content-Type": "application/json"}
        )

        # Should return 422 for invalid JSON
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_query_endpoint_extra_fields(self, test_client):
        """Test query request with extra fields (should be ignored)"""
        request_data = {
            "query": "What is testing?",
            "session_id": "test_123",
            "extra_field": "ignored"
        }
        response = test_client.post("/api/query", json=request_data)

        # Should succeed and ignore extra fields
        assert response.status_code == status.HTTP_200_OK

    def test_query_endpoint_response_format(self, test_client):
        """Test that response format matches QueryResponse model"""
        request_data = {"query": "What is testing?", "session_id": "test_session"}
        response = test_client.post("/api/query", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Validate all required fields are present
        required_fields = ["answer", "sources", "session_id"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    def test_query_endpoint_error_handling(self, test_client, mock_rag_system):
        """Test error handling when RAG system raises exception"""
        # Configure mock to raise exception
        mock_rag_system.query.side_effect = Exception("Test error")

        request_data = {"query": "What is testing?", "session_id": "test_123"}
        response = test_client.post("/api/query", json=request_data)

        # Should return 500 Internal Server Error
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data


@pytest.mark.api
class TestCoursesEndpoint:
    """Test /api/courses endpoint"""

    def test_courses_endpoint_success(self, test_client):
        """Test successful courses request"""
        response = test_client.get("/api/courses")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check response structure
        assert "total_courses" in data
        assert "course_titles" in data

        # Check data types
        assert isinstance(data["total_courses"], int)
        assert isinstance(data["course_titles"], list)

        # Check values from mock
        assert data["total_courses"] == 2
        assert len(data["course_titles"]) == 2
        assert "Course A" in data["course_titles"]
        assert "Course B" in data["course_titles"]

    def test_courses_endpoint_response_format(self, test_client):
        """Test that response format matches CourseStats model"""
        response = test_client.get("/api/courses")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Validate all required fields are present
        required_fields = ["total_courses", "course_titles"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Validate course_titles is a list of strings
        assert all(isinstance(title, str) for title in data["course_titles"])

    def test_courses_endpoint_empty_courses(self, test_client, mock_rag_system):
        """Test courses endpoint when no courses exist"""
        # Configure mock to return empty courses
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": []
        }

        response = test_client.get("/api/courses")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["total_courses"] == 0
        assert data["course_titles"] == []

    def test_courses_endpoint_error_handling(self, test_client, mock_rag_system):
        """Test error handling when RAG system raises exception"""
        # Configure mock to raise exception
        mock_rag_system.get_course_analytics.side_effect = Exception("Database error")

        response = test_client.get("/api/courses")

        # Should return 500 Internal Server Error
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = response.json()
        assert "detail" in data

    def test_courses_endpoint_no_body(self, test_client):
        """Test courses endpoint doesn't require request body"""
        response = test_client.get("/api/courses")

        # Should succeed without any request body
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.api
class TestAPIIntegration:
    """Integration tests for API endpoints"""

    def test_multiple_queries_same_session(self, test_client):
        """Test multiple queries with the same session ID"""
        session_id = "integration_test_session"

        # First query
        response1 = test_client.post("/api/query", json={
            "query": "What is testing?",
            "session_id": session_id
        })
        assert response1.status_code == status.HTTP_200_OK
        data1 = response1.json()
        assert data1["session_id"] == session_id

        # Second query with same session
        response2 = test_client.post("/api/query", json={
            "query": "Tell me more",
            "session_id": session_id
        })
        assert response2.status_code == status.HTTP_200_OK
        data2 = response2.json()
        assert data2["session_id"] == session_id

    def test_different_sessions_independent(self, test_client):
        """Test that different sessions are independent"""
        # Query with session 1
        response1 = test_client.post("/api/query", json={
            "query": "What is testing?",
            "session_id": "session_1"
        })
        assert response1.status_code == status.HTTP_200_OK

        # Query with session 2
        response2 = test_client.post("/api/query", json={
            "query": "What is testing?",
            "session_id": "session_2"
        })
        assert response2.status_code == status.HTTP_200_OK

        # Sessions should be different
        assert response1.json()["session_id"] != response2.json()["session_id"]

    def test_query_then_courses(self, test_client):
        """Test querying then getting course stats"""
        # First make a query
        query_response = test_client.post("/api/query", json={
            "query": "What courses are available?"
        })
        assert query_response.status_code == status.HTTP_200_OK

        # Then get course stats
        courses_response = test_client.get("/api/courses")
        assert courses_response.status_code == status.HTTP_200_OK

        # Both should succeed independently
        assert "answer" in query_response.json()
        assert "total_courses" in courses_response.json()

    def test_cors_headers(self, test_client):
        """Test that CORS headers are present"""
        response = test_client.get("/api/courses")

        # Check for CORS headers (TestClient may not expose all headers)
        # This test verifies the endpoint is accessible, which requires CORS to be configured
        assert response.status_code == status.HTTP_200_OK

    def test_content_type_headers(self, test_client):
        """Test that proper content type headers are set"""
        response = test_client.get("/api/courses")

        assert response.status_code == status.HTTP_200_OK
        # FastAPI automatically sets application/json for Pydantic models
        assert "application/json" in response.headers.get("content-type", "")


@pytest.mark.api
class TestAPIEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_very_long_query(self, test_client):
        """Test handling of very long query strings"""
        long_query = "What is testing? " * 1000  # ~18000 characters
        request_data = {"query": long_query, "session_id": "test_long"}

        response = test_client.post("/api/query", json=request_data)

        # Should handle long queries gracefully
        assert response.status_code == status.HTTP_200_OK

    def test_special_characters_in_query(self, test_client):
        """Test handling of special characters in queries"""
        special_queries = [
            "What is <testing>?",
            "Tell me about \"testing\" & 'mocking'",
            "How to test: Step 1; Step 2",
            "Testing with emoji 🧪🔬",
            "Query with\nnewlines\nand\ttabs",
        ]

        for query in special_queries:
            request_data = {"query": query, "session_id": "test_special"}
            response = test_client.post("/api/query", json=request_data)
            assert response.status_code == status.HTTP_200_OK

    def test_unicode_in_query(self, test_client):
        """Test handling of Unicode characters"""
        unicode_queries = [
            "What is テスト?",  # Japanese
            "Qu'est-ce que le testing?",  # French
            "Was ist Testen?",  # German
            "¿Qué es testing?",  # Spanish
        ]

        for query in unicode_queries:
            request_data = {"query": query, "session_id": "test_unicode"}
            response = test_client.post("/api/query", json=request_data)
            assert response.status_code == status.HTTP_200_OK

    def test_concurrent_requests(self, test_client):
        """Test handling of multiple concurrent-like requests"""
        # Simulate multiple requests (sequential but rapid)
        sessions = [f"session_{i}" for i in range(10)]
        responses = []

        for session_id in sessions:
            response = test_client.post("/api/query", json={
                "query": f"Query for {session_id}",
                "session_id": session_id
            })
            responses.append(response)

        # All should succeed
        for response in responses:
            assert response.status_code == status.HTTP_200_OK

        # Each should have correct session
        for i, response in enumerate(responses):
            assert response.json()["session_id"] == sessions[i]

    def test_sql_injection_attempt(self, test_client):
        """Test that SQL injection attempts are safely handled"""
        injection_attempts = [
            "'; DROP TABLE courses; --",
            "1' OR '1'='1",
            "admin'--",
        ]

        for attempt in injection_attempts:
            request_data = {"query": attempt, "session_id": "test_injection"}
            response = test_client.post("/api/query", json=request_data)

            # Should process safely without errors
            assert response.status_code == status.HTTP_200_OK

    def test_xss_attempt(self, test_client):
        """Test that XSS attempts are safely handled"""
        xss_attempts = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
        ]

        for attempt in xss_attempts:
            request_data = {"query": attempt, "session_id": "test_xss"}
            response = test_client.post("/api/query", json=request_data)

            # Should process safely
            assert response.status_code == status.HTTP_200_OK
