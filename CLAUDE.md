# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build, Test, and Development Commands

### Environment Setup
```bash
# Install uv package manager (if not installed)
pip install uv
# Or: brew install uv (macOS) / choco install uv (Windows)

# Install dependencies
uv sync --dev

# Or use requirements.txt with Aliyun mirror
uv pip install -r requirements.txt -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
```

### Running the Application
```bash
# Start the FastAPI server (reads host/port from configs)
uv run uvicorn app:app --reload

# Or run directly
python app.py
```

### Database Migrations
```bash
# Create a new migration
uv run alembic -c alembic/alembic.ini revision --autogenerate -m "description"

# Apply migrations
uv run alembic -c alembic/alembic.ini upgrade head

# Rollback one migration
uv run alembic -c alembic/alembic.ini downgrade -1
```

### Testing
```bash
# Run all tests
uv run pytest

# Run specific test suite
uv run pytest tests/completion

# Run tests matching keyword
uv run pytest -k translate

# Run with verbose output
uv run pytest -v

# Run tests excluding slow ones
uv run pytest -m "not slow"
```

### Code Quality
```bash
# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Auto-fix linting issues
uv run ruff check --fix .
```

## High-Level Architecture

### Application Initialization Flow
The application follows a factory pattern:
- `app.py` - Entry point that imports the factory
- `app_factory.py` - Creates and configures the FastAPI app
  - Initializes logging, cache, storage, snowflake ID generator
  - Sets up event manager for async event processing
  - Configures RPC service registration with Nacos discovery
  - Wires up middleware (trace ID, API key context, logging)

### Core Architectural Layers

**Controllers → Services → Runtime/Models → Components**

1. **Controllers** (`controllers/`) - Thin HTTP request handlers
   - Route definitions and request/response transformation
   - Use `@catch_exceptions` decorator to convert `BaseServiceError` to HTTP responses
   - Never contain business logic

2. **Services** (`service/`) - Business logic layer
   - Stateless static/class methods
   - Orchestrate runtime components and database operations
   - Use context-managed DB sessions: `with get_db() as session:`
   - Emit events via `event_manager` for async processing
   - Key services: ModelService, CompletionService, KnowledgeBaseService, QAMemoryService, AgentService

3. **Runtime** (`runtime/`) - LLM orchestration and execution
   - **ModelManager**: Factory-based provider abstraction
   - **AgentManager**: Coordinates sessions, memory, tools, and response generation
   - **RagManager**: ETL pipeline for document processing (Extract → Transform → Load)
   - **Transformation system**: Strategy pattern for provider-specific API calls (OpenAI-like, Anthropic, DeepSeek, etc.)

4. **Models** (`models/`) - SQLAlchemy ORM models
   - Database table definitions
   - Shared across services via `get_db()` session manager

5. **Components** (`component/`) - Infrastructure adapters
   - Storage backends (local, S3, OpenDAL)
   - Vector databases (Milvus, pgvecto_rs)
   - Logging and caching (Redis)

### Key Design Patterns

**Model Provider Orchestration** (`runtime/model_manager.py`, `runtime/provider_manager.py`):
- Factory pattern creates model instances by type (LLM, Embedding, Rerank, TTS, ASR)
- Wrapper pattern: `ModelInstance` wraps provider + credentials
- Supported SDKs: OpenAI-like, Anthropic, GitHub Copilot, DeepSeek, OpenRouter, Transformers
- Transformation classes handle provider-specific API formatting

**Agent Execution** (`runtime/agent_manager.py`):
- Modular managers: SessionManager, MemoryManager, ToolManager, ResponseGenerator
- Tool types: BUILTIN (CurrentTime, CurrentWeather) and MCP (dynamic server integration)
- Memory integration: short-term conversation history + long-term embedding retrieval
- Recursive tool calling with callback management

**RAG Pipeline** (`runtime/rag_manager.py`, `runtime/rag/`):
- **Extract**: FileResource → Extractor (Text, Markdown, HTML, ConversationMessage)
- **Transform**: Document cleaning → Text splitting → Hash generation → UUID assignment
- **Load**: Parallel indexing (vector + keyword) via ThreadPoolExecutor (10 workers)
- **Retrieval**: Parallel search (embedding + full-text + keyword) → Reranking → Scoring

