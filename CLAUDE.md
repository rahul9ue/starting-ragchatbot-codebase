# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Application Overview

This is a RAG (Retrieval-Augmented Generation) chatbot system for answering questions about course materials. It combines FastAPI (backend), vanilla JavaScript (frontend), ChromaDB (vector storage), Sentence Transformers (embeddings), and Anthropic's Claude (AI generation).

## Running the Application

**IMPORTANT:** This project uses `uv` for package management and execution.

- **Always use `uv run`** to execute Python files and commands
- **Never use `python` or `pip` directly**
- All Python execution must go through `uv run python script.py` or `uv run <command>`

```bash
# Initial setup
uv sync
cp .env.example .env  # Add your ANTHROPIC_API_KEY

# Run the application
./run.sh

# Manual start (alternative)
cd backend && uv run uvicorn app:app --reload --port 8000
```

Access points:

- Web Interface: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## Core Architecture

### Component Interaction Flow

```
Frontend → FastAPI (app.py) → RAGSystem (orchestrator)
                                     ↓
        ┌────────────────────────────┼────────────────────────────┐
        ↓                            ↓                            ↓
  DocumentProcessor          VectorStore (ChromaDB)        AIGenerator (Claude)
        ↓                            ↓                            ↓
  Parse & Chunk           Semantic Search + Filtering    Tool-Based Generation
```

**RAGSystem** (`backend/rag_system.py`) is the central orchestrator that coordinates all components. The `query()` method is the main entry point for user queries.

### Dual-Collection Vector Store Design

ChromaDB uses two collections for different purposes:

1. **`course_catalog`** - Course discovery via semantic search
   - Document: Course title text
   - Metadata: instructor, course_link, lessons_json, lesson_count
   - Used by `_resolve_course_name()` for fuzzy course matching (e.g., "MCP" → full title)

2. **`course_content`** - Actual searchable content chunks
   - Document: Chunk text with context prefix
   - Metadata: course_title, lesson_number, chunk_index
   - Enables filtering by course and lesson

This architecture allows intelligent course name resolution before content search.

### Tool-Based Search (Not Traditional RAG)

Unlike typical RAG systems that always embed and search, this uses **tool calling**:

- Claude decides whether to use the `search_course_content` tool
- General knowledge questions skip search entirely
- Course-specific questions trigger search
- Maximum one search per query (enforced in system prompt)
- More efficient and context-aware than always searching

**Key Files:**
- `backend/search_tools.py` - Tool definitions and execution
- `backend/ai_generator.py` - Tool execution loop in `_handle_tool_execution()`

### Document Processing Pipeline

Expected document format:
```
Course Title: [title]
Course Link: [url]
Course Instructor: [instructor]

Lesson 0: [title]
Lesson Link: [url]
[content...]

Lesson 1: [title]
[content...]
```

Processing flow (`backend/document_processor.py`):
1. Extract metadata from first 3-4 lines
2. Parse lessons using regex: `Lesson \d+:`
3. Chunk text using **sentence-based splitting** (800 chars, 100 char overlap)
4. Add context to chunks: `"Course {title} Lesson {N} content: {chunk}"`
5. Store in both collections (catalog metadata + searchable content)

**Chunking Strategy:**
- Sentence boundaries preserved (regex handles abbreviations)
- 100-char overlap between chunks prevents context loss
- First chunk of each lesson gets lesson context prefix

### Session Management

Sessions are **in-memory** and volatile:
- Auto-generated IDs: `session_1`, `session_2`, etc.
- Sliding window history: keeps last 2 user/assistant pairs (4 messages total)
- History injected into system prompt as conversation context
- Lost on server restart (acceptable for educational use)

**Files:** `backend/session_manager.py`

### Configuration Settings

All settings in `backend/config.py`:

```python
CHUNK_SIZE = 800           # Characters per chunk
CHUNK_OVERLAP = 100        # Overlap between chunks
MAX_RESULTS = 5            # Search results returned
MAX_HISTORY = 2            # Conversation turns remembered
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # SentenceTransformer
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
```

These values balance context preservation, token costs, and search quality.

## Development Workflows

### Adding Course Documents

