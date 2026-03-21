<div align="center">

# Memex-OS

**让 AI 拥有记忆能力 —— 企业级 LLM 应用平台**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116+-009688.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

[核心特性](#-核心特性) • [快速开始](#-快速开始) • [架构设计](#-架构设计) • [记忆系统](#-记忆系统) • [部署](#-部署)

---

## 📋 简介

**Memex-OS** 是一个让大型语言模型真正拥有记忆、经验和持续学习能力的 AI 平台。

不同于传统的 LLM 调用平台，Memex-OS 专注于**记忆管理**：
- 跨会话持久化用户交互历史
- 从成功/失败中提取模式并学习
- 智能检索相关记忆辅助推理
- 知识图谱构建与关系推理

### 🎯 核心能力

| 能力 | 说明 |
|------|------|
| 🧠 **持久记忆** | 向量记忆、图谱记忆、学习引擎，多层记忆体系 |
| 📚 **RAG 引擎** | 混合检索（向量+全文+关键词+重排序） |
| 🤖 **Agent 编排** | 多会话管理、递归工具调用、MCP 扩展 |
| 🔄 **持续学习** | 从反馈中提取信号，自动优化记忆质量 |
| ⚡ **多模型支持** | OpenAI / Claude / DeepSeek / Copilot / 本地模型 |

---

## ✨ 核心特性

### 🧠 记忆系统 (Memory)

```
┌─────────────────────────────────────────────────────────────┐
│                     Memory Architecture                       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │Vector Memory│  │Graph Memory │  │  Learning   │       │
│  │  (Milvus)   │  │  (Neo4j)    │  │   Engine    │       │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │
│         │                │                │                 │
│         └────────────────┼────────────────┘                 │
│                          ▼                                   │
│               ┌─────────────────────┐                        │
│               │   Memory Manager   │                        │
│               └─────────────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

#### 向量记忆
- 基于 Milvus / pgvecto_rs 的语义检索
- 支持多向量场的混合检索
- 可配置的相似度阈值和召回数量

#### 图谱记忆
- Neo4j / Apache AGE 知识图谱
- 实体-关系-实体三元组提取
- 支持多跳关系推理

#### 学习引擎
- **信号评分**: 从执行反馈中提取学习信号
- **质量评分**: 多维度评估记忆质量
- **故障分析**: 识别失败模式并优化
- **洞察提取**: 归纳总结有价值的经验
- **记忆修剪**: 自动清理低价值记忆
- **成本优化**: 平衡效果与资源消耗

### 📚 RAG 引擎

```
文档输入 → 提取(Parse) → 清洗(Clean) → 分块(Split) → 向量化 → 索引
                                      ↓
                              关键词提取 + Hash + UUID
                                      ↓
                              混合索引 (Vector + Keyword)
                                      ↓
                              检索时: Semantic + FullText + Rerank
```

**支持格式**: PDF, Markdown, HTML, Text, Office文档

### 🤖 Agent 系统

| 组件 | 职责 |
|------|------|
| SessionManager | 多会话管理，上下文隔离与共享 |
| MemoryManager | 短时对话记忆 + 长时持久记忆 |
| ToolManager | 内置工具 + MCP 扩展工具 |
| ResponseGenerator | 流式响应生成，工具调用编排 |

**内置工具**: 网页搜索、网页抓取、文件读写、计划管理、Cron调度

### 🔌 多模型支持

| 提供商 | 模型 | 特点 |
|--------|------|------|
| OpenAI | GPT-4, GPT-3.5 | 流式调用，函数调用 |
| Anthropic | Claude 3.5 Sonnet/Opus/Haiku | 长上下文，推理能力 |
| DeepSeek | DeepSeek Chat/Coder | 高性价比 |
| GitHub | Copilot | 代码辅助 |
| OpenRouter | 聚合路由 | 统一访问 |
| Transformers | 本地模型 | 隐私敏感场景 |

---

## 🚀 快速开始

### 环境要求

- Python 3.11+
- PostgreSQL 13+ (关系数据)
- Redis 6.4+ (缓存)
- Milvus 2.3+ 或 pgvecto_rs (向量数据库)

### 安装

```bash
# 1. 克隆项目
git clone https://github.com/your-org/memex-os.git
cd memex-os

# 2. 安装依赖
uv sync --dev

# 或使用镜像
uv pip install -r requirements.txt -i http://mirrors.aliyun.com/pypi/simple/

# 3. 配置环境
cp .env.example .env
# 编辑 .env 填入 API Keys 和数据库配置

# 4. 初始化数据库
uv run alembic -c alembic/alembic.ini revision --autogenerate -m "init"
uv run alembic -c alembic/alembic.ini upgrade head

# 5. 启动服务
python app.py
```

### 验证

```bash
# 健康检查
curl http://localhost:8000/v1/api/health

# 访问 API 文档
# Swagger UI: http://localhost:8000/docs
# ReDoc:      http://localhost:8000/redoc
```

---

## 🏗️ 架构设计

### 系统分层

```
┌─────────────────────────────────────────────────────────────┐
│                    API Layer (FastAPI)                       │
│   Chat │ Agent │ Knowledge │ Model │ Auth │ Memory          │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                   Service Layer                              │
│  CompletionService │ RagService │ AgentService │ MemoryService│
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                   Runtime Layer                              │
│  ModelManager │ RagManager │ ToolManager │ MemoryManager     │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│              Infrastructure Layer                            │
│    Database │ VectorDB │ Storage │ Cache │ EventBus          │
└─────────────────────────────────────────────────────────────┘
```

### 关键设计

| 模式 | 应用场景 |
|------|----------|
| Factory | ModelProvider 实例化，按类型创建 LLM/Embedding/Rerank |
| Strategy | Provider 转换层 (OpenAI↔Anthropic↔DeepSeek) |
| Observer | 回调系统 (on_before_invoke / on_after_invoke) |
| Pipeline | RAG ETL，数据流式处理 |

---

## 📖 API 示例

### 对话补全

```http
POST /v1/chat/completions
X-Api-Key: your_api_key

{
  "model": "claude-3-5-sonnet",
  "messages": [
    {"role": "system", "content": "你是 Memex，一个有记忆的AI助手"},
    {"role": "user", "content": "上次我们讨论的是什么话题？"}
  ],
  "stream": true
}
```

### 记忆检索

```http
POST /v1/api/memory/query
{
  "query": "用户之前提到的项目计划",
  "session_id": "user_123",
  "top_k": 5,
  "memory_types": ["qa", "vector", "graph"]
}
```

### 知识库查询

```http
POST /v1/api/knowledge/{kb_id}/query
{
  "question": "如何配置 Memex 的向量数据库？",
  "top_k": 10,
  "rerank": true
}
```

---

## ⚙️ 配置说明

```bash
# .env 配置示例

# 应用
APP_NAME=memex-os
APP_HOST=0.0.0.0
APP_PORT=8000

# 数据库
DATABASE_URL=postgresql://user:pass@localhost:5432/memex

# 向量数据库
VECTOR_DB_TYPE=milvus
MILVUS_HOST=localhost
MILVUS_PORT=19530

# 存储
STORAGE_TYPE=local
STORAGE_PATH=/data/memex

# 缓存
REDIS_HOST=localhost
REDIS_PORT=6379

# AI Provider Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

---

## 🔧 开发指南

### 项目结构

```
memex-os/
├── app.py                    # 入口
├── app_factory.py            # 应用工厂
├── controllers/              # API 路由
│   ├── chat/                # 对话补全
│   ├── agent/               # Agent 交互
│   ├── knowledge/           # 知识库
│   └── memory/              # 记忆管理
├── service/                  # 业务逻辑
├── runtime/                  # 运行时编排
│   ├── agent/               # Agent 管理
│   ├── model_execution/     # 模型执行
│   ├── rag/                # RAG 管道
│   └── memory/              # 记忆管理
├── component/                # 基础设施
│   ├── storage/            # 存储后端
│   └── vdb/                # 向量数据库
├── models/                   # ORM 模型
└── configs/                  # 配置管理
```

### 代码规范

```bash
# 格式化
uv run ruff format .

# 检查
uv run ruff check .

# 自动修复
uv run ruff check --fix .

# 运行测试
uv run pytest -v

# 特定测试
uv run pytest tests/completion -v
```

---

## 📄 License

Apache License 2.0

---

## 🙏 致谢

- [Vannevar Bush](https://en.wikipedia.org/wiki/Vannevar_Bush) - "As We May Think"
- [FastAPI](https://fastapi.tiangolo.com/) - 现代 Python Web 框架
- [Anthropic](https://www.anthropic.com/) - Claude 模型
- [Milvus](https://milvus.io/) - 向量数据库
- [LangChain](https://www.langchain.com/) - LLM 应用框架启发

---

<div align="center">

**如果 Memex-OS 对你有帮助，请给个 ⭐**

</div>
