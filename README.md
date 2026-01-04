<div align="center">

# 🤖 Aduib AI

**Production-Ready LLM Application Platform**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116+-009688.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

[Features](#-features) • [Quick Start](#-quick-start) • [Architecture](#-architecture) • [API Docs](#-api-documentation) • [Deployment](#-deployment)

</div>

---

## 📋 Overview

**Aduib AI** is a comprehensive, production-ready platform for building LLM-powered applications. It provides a unified API for multiple AI providers, RAG capabilities, knowledge management, and intelligent agent orchestration.

### 🎯 Key Highlights

- **🔌 Multi-Provider Support** - Seamlessly switch between OpenAI, Anthropic, DeepSeek, GitHub Copilot, and more
- **📚 RAG Engine** - Built-in Retrieval-Augmented Generation with vector databases (Milvus, pgvecto_rs)
- **🧠 Knowledge Management** - Advanced document processing, chunking, and semantic search
- **🤵 Intelligent Agents** - Agentic workflows with tool calling and memory management
- **💾 Task Caching** - Intelligent caching system to reduce costs and improve response times
- **🎓 QA Memory** - Self-improving Q&A system that learns from execution feedback
- **🔄 MCP Integration** - Model Context Protocol support for extensible tool ecosystems
- **⚡ High Performance** - Async architecture with event-driven processing

---

## ✨ Features

### 🤖 LLM Capabilities

- **Multi-Model Support**
  - OpenAI-compatible APIs (GPT-4, GPT-3.5, etc.)
  - Anthropic Claude (Sonnet, Opus, Haiku)
  - DeepSeek models
  - GitHub Copilot integration
  - OpenRouter support
  - Local models via Transformers

- **Advanced Features**
  - Streaming responses
  - Function/tool calling
  - Multi-turn conversations
  - System prompt management
  - Token usage tracking
  - Rate limiting

### 📊 RAG & Knowledge Management

- **Document Processing Pipeline**
  - Multiple format support (PDF, Markdown, HTML, Text)
  - Intelligent text chunking
  - Entity extraction
  - Keyword generation
  - Parallel indexing (10 workers)

- **Retrieval Strategies**
  - Semantic search (embedding-based)
  - Full-text search
  - Keyword matching
  - Hybrid search with reranking
  - Configurable scoring algorithms

- **Vector Databases**
  - Milvus (production-grade)
  - pgvecto_rs (PostgreSQL extension)
  - Easy switching via configuration

### 🎯 Agent System

- **Modular Architecture**
  - Session management
  - Short-term & long-term memory
  - Tool orchestration
  - Recursive tool calling
  - Callback system for monitoring

- **Built-in Tools**
  - Current time
  - Weather information
  - Custom tool integration via MCP

### 💡 Smart Features

- **Task Caching**
  - Request deduplication
  - Automatic cache invalidation
  - Hit tracking and analytics
  - Configurable TTL

- **QA Memory System**
  - Automatic Q&A learning from feedback
  - Multi-level validation (L0-L3)
  - Trust scoring
  - Automatic promotion/demotion
  - TTL-based lifecycle management

- **Performance Optimization**
  - Connection pooling
  - Event-driven async processing
  - ThreadPoolExecutor for CPU-bound tasks
  - Lazy loading for heavy components

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **PostgreSQL 13+** (or compatible database)
- **Redis** (optional, for caching)
- **Vector Database** (Milvus or pgvecto_rs)

### Installation

1. **Install UV package manager**
   ```bash
   # macOS
   brew install uv

   # Windows
   choco install uv

   # Or via pip
   pip install uv
   ```

2. **Clone and setup**
   ```bash
   git clone https://github.com/chaorenex1/aduib-ai.git
   cd aduib-ai

   # Install dependencies
   uv sync --dev

   # Or with custom mirror
   uv pip install -r requirements.txt -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and database credentials
   ```

4. **Initialize database**
   ```bash
   # Run migrations
   uv run alembic -c alembic/alembic.ini upgrade head
   ```

5. **Start the server**
   ```bash
   # Development mode with auto-reload
   python app.py

   # Or production mode
   python scripts/start_stack.py
   ```

6. **Access the API**
   - **Swagger UI**: http://localhost:8000/docs
   - **ReDoc**: http://localhost:8000/redoc
   - **Health Check**: http://localhost:8000/v1/api/health

---

## 🏗️ Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     API Layer (FastAPI)                      │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐  │
│  │  Chat    │  Agent   │Knowledge │   Model  │   Auth   │  │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   Service Layer                              │
│  ┌──────────────┬──────────────┬──────────────┐            │
│  │ Completion   │ RAG Manager  │ Agent Manager │            │
│  │   Service    │              │               │            │
│  └──────────────┴──────────────┴──────────────┘            │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                Runtime Layer                                 │
│  ┌──────────────┬──────────────┬──────────────┐            │
│  │   Model      │     RAG      │    Tool      │            │
│  │   Manager    │   Pipeline   │   Manager    │            │
│  └──────────────┴──────────────┴──────────────┘            │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│              Infrastructure Layer                            │
│  ┌──────────┬──────────┬──────────┬──────────┐            │
│  │ Database │  Vector  │  Storage │  Cache   │            │
│  │   (PG)   │    DB    │ (S3/Local│ (Redis)  │            │
│  └──────────┴──────────┴──────────┴──────────┘            │
└──────────────────────────────────────────────────────────────┘
```

### Design Patterns

- **Factory Pattern**: Model provider instantiation
- **Strategy Pattern**: Provider-specific API transformations
- **Observer Pattern**: Callback system for LLM invocations
- **Repository Pattern**: Database access abstraction
- **Dependency Injection**: Configuration and service management

### Key Components

#### 1. Model Provider System
- Abstracted provider interface
- Transformation layer for API compatibility
- Automatic retry with exponential backoff
- Error mapping and handling

#### 2. RAG Pipeline
```
Extract → Transform → Load
   ↓         ↓         ↓
 Parse    Clean    Index
          Split   (Vector + Keyword)
         Dedupe
```

#### 3. Agent Execution Flow
```
User Input → Session → Memory Retrieval → LLM Call
                ↓           ↓               ↓
            Tool Call → Tool Execution → Response
                            ↓
                      Callback Events
```

---

## 📖 API Documentation

### Core Endpoints

#### Chat Completion
```http
POST /v1/chat/completions
Content-Type: application/json
X-Api-Key: your_api_key

{
  "model": "claude-3-5-sonnet",
  "messages": [
    {"role": "user", "content": "Hello!"}
  ],
  "stream": true
}
```

#### Knowledge Base Management
```http
# Create knowledge base
POST /v1/api/knowledge

# Upload document
POST /v1/api/knowledge/{kb_id}/documents

# Query knowledge
POST /v1/api/knowledge/{kb_id}/query
```

#### Agent Interaction
```http
POST /v1/api/agent/chat
{
  "agent_id": "agent_123",
  "message": "What's the weather?",
  "session_id": "session_456"
}
```

#### Task Cache
```http
# Query cache
POST /v1/api/cache/query
{
  "prompt": "Translate 'Hello' to Spanish",
  "model": "gpt-4"
}

# Save to cache
POST /v1/api/cache/save
```

#### QA Memory
```http
# Search QA pairs
POST /v1/api/qa/search
{
  "question": "How to configure Redis?",
  "top_k": 5
}

# Validate answer
POST /v1/api/qa/validate
{
  "qa_id": "qa_123",
  "signal": "strong_pass"
}
```

### Full API Documentation

Visit `/docs` for interactive Swagger UI or `/redoc` for ReDoc documentation.

---

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Application
APP_NAME=aduib-ai
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/aduib_ai

# Vector Database (choose one)
VECTOR_DB_TYPE=milvus  # or pgvecto_rs
MILVUS_HOST=localhost
MILVUS_PORT=19530

# Storage
STORAGE_TYPE=local  # or s3, opendal
STORAGE_PATH=/data/storage

# Cache
REDIS_HOST=localhost
REDIS_PORT=6379

# Nacos (optional, for service discovery)
NACOS_SERVER_ADDRESSES=localhost:8848
NACOS_NAMESPACE=dev

# Sentry (optional, for error tracking)
SENTRY_DSN=https://...
```

### Configuration Files

All configurations are in `configs/` directory:

- `app_config.py` - Main application config
- `db/` - Database settings
- `vdb/` - Vector database config
- `storage/` - Storage backend config
- `rag/` - RAG pipeline settings
- `task_grade/` - Task grading config
- `task_cache_config.py` - Task caching settings

---

## 🚢 Deployment

### Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install uv && uv sync --no-dev

EXPOSE 8000
CMD ["python", "app.py"]
```

```bash
# Build and run
docker build -t aduib-ai .
docker run -p 8000:8000 --env-file .env aduib-ai
```

### Docker Compose

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/aduib_ai
      - REDIS_HOST=redis
    depends_on:
      - db
      - redis
      - milvus

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: aduib_ai
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine

  milvus:
    image: milvusdb/milvus:latest
    ports:
      - "19530:19530"

volumes:
  postgres_data:
```

### Production Considerations

1. **Database**
   - Use connection pooling
   - Enable query logging for debugging
   - Regular backups

2. **Caching**
   - Redis cluster for high availability
   - Set appropriate TTLs

3. **Monitoring**
   - Enable Sentry for error tracking
   - Use Prometheus metrics
   - Set up health check endpoints

4. **Security**
   - Use API key authentication
   - Enable HTTPS
   - Rate limiting per API key
   - Input validation

---

## 🔧 Development

### Project Structure

```
aduib-ai/
├── app.py                  # Application entry point
├── app_factory.py          # App factory with middleware setup
├── alembic/                # Database migrations
├── component/              # Infrastructure components
│   ├── cache/             # Redis cache implementation
│   ├── log/               # Logging configuration
│   ├── storage/           # Storage backends (local, S3, OpenDAL)
│   └── vdb/               # Vector database adapters
├── configs/                # Configuration modules
├── constants/              # Application constants
├── controllers/            # API endpoints
│   ├── agent/             # Agent endpoints
│   ├── chat/              # Chat completion endpoints
│   ├── knowledge/         # Knowledge base endpoints
│   ├── model/             # Model management
│   ├── qa_memory/         # QA memory endpoints
│   └── task_cache/        # Task cache endpoints
├── event/                  # Event system
├── libs/                   # Shared libraries
├── models/                 # SQLAlchemy ORM models
├── runtime/                # Runtime components
│   ├── agent/             # Agent manager
│   ├── model_execution/   # Model execution
│   ├── rag/               # RAG pipeline
│   ├── tool/              # Tool management
│   └── transformation/    # Provider transformations
├── service/                # Business logic layer
├── tests/                  # Test suite
└── utils/                  # Utility functions
```

### Development Commands

```bash
# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Auto-fix linting issues
uv run ruff check --fix .

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=. --cov-report=html

# Run specific test suite
uv run pytest tests/completion -v

# Database migrations
uv run alembic -c alembic/alembic.ini revision --autogenerate -m "description"
uv run alembic -c alembic/alembic.ini upgrade head
```

### Coding Standards

- **Python Version**: 3.11+
- **Style Guide**: Follow PEP 8, enforced by Ruff
- **Type Hints**: Required on all public functions
- **Docstrings**: Google-style docstrings
- **Line Length**: 120 characters max
- **Import Order**: stdlib → third-party → local

### Testing Guidelines

- Write tests for all new features
- Maintain >80% code coverage
- Use fixtures for common test data
- Mock external services
- Mark slow tests with `@pytest.mark.slow`

---

## 🗺️ Roadmap

- [ ] **WebSocket Support** - Real-time streaming
- [ ] **Multi-tenancy** - Tenant isolation and management
- [ ] **Plugin System** - Dynamic plugin loading
- [ ] **Advanced Analytics** - Usage analytics dashboard
- [ ] **GraphQL API** - Alternative API interface
- [ ] **Kubernetes Deployment** - K8s manifests and Helm charts
- [ ] **Prompt Templates** - Template management system
- [ ] **A/B Testing** - Experiment framework
- [ ] **Fine-tuning Pipeline** - Model fine-tuning support

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Contribution Guidelines

- Follow the coding standards
- Add tests for new features
- Update documentation
- Ensure all tests pass
- Keep PR scope focused

---

## 📄 License

This project is licensed under the **Apache License 2.0** - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [LangChain](https://www.langchain.com/) - LLM application framework
- [Anthropic](https://www.anthropic.com/) - Claude API
- [OpenAI](https://openai.com/) - GPT models
- [Milvus](https://milvus.io/) - Vector database

---

## 📞 Support

- **Documentation**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/yourusername/aduib-ai/issues)
- **Email**: 24537608z@gmail.com

---

<div align="center">

**⭐ Star this repository if you find it helpful!**

Made with ❤️ by [chaorenex1](https://github.com/chaorenex1)

</div>