1. Place `.pdf`, `.docx`, or `.txt` files in `docs/` folder
2. Restart server or trigger reload
3. Auto-processed on startup via `app.py` lines 88-98
4. Deduplication by course title (won't re-add existing)

### Query Flow

```
1. Frontend POST /api/query with {query, session_id}
2. RAGSystem.query() retrieves conversation history
3. AIGenerator.generate_response() with tool definitions
4. Claude decides: use search_course_content tool or answer directly
5. If tool_use:
   a. ToolManager.execute_tool() → CourseSearchTool.execute()
   b. VectorStore.search() with semantic similarity + filters
   c. Results sent back to Claude
   d. Claude generates final response
6. Response + sources returned to frontend
7. Session updated with query/response pair
```

### Debugging Considerations

**Tool Execution:**
- Tool calls are transparent in `ai_generator.py:_handle_tool_execution()`
- Results included in conversation sent back to Claude
- Sources tracked in `ToolManager.last_sources`

**Vector Store:**
- Persisted to `backend/chroma_db/chroma.sqlite3`
- Can inspect collections directly using ChromaDB client
- Clear data: delete `chroma_db/` directory

**Session State:**
- In-memory only: inspect `SessionManager.sessions` dict while running
- Reset by starting new chat session in frontend

## Key Architectural Insights

### Why Dual Collections?

Separating course catalog from content enables:
- Semantic course discovery ("computer use" → matches course title)
- Metadata-rich filtering (by course name, lesson number)
- Efficient course analytics without scanning all chunks

### Why Tool-Based vs. Always Searching?

Traditional RAG always embeds and searches. This system:
- Lets Claude decide when search is needed
- Saves API calls for general questions
- Better follow-up handling using conversation context
- Extensible: can add more tools (e.g., summarize_course, list_lessons)

### Chunk Overlap Strategy

100-char overlap ensures:
- Sentences split across chunks remain accessible
- Context continuity for semantic embeddings
- Last sentence of previous chunk provides context for next

## Important Implementation Details

### Course Name Resolution

`VectorStore._resolve_course_name()` (lines 146-167):
- Uses semantic search on course_catalog collection
- Enables fuzzy matching: "MCP" → "Building Towards Computer Use with Anthropic"
- Returns exact title for filtering course_content searches

### System Prompt Design

`AIGenerator.SYSTEM_PROMPT` (lines 8-30):
- Instructs Claude to use tool **only** for course-specific questions
- Limits to one search per query
- Requests direct answers without meta-commentary
- Guides citation format

### Frontend Session Management

`frontend/script.js`:
- Generates session_id on first query: `session_${Date.now()}`
- Persists across all queries in same chat
- New session on page refresh
- Sends session_id with every query for context continuity

## File Organization

```
backend/
  ├── app.py                 # FastAPI endpoints, CORS, static serving
  ├── config.py              # Centralized configuration
  ├── models.py              # Pydantic data models
  ├── rag_system.py          # Main orchestrator facade
  ├── vector_store.py        # ChromaDB wrapper with dual collections
  ├── document_processor.py  # Parsing, chunking, metadata extraction
  ├── ai_generator.py        # Claude API with tool execution loop
  ├── search_tools.py        # Tool definitions and source tracking
  ├── session_manager.py     # In-memory conversation state
  └── chroma_db/             # ChromaDB persistence (SQLite)

frontend/
  ├── index.html             # Chat UI structure
  ├── script.js              # API calls, session management, rendering
  └── style.css              # Styling

docs/                        # Course documents auto-loaded on startup
```

## Common Modification Patterns

### Managing Dependencies

**Always use `uv` for all dependency and execution operations.**

- Never use `pip install` - use `uv add` instead
- Never run `python script.py` - use `uv run python script.py` instead
- All Python commands must be prefixed with `uv run`

Add a new package:

```bash
uv add package-name
```

Add a development dependency:

```bash
uv add --dev package-name
```

Update dependencies:

```bash
uv sync
```

Execute Python files or commands:

```bash
# Run a Python script
uv run python script.py

# Run any Python command
uv run uvicorn app:app --reload
uv run pytest tests/
uv run python -m module_name
```

Dependencies are defined in `pyproject.toml` and locked in `uv.lock`. Always commit both files when dependencies change.

### Adding a New Tool

1. Create tool class extending `Tool` in `search_tools.py`
2. Implement `get_definition()` and `execute()` methods
3. Register in `RAGSystem.__init__()`: `self.tool_manager.register_tool(new_tool)`
4. Tool automatically available to Claude

### Adjusting Chunk Size

Modify `config.py`:
- Increase `CHUNK_SIZE` for more context per chunk (higher token cost)
- Increase `CHUNK_OVERLAP` for better continuity (more redundancy)
- Balance: larger chunks = fewer API calls but higher per-call cost

### Changing Conversation History Length

Modify `config.py` `MAX_HISTORY`:
- Current: 2 (keeps 4 messages: 2 user + 2 assistant)
- Increase for longer context (higher token cost)
- Decrease for shorter memory (lower cost, less context)

### Adding Persistent Sessions

Replace `SessionManager` in-memory dict with:
- Database storage (SQLite, PostgreSQL)
- Redis for distributed deployments
- Update `get_conversation_history()` and `add_exchange()` methods

## Code Quality Tools

This project uses automated code quality tools to maintain consistent formatting and catch common issues.

### Installed Tools

**Black** - Opinionated code formatter
- Line length: 100 characters
- Target: Python 3.13
- Config: `[tool.black]` in `pyproject.toml`

**Ruff** - Fast Python linter
- Checks: pycodestyle (E/W), pyflakes (F), isort (I), bugbear (B), comprehensions (C4), pyupgrade (UP)
- Auto-fixes many issues
- Config: `[tool.ruff]` in `pyproject.toml`

### Running Quality Checks

**Quick check (recommended before committing):**
```bash
./quality.sh
```

This runs:
- Black format check (no modifications)
- Ruff linting

**With tests:**
```bash
./quality.sh --with-tests
```

**Auto-format code:**
```bash
./format.sh
```

This runs:
- Black formatter (modifies files)
- Ruff auto-fixes

**Manual commands:**
```bash
# Format code
uv run black backend/

# Check formatting without changes
uv run black --check backend/

# Run linter
uv run ruff check backend/

# Run linter with auto-fix
uv run ruff check backend/ --fix
```

### Pre-Commit Workflow

1. Make your code changes
2. Run `./format.sh` to auto-format
3. Run `./quality.sh` to verify all checks pass
4. Commit your changes

### Configuration Details

All quality tool settings are in `pyproject.toml`:

- Line length: 100 (both Black and Ruff)
- Excluded directories: `.venv`, `build`, `dist`, `chroma_db`
- Import sorting: `backend` is treated as first-party package
- Special rules: E402 (imports not at top) ignored for `app.py` due to warnings filter
