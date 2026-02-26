# Contributing to Aduib AI

Thank you for your interest in contributing to Aduib AI! This document provides guidelines and instructions for contributing.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Testing Guidelines](#testing-guidelines)
- [Submitting Changes](#submitting-changes)
- [Reporting Issues](#reporting-issues)

---

## 📜 Code of Conduct

This project follows a Code of Conduct to ensure a welcoming environment for all contributors:

- **Be respectful** - Treat everyone with respect
- **Be collaborative** - Work together constructively
- **Be inclusive** - Welcome diverse perspectives
- **Be professional** - Maintain professionalism in all interactions

---

## 🚀 Getting Started

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/aduib-ai.git
   cd aduib-ai
   ```

3. Add upstream remote:
   ```bash
   git remote add upstream https://github.com/chaorenex1/aduib-ai.git
   ```

### Setup Development Environment

1. **Install UV package manager**:
   ```bash
   pip install uv
   ```

2. **Install dependencies**:
   ```bash
   uv sync --dev
   ```

3. **Setup environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Initialize database**:
   ```bash
   uv run alembic -c alembic/alembic.ini upgrade head
   ```

5. **Run tests to verify setup**:
   ```bash
   uv run pytest
   ```

---

## 🔄 Development Workflow

### Create a Feature Branch

Always create a new branch for your work:

```bash
# Update your main branch
git checkout main
git pull upstream main

# Create a feature branch
git checkout -b feature/your-feature-name
```

### Branch Naming Convention

- **Features**: `feature/description` (e.g., `feature/add-websocket-support`)
- **Bug fixes**: `fix/description` (e.g., `fix/memory-leak-in-agent`)
- **Documentation**: `docs/description` (e.g., `docs/update-api-guide`)
- **Refactoring**: `refactor/description` (e.g., `refactor/simplify-rag-pipeline`)
- **Tests**: `test/description` (e.g., `test/add-integration-tests`)

### Make Your Changes

1. Write your code following our [Code Standards](#code-standards)
2. Add tests for new functionality
3. Update documentation as needed
4. Ensure all tests pass

### Commit Your Changes

Follow conventional commit format:

```bash
git commit -m "feat: add WebSocket support for real-time streaming"
git commit -m "fix: resolve memory leak in agent session management"
git commit -m "docs: update API documentation for new endpoints"
git commit -m "test: add integration tests for RAG pipeline"
```

**Commit Message Format**:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Adding or updating tests
- `refactor:` - Code refactoring
- `perf:` - Performance improvements
- `chore:` - Build process or auxiliary tool changes

---

## 📝 Code Standards

### Python Style Guide

We follow **PEP 8** style guide, enforced by **Ruff**:

```bash
# Format code
uv run ruff format .

# Check for issues
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .
```

### Code Requirements

1. **Type Hints**: Required on all public functions
   ```python
   def process_document(doc: Document) -> ProcessedDocument:
       """Process a document."""
       ...
   ```

2. **Docstrings**: Google-style docstrings for all public functions/classes
   ```python
   def query_knowledge_base(kb_id: str, query: str, top_k: int = 5) -> List[Document]:
       """Query a knowledge base.

       Args:
           kb_id: Knowledge base identifier
           query: Search query
           top_k: Number of results to return

       Returns:
           List of matching documents

       Raises:
           ValueError: If kb_id is invalid
       """
       ...
   ```

3. **Line Length**: Maximum 120 characters

4. **Import Order**:
   - Standard library
   - Third-party packages
   - Local imports

5. **Naming Conventions**:
   - Functions/variables: `snake_case`
   - Classes: `PascalCase`
   - Constants: `SCREAMING_SNAKE_CASE`
   - Private members: `_leading_underscore`

### Code Quality Checklist

- [ ] Code follows PEP 8 style guide
- [ ] All functions have type hints
- [ ] All public functions have docstrings
- [ ] No unused imports or variables
- [ ] No security vulnerabilities (SQL injection, XSS, etc.)
- [ ] Error handling is appropriate
- [ ] Logging is added for important operations

---

## 🧪 Testing Guidelines

### Writing Tests

1. **Test Coverage**: Aim for >80% code coverage
2. **Test Structure**: Use pytest and follow AAA pattern (Arrange, Act, Assert)
   ```python
   def test_document_processing():
       # Arrange
       document = create_test_document()
       processor = DocumentProcessor()

       # Act
       result = processor.process(document)

       # Assert
       assert result.status == "processed"
       assert len(result.chunks) > 0
   ```

3. **Fixtures**: Use fixtures for common test data
   ```python
   @pytest.fixture
   def test_document():
       return Document(content="Test content", metadata={})
   ```

4. **Mocking**: Mock external services
   ```python
   @patch('service.openai_client.create')
   def test_llm_call(mock_create):
       mock_create.return_value = {"text": "Response"}
       # Test implementation
   ```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=. --cov-report=html

# Run specific test file
uv run pytest tests/test_rag_pipeline.py -v

# Run tests matching pattern
uv run pytest -k "test_document" -v

# Skip slow tests
uv run pytest -m "not slow"
```

### Test Types

1. **Unit Tests**: Test individual functions/classes
   - Location: `tests/unit/`
   - Fast, isolated, no external dependencies

2. **Integration Tests**: Test component interactions
   - Location: `tests/integration/`
   - May use database, cache, etc.

3. **End-to-End Tests**: Test full workflows
   - Location: `tests/e2e/`
   - Test complete user scenarios

---

## 📤 Submitting Changes

### Before Submitting

1. **Update your branch**:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run tests**:
   ```bash
   uv run pytest
   ```

3. **Check code style**:
   ```bash
   uv run ruff check .
   ```

4. **Update documentation**:
   - Update README.md if needed
   - Update docstrings
   - Add/update examples

### Create Pull Request

1. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Open Pull Request** on GitHub

3. **Fill PR template**:
   - Clear description of changes
   - Link to related issues
   - Screenshots/examples if applicable
   - Checklist of completed items

### Pull Request Template

```markdown
## Description
Brief description of what this PR does.

## Related Issues
Closes #123

## Changes Made
- Added feature X
- Fixed bug Y
- Updated documentation

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] All tests passing
- [ ] Manual testing completed

## Screenshots
(If applicable)

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Tests added/updated
- [ ] All tests passing
- [ ] No breaking changes
```

### Code Review Process

1. Maintainers will review your PR
2. Address feedback and update PR
3. Once approved, PR will be merged

**Review Criteria**:
- Code quality and style
- Test coverage
- Documentation completeness
- No breaking changes
- Performance impact

---

## 🐛 Reporting Issues

### Before Reporting

1. **Search existing issues** - Check if already reported
2. **Check documentation** - Ensure it's not expected behavior
3. **Try latest version** - Issue may already be fixed

### Creating an Issue

Use appropriate issue template:

#### Bug Report Template

```markdown
**Description**
Clear description of the bug.

**Steps to Reproduce**
1. Step one
2. Step two
3. See error

**Expected Behavior**
What should happen.

**Actual Behavior**
What actually happens.

**Environment**
- OS: [e.g., Ubuntu 22.04]
- Python Version: [e.g., 3.11.5]
- Aduib AI Version: [e.g., 0.1.0]

**Logs/Screenshots**
Relevant error messages or screenshots.
```

#### Feature Request Template

```markdown
**Feature Description**
Clear description of the proposed feature.

**Use Case**
Why is this feature needed?

**Proposed Solution**
How should it work?

**Alternatives Considered**
Other approaches you've considered.

**Additional Context**
Any other relevant information.
```

---

## 💡 Development Tips

### Local Development

1. **Use virtual environment**:
   ```bash
   uv venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows
   ```

2. **Enable pre-commit hooks** (optional):
   ```bash
   uv pip install pre-commit
   pre-commit install
   ```

3. **Use debug logging**:
   ```bash
   export LOG_LEVEL=DEBUG
   python app.py
   ```

### Database Migrations

```bash
# Create new migration
uv run alembic -c alembic/alembic.ini revision --autogenerate -m "description"

# Review generated migration
# Edit alembic/versions/xxxx_description.py if needed

# Apply migration
uv run alembic -c alembic/alembic.ini upgrade head

# Rollback migration
uv run alembic -c alembic/alembic.ini downgrade -1
```

### Debugging

1. **Use Python debugger**:
   ```python
   import pdb; pdb.set_trace()
   ```

2. **Enable verbose logging**:
   ```python
   logging.basicConfig(level=logging.DEBUG)
   ```

3. **Use FastAPI debug mode**:
   ```bash
   uvicorn app:app --reload --log-level debug
   ```

---

## 📚 Additional Resources

- **Documentation**: [docs/](docs/)
- **Architecture Guide**: [docs/architecture.md](docs/architecture.md)
- **API Reference**: [docs/api_reference.md](docs/api_reference.md)
- **CLAUDE.md**: [CLAUDE.md](CLAUDE.md) - Claude Code guidance

---

## ❓ Questions?

- **GitHub Discussions**: For questions and discussions
- **GitHub Issues**: For bug reports and feature requests
- **Email**: 24537608z@gmail.com

---

## 🙏 Thank You!

Your contributions make this project better. We appreciate your time and effort!

**Happy Coding! 🚀**
