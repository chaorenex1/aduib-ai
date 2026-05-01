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
The application uses a custom `AduibAIApp` (subclass of FastAPI) with a factory pattern:
- `app.py` - Entry point that imports the factory
- `app_factory.py` - Creates and configures the app
  - `AduibAIApp` stores `app_home`, `workdir`, `config`, and `extensions` dict
  - Middleware stack (in order): `TraceIdContextMiddleware` → `ApiKeyContextMiddleware` → `PerformanceMetricsMiddleware` (and `LoggingMiddleware` in debug mode)
  - `init_apps()` initializes cache, storage, event manager, and ClickHouse

**Lifespan startup sequence** (`app_factory.lifespan`):
1. RPC service registration with Nacos discovery (background task)
2. Event manager start
3. Memory write task queue start (`MemoryWriteTaskQueueRuntime`)
4. Ensure default admin account exists (`UserService.ensure_admin_exists`)
5. Register builtin agents and start cron scheduler
6. Initialize `AgentManager("supervisor_agent_v3")`

**Lifespan shutdown sequence**:
1. Stop event manager
2. Stop cron scheduler
3. Stop memory write task queue
4. Close database connections

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
- **Policy resolvers**: `StreamingPolicyResolver` and `ThinkingPolicyResolver` determine streaming mode and thinking behavior per request

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

### Memory System

#### Memory Write Pipeline (New)
A state-machine-based pipeline for persisting structured memory from conversations:

**Architecture**: Trigger (`MEMORY_API` or `SESSION_COMMIT`) → Async Task Queue → State Machine → Committed

**Phases** (`runtime/memory/write_state_machine.py`):
1. `PREPARE_EXTRACT_CONTEXT` — Archive source material, build conversation snapshot
2. `EXTRACT_OPERATIONS` — `ReActOrchestrator` plans memory changes (write/edit/delete/ignore) via LLM reasoning with tool use (ls/read/find)
3. `MEMORY_UPDATER` — Resolve document operations, build patch plan, apply mutations, refresh navigation/metadata
4. `COMMITTED` — Finalize with rollback support

**Memory Types** (`runtime/memory/base/enums.py`):
`entity`, `event`, `pattern`, `preference`, `profile`, `review`, `skill`, `solution`, `task`, `tool`, `verification`, `deployment`, `incident`, `rollback`, `runbook`

**Contracts**: All memory structures use strict Pydantic contracts in `runtime/memory/base/contracts.py` (`MemoryContract` base with `extra="forbid"`)

**Task Queue**: `MemoryWriteTaskQueueRuntime` manages an `AsyncTaskQueue` with configurable workers for async memory writes.

#### Memory Retrieval
`MemoryRetrievalService` (`runtime/agent/memory_retrieval_service.py`) provides the read path:
- Agent mode: `MemorySearchRuntime.search_for_current_user()` with session context (last 8 messages)
- Non-agent mode: `MemoryFindRuntime.find_for_current_user()`
- Results formatted as XML `<memory>` tags injected into the prompt

#### QA Memory System (Legacy)
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

## Frontend Project

The frontend lives in a **separate repository** at `~/Documents/aduib-app/memexos-bot` (sibling to this backend). It is a React + TypeScript + Vite + Electron monorepo that consumes this FastAPI backend.

### Tech Stack

- **Framework**: React 19 + TypeScript 5 + Vite 5
- **Desktop**: Electron 31 + electron-vite 2
- **Monorepo**: pnpm 9.x workspace + Turborepo 2
- **UI**: Tailwind CSS 3.4 + shadcn/ui
- **State**: Zustand 4
- **Data Fetching**: TanStack Query 5 + Axios 1
- **Routing**: React Router 6 (browser for web, hash for desktop)

### Workspace Structure

```
apps/
  web/         # PC Web + Mobile Web SPA (@app/web)
  web-ssr/     # Next.js 14 SSR/SSG (@app/web-ssr)
  desktop/     # Electron Desktop (@app/desktop)
packages/
  ui/          # shadcn/ui component library (@repo/ui)
  store/       # Zustand state management (@repo/store)
  request/     # Axios + TanStack Query layer (@repo/request)
  platform/    # Platform abstraction (@repo/platform)
  hooks/       # Shared React hooks (@repo/hooks)
  theme/       # Design tokens + CSS variables (@repo/theme)
  ...
```

**Dependency direction**: `apps → packages` only; packages never import from apps. Packages internal hierarchy: `types ← constants ← utils ← hooks/store/request/...`

### Common Commands (run from frontend root)

```bash
# Install
pnpm install

# Development
pnpm dev:web         # http://localhost:5173
pnpm dev:ssr         # http://localhost:3000
pnpm dev:desktop     # Electron window

# Build
pnpm build:web
pnpm build:desktop

# Quality
pnpm lint
pnpm typecheck
pnpm format

# Testing
pnpm test            # Vitest
pnpm test:e2e        # Playwright
```

### Key Constraints

- **pnpm strict isolation**: Any package imported in source must be listed in that workspace's own `package.json` (no hoisting reliance)
- **Electron security**: Renderer cannot directly access Node APIs; all Node capabilities go through preload + IPC with Zod validation
- **Platform abstraction**: Cross-platform code imports from `@repo/platform`, which dispatches to `web/` or `desktop/` implementations at runtime
- **Tailwind v3.4 only** (do not upgrade to v4); all apps reference `@repo/tailwind-config/preset`
- **Next.js SSR**: Must explicitly list all `@repo/*` packages in `transpilePackages` because packages ship TS source (no build step)

### Full Frontend Guidance

The frontend has its own `CLAUDE.md` at `~/Documents/aduib-app/memexos-bot/CLAUDE.md` with exhaustive architecture details, Electron security rules, scaffolding commands, and workspace constraints.

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