**Callback System** (`runtime/callbacks/`):
- Observer pattern with lifecycle hooks: `on_before_invoke`, `on_new_chunk`, `on_after_invoke`, `on_invoke_error`
- Used for message recording, logging, event emission
- Triggered during LLM invocations for monitoring and persistence

**Event-Driven Processing** (`event/event_manager.py`):
- Async event emission for decoupled processing
- Events: `qa_rag_from_conversation_message`, `paragraph_rag_from_web_memo`, `agent_from_conversation_message`
- Started in app lifespan, stopped on shutdown

### QA Memory System

A specialized subsystem for automatic Q&A learning from execution feedback:

**Architecture**: MCP Wrapper → QA Memory Service → Milvus + Embeddings

**Lifecycle**:
1. Search → Inject QA references → Execute → Validate → Rank promotion
2. Validation signals (strong/medium/weak) update trust scores and TTL
3. Automatic upgrade (L0 candidate → L1 basic → L2 strong → L3 canonical)
4. Automatic demotion on consecutive failures (active → stale → deprecated)

**Trust Score**: Weighted by signal strength (strong pass: +0.25, strong fail: -0.35, consecutive fails: -0.5 each)

**Key APIs**: `/qa/search`, `/qa/candidates`, `/qa/hit`, `/qa/validate`

### RPC Integration

The app registers itself with Nacos service discovery and exposes RPC endpoints:
- Uses `aduib-rpc` library for service registration and discovery
- Auto-discovers free ports for RPC services
- Registers two services: `{APP_NAME}-app` (HTTP) and RPC service (gRPC/ZMQ)
- RPC services defined in `rpc/service/` (completion, RAG, QA memory)
- Client-side calls in `rpc/client/` (e.g., crawl service)

### Configuration Management

All config lives in `configs/` with Pydantic models:
- `configs/app_config.py` defines `AduibAiConfig` (loaded from environment variables)
- Import via: `from configs import config`
- Supports: database, storage, vector DB, Nacos, deployment, logging, Sentry, task grading
- Feature flags and provider toggles controlled via environment variables

### Anthropic Integration

Native support for Claude models via transformation layer:
- Provider type: `anthropic`
- Models: claude-3-5-sonnet, claude-3-5-haiku, claude-3-opus, etc.
- Request transformation: OpenAI format → Anthropic format (system message extraction)
- Error handling: Auth, rate limit, model not found, server errors with retry strategies
- Test with: `uv run pytest tests/anthropic/ -v`

## Coding Conventions

- **Python version**: 3.11+
- **Indentation**: 4 spaces
- **Type hints**: Required on public functions
- **Naming**:
  - Functions/variables: `snake_case`
  - Classes: `PascalCase`
  - Config keys: `SCREAMING_SNAKE_CASE`
- **Line length**: 120 characters
- **Quotes**: Double quotes
- **Import style**: Lazy imports for heavy runtime components (inside methods) to avoid circular dependencies
- **Error handling**: Raise `BaseServiceError` subclasses from services, catch in controllers

## Testing Guidelines

- Test framework: pytest (config in `pytest.ini`)
- Test structure: `tests/<domain>/<test_file>.py`
- Naming: `test_<feature>_<behavior>()`
- Fixtures: Co-locate in `tests/<domain>/conftest.py`
- Mock external services, but maintain at least one integration test per adapter
- Mark slow/network tests: `@pytest.mark.slow` (filter with `-m "not slow"`)
- Focus on API contracts and critical error paths

## Important Notes

- **Database sessions**: Always use `with get_db() as session:` for automatic cleanup
- **Event emission**: Async operations should emit events rather than blocking
- **Rate limiting**: CompletionService uses `RateLimit` for request throttling
- **Storage**: Accessed via `storage_manager` (configured in `component/storage/`)
- **Vector DB**: Milvus or pgvecto_rs (configured via `configs/vdb/`)
- **Secrets**: Use `.env` file (copy from `.env.example`), never commit secrets
- **Migrations**: Always review auto-generated Alembic migrations before applying
- **Task grading**: New feature for evaluating LLM task quality (see `runtime/tasks/task_grade_drift.py`)
