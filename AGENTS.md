# Repository Guidelines

## Project Structure & Module Organization
FastAPI entry points live in `app.py` and `aduib_app.py`, with `app_factory.py` wiring configs and startup hooks. Domain folders: `component/` (storage, logging, vector adapters), `controllers/` (routes), `service/` (business flows), `models/` (ORM/DTOs), and `runtime/` (provider orchestration). Helpers live in `libs/` and `utils/`, config defaults in `configs/`, migrations in `alembic/`, and docs in `docs/`.

## Controller & Service Layering
Keep `controllers/` transport-only and `service/` orchestration-first. Controllers should parse path/query/body inputs, run dependencies, call services, and map results into HTTP responses. Do not place ORM queries, file writes, queue orchestration, provider calls, or multi-step business workflows directly in controllers unless a route is an explicit protocol bridge.

Organize new endpoints by domain and resource rather than action names. Prefer files such as `controllers/memory/memories.py`, `controllers/memory/tasks.py`, and `controllers/mcp/servers.py`; avoid adding new action-style controller files such as `store.py`, `retrieve.py`, or `process.py`. Keep `controllers/route.py` limited to router registration and make sure static routes are registered before conflicting dynamic routes.

Services should own business rules, transaction boundaries, runtime orchestration, task submission, deduplication, and mapping between HTTP DTOs and runtime/domain objects. Do not return FastAPI response objects from services, and do not embed controller-only envelope formatting in `service/`.

For programmer-memory work, follow the domain-first split already established under `service/memory/`:
- Controllers may parse HTTP DTOs from `controllers/memory/schemas.py`, but they must convert those DTOs into service-layer contracts via `service/memory/base/mappers.py` before calling memory services.
- Service implementations under `service/memory/*.py` and `service/memory/repository/*.py` must not import `controllers/memory/schemas.py` directly. Controller DTO awareness is restricted to `service/memory/base/mappers.py`.
- Shared memory-domain contracts, enums, errors, path helpers, builders, and service utility helpers must live under `service/memory/base/` rather than the `service/memory/` root. Use:
  - `service/memory/base/contracts.py`
  - `service/memory/base/enums.py`
  - `service/memory/base/errors.py`
  - `service/memory/base/paths.py`
  - `service/memory/base/builders.py`
  - `service/memory/base/base.py`
- Service-layer inputs and outputs must use models from `service/memory/base/contracts.py`; avoid passing raw controller DTOs or ad-hoc `dict[str, Any]` payloads across service boundaries unless the data is intentionally free-form.
- Memory-domain exceptions must live in `service/memory/base/errors.py` and inherit from the shared `BaseServiceError` path so controller decorators can render them uniformly.
- Memory trigger/state/phase strings must come from `service/memory/base/enums.py`, not scattered string literals.
- Memory path construction and task/idempotency helpers must be centralized in `service/memory/base/paths.py` and `service/memory/base/builders.py`; do not duplicate archive-path, queue-payload, task-id, trace-id, or idempotency-key logic inside controllers or unrelated services.
- Direct database access for programmer-memory belongs in `service/memory/repository/`. Service modules should orchestrate business logic and call repositories rather than opening their own ORM sessions unless there is a strong local reason not to.
- Keep `service/memory/__init__.py` as a slim stable surface that primarily re-exports top-level services and selected repositories. Do not re-expand it into a catch-all export surface for low-level contracts, mappers, builders, enums, errors, or path helpers; import those from `service.memory.base.*` explicitly when needed.
- External callers should prefer `from service.memory import ...` only for stable service/repository entry points; import base-layer internals from `service.memory.base.*` explicitly.

## API & DTO Conventions
Prefer resource-oriented routes for new APIs. Use route families such as `/memories`, `/memories/{memory_id}`, `/memories/tasks`, and `/memories/conversations` for new memory work instead of introducing additional action-style endpoints. Legacy action-style routes may remain temporarily for compatibility, but they should be isolated in explicit legacy modules and should not receive new features.

Do not continue expanding `controllers/params.py` for new feature work. New DTOs should live in the domain that owns them, for example `controllers/memory/schemas.py`, `controllers/mcp/schemas.py`, or `controllers/auth/schemas.py`. Use consistent names such as `*CreateRequest`, `*UpdateRequest`, `*Query`, and `*Response`. For non-trivial query parameters, prefer a dedicated query model over a long list of inline `Query(...)` arguments.

Keep one response envelope style per API family. Existing general APIs may continue using `BaseResponse`, and the programmer-memory draft APIs may continue using their dedicated response model during migration, but do not introduce additional envelope styles without a clear migration plan.

## Build, Test, and Development Commands
- `uv pip install -r requirements.txt` installs runtime dependencies via the Aliyun mirror.
- `uv sync --dev` provisions the managed venv with pytest, ruff, and alembic.
- `uv run uvicorn app:app --reload` starts the API with host and port from `configs/`.
- `uv run alembic -c alembic/alembic.ini upgrade head` applies database migrations.
- `uv run pytest tests/completion -k translate` shows how to target suites or keywords.

## Coding Style & Naming Conventions
Use Python 3.11, 4-space indentation, and type hints on public functions. Follow the domain-first layout (for example, auth controllers stay under `controllers/auth`). Run `uv run ruff format .` and `uv run ruff check .` before committing; rules enforce 120-character lines, double quotes, pep8-naming, pytest-style conventions, and security checks. Keep snake_case for functions and variables, PascalCase for classes, and SCREAMING_SNAKE_CASE for config keys.

## Testing Guidelines
Pytest is the single runner. Name tests `test_<feature>_<behavior>()`, co-locate fixtures in `tests/<domain>/conftest.py`, and mock outbound services while keeping at least one integration test that exercises the adapter under `component/`. Mark slow or network cases so CI can filter (`-m "not slow"`). Focus assertions on API contracts and critical error paths rather than raw coverage.

After each TDD-driven implementation pass that changes code, run the `security-review` skill before considering the task complete. Treat this as a required post-implementation safety gate, especially for API, auth, storage, file, queue, and user-input handling changes.

## Commit & Pull Request Guidelines
Commits use short imperative subjects such as `Add BLOG_TRANSFORM_PROMPT` or `Refactor web memo processing`. Pull requests should summarize scope, enumerate affected modules, call out config or migration changes (`.env`, `alembic`), and attach screenshots or curl output when responses shift. Reference issue IDs, request reviewers early, and list the commands you ran (pytest, ruff, alembic). Avoid bundling unrelated refactors unless the PR is labeled cleanup.

## Configuration & Operational Notes
Copy `.env.example` to `.env`, populate only needed keys, and keep secrets out of version control. Runtime storage, vector, nacos, and provider toggles live in `configs/` plus `constants/`; gate new integrations behind feature flags or environment variables. Extend `runtime/` managers when adding services so observability stays consistent, and document any new ports or nacos namespaces in `docs/` or the pull request checklist.
