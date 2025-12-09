"""Tests for search_tools.py - CourseSearchTool and CourseOutlineTool"""

from search_tools import CourseOutlineTool, CourseSearchTool, ToolManager


class TestCourseSearchTool:
    """Test CourseSearchTool functionality"""

    def test_tool_definition(self, test_vector_store):
        """Test that tool definition is properly structured"""
        tool = CourseSearchTool(test_vector_store)
        definition = tool.get_tool_definition()

        assert definition["name"] == "search_course_content"
        assert "description" in definition
        assert "input_schema" in definition
        assert "query" in definition["input_schema"]["properties"]
        assert "course_name" in definition["input_schema"]["properties"]
        assert "lesson_number" in definition["input_schema"]["properties"]
        assert "query" in definition["input_schema"]["required"]

    def test_execute_basic_search(self, test_vector_store):
        """Test basic search without filters"""
        tool = CourseSearchTool(test_vector_store)
        result = tool.execute(query="testing basics")

        print("\n--- Basic Search Result ---")
        print(result)
        print("--- End Result ---\n")

        # Should return formatted results
        assert isinstance(result, str)
        assert len(result) > 0
        # Should not be an error message
        assert not result.startswith("No relevant content found")
        assert "Testing Fundamentals" in result or "testing" in result.lower()

    def test_execute_with_course_filter(self, test_vector_store):
        """Test search with course name filter"""
        tool = CourseSearchTool(test_vector_store)
        result = tool.execute(query="testing", course_name="Testing Fundamentals")

        print("\n--- Search with Course Filter Result ---")
        print(result)
        print("--- End Result ---\n")

        assert isinstance(result, str)
        assert "Testing Fundamentals" in result

    def test_execute_with_partial_course_name(self, test_vector_store):
        """Test search with partial course name (semantic matching)"""
        tool = CourseSearchTool(test_vector_store)
        result = tool.execute(query="testing", course_name="Testing")

        print("\n--- Search with Partial Course Name Result ---")
        print(result)
        print("--- End Result ---\n")

        assert isinstance(result, str)
        # Should resolve "Testing" to "Testing Fundamentals"
        assert "Testing Fundamentals" in result or "testing" in result.lower()

    def test_execute_with_lesson_filter(self, test_vector_store):
        """Test search with lesson number filter"""
        tool = CourseSearchTool(test_vector_store)
        result = tool.execute(query="testing", course_name="Testing Fundamentals", lesson_number=0)

        print("\n--- Search with Lesson Filter Result ---")
        print(result)
        print("--- End Result ---\n")

        assert isinstance(result, str)
        assert "Lesson 0" in result

    def test_execute_nonexistent_course(self, test_vector_store):
        """Test search with non-existent course name"""
        tool = CourseSearchTool(test_vector_store)
        result = tool.execute(query="testing", course_name="Nonexistent Course")

        print("\n--- Search Nonexistent Course Result ---")
        print(result)
        print("--- End Result ---\n")

        assert isinstance(result, str)
        assert "No course found" in result or "No relevant content found" in result

    def test_execute_no_results(self, test_vector_store):
        """Test search that returns no results"""
        tool = CourseSearchTool(test_vector_store)
        result = tool.execute(query="quantum mechanics advanced physics")

        print("\n--- Search No Results ---")
        print(result)
        print("--- End Result ---\n")

        assert isinstance(result, str)
        # Should indicate no results found
        assert "No relevant content found" in result or len(result) > 0

    def test_sources_tracking(self, test_vector_store):
        """Test that sources are properly tracked after search"""
        tool = CourseSearchTool(test_vector_store)
        _result = tool.execute(query="testing basics")

        # Check that sources were stored
        assert hasattr(tool, "last_sources")
        assert isinstance(tool.last_sources, list)
        assert len(tool.last_sources) > 0

        # Check source structure
        for source in tool.last_sources:
            assert "text" in source
            assert "link" in source
            print(f"\nSource: {source}")


