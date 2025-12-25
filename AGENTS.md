# Repository Guidelines

## Project Structure & Module Organization
FastAPI entry points live in `app.py` and `aduib_app.py`, with `app_factory.py` wiring configs and startup hooks. Domain folders: `component/` (storage, logging, vector adapters), `controllers/` (routes), `service/` (business flows), `models/` (ORM/DTOs), and `runtime/` (provider orchestration). Helpers live in `libs/` and `utils/`, config defaults in `configs/`, migrations in `alembic/`, and docs in `docs/`.

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

## Commit & Pull Request Guidelines
Commits use short imperative subjects such as `Add BLOG_TRANSFORM_PROMPT` or `Refactor web memo processing`. Pull requests should summarize scope, enumerate affected modules, call out config or migration changes (`.env`, `alembic`), and attach screenshots or curl output when responses shift. Reference issue IDs, request reviewers early, and list the commands you ran (pytest, ruff, alembic). Avoid bundling unrelated refactors unless the PR is labeled cleanup.

## Configuration & Operational Notes
Copy `.env.example` to `.env`, populate only needed keys, and keep secrets out of version control. Runtime storage, vector, nacos, and provider toggles live in `configs/` plus `constants/`; gate new integrations behind feature flags or environment variables. Extend `runtime/` managers when adding services so observability stays consistent, and document any new ports or nacos namespaces in `docs/` or the pull request checklist.