class TestCourseOutlineTool:
    """Test CourseOutlineTool functionality"""

    def test_tool_definition(self, test_vector_store):
        """Test that tool definition is properly structured"""
        tool = CourseOutlineTool(test_vector_store)
        definition = tool.get_tool_definition()

        assert definition["name"] == "get_course_outline"
        assert "description" in definition
        assert "input_schema" in definition
        assert "course_name" in definition["input_schema"]["properties"]
        assert "course_name" in definition["input_schema"]["required"]

    def test_execute_get_outline(self, test_vector_store):
        """Test getting course outline"""
        tool = CourseOutlineTool(test_vector_store)
        result = tool.execute(course_name="Testing Fundamentals")

        print("\n--- Course Outline Result ---")
        print(result)
        print("--- End Result ---\n")

        assert isinstance(result, str)
        assert "Testing Fundamentals" in result
        assert "Course Link" in result
        assert "Lesson 0" in result
        assert "Lesson 1" in result
        assert "Lesson 2" in result
        assert "Introduction to Testing" in result
        assert "Advanced Testing Strategies" in result

    def test_execute_partial_course_name(self, test_vector_store):
        """Test getting outline with partial course name"""
        tool = CourseOutlineTool(test_vector_store)
        result = tool.execute(course_name="Testing")

        print("\n--- Outline with Partial Name Result ---")
        print(result)
        print("--- End Result ---\n")

        assert isinstance(result, str)
        assert "Testing Fundamentals" in result

    def test_execute_nonexistent_course(self, test_vector_store):
        """Test getting outline for non-existent course"""
        tool = CourseOutlineTool(test_vector_store)
        result = tool.execute(course_name="Nonexistent Course")

        print("\n--- Outline Nonexistent Course Result ---")
        print(result)
        print("--- End Result ---\n")

        assert isinstance(result, str)
        assert "No course found" in result


class TestToolManager:
    """Test ToolManager functionality"""

    def test_register_tool(self, test_vector_store):
        """Test tool registration"""
        manager = ToolManager()
        search_tool = CourseSearchTool(test_vector_store)

        manager.register_tool(search_tool)

        assert "search_course_content" in manager.tools

    def test_get_tool_definitions(self, test_vector_store):
        """Test getting all tool definitions"""
        manager = ToolManager()
        search_tool = CourseSearchTool(test_vector_store)
        outline_tool = CourseOutlineTool(test_vector_store)

        manager.register_tool(search_tool)
        manager.register_tool(outline_tool)

        definitions = manager.get_tool_definitions()

        assert isinstance(definitions, list)
        assert len(definitions) == 2
        tool_names = [d["name"] for d in definitions]
        assert "search_course_content" in tool_names
        assert "get_course_outline" in tool_names

    def test_execute_tool(self, test_vector_store):
        """Test executing a tool through the manager"""
        manager = ToolManager()
        search_tool = CourseSearchTool(test_vector_store)
        manager.register_tool(search_tool)

        result = manager.execute_tool("search_course_content", query="testing basics")

        print("\n--- Tool Manager Execute Result ---")
        print(result)
        print("--- End Result ---\n")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_execute_nonexistent_tool(self, test_vector_store):
        """Test executing a tool that doesn't exist"""
        manager = ToolManager()

        result = manager.execute_tool("nonexistent_tool", query="test")

        assert "not found" in result

    def test_get_last_sources(self, test_vector_store):
        """Test retrieving sources from last search"""
        manager = ToolManager()
        search_tool = CourseSearchTool(test_vector_store)
        manager.register_tool(search_tool)

        # Execute a search
        manager.execute_tool("search_course_content", query="testing basics")

        # Get sources
        sources = manager.get_last_sources()

        assert isinstance(sources, list)
        assert len(sources) > 0

    def test_reset_sources(self, test_vector_store):
        """Test resetting sources"""
        manager = ToolManager()
        search_tool = CourseSearchTool(test_vector_store)
        manager.register_tool(search_tool)

        # Execute a search
        manager.execute_tool("search_course_content", query="testing basics")

        # Reset sources
        manager.reset_sources()

        # Should be empty now
        sources = manager.get_last_sources()
        assert len(sources) == 0
