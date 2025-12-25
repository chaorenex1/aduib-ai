# QA Memory 系统整体方案 — 汇总版

## 1️⃣ 目标（已确认）

构建一套：\
**FastAPI + Milvus + Ollama** 的 QA 记忆系统，\
通过 **MCP（HTTP Wrapper）** 接入 **Codex CLI / Claude Code** 等 codecli，

实现：

- 无需用户确认
- 自动学习（正确案例）
- 自动纠错（失败案例）
- 自动过期（过时知识衰减）

并保持：

- 可审计
- 可扩展
- 不污染知识库

---

## 2️⃣ 核心设计理念（贯穿全系统）

> **确认不再是“动作”，而是“行为副作用”。**

系统只依赖：

1. **使用行为**
2. **执行结果**

来判断：\
是否升级、降级、冻结、废弃。

没有弹窗、没有“是否保存？”这类打断式操作。

---

## 3️⃣ 架构形态（定稿）

```
CodeCLI (Codex / Claude)
        │  (MCP)
        ▼
MCP Wrapper  ——(HTTP)——>  QA Memory Service  ——>  Milvus + Ollama
```

- **MCP Wrapper**\
  做协议适配（工具列表 / hit / validate / 注入引用锚点）

- **QA Memory Service（FastAPI）**\
  负责真正的业务：
  - search
  - candidates
  - hit
  - validate
  - 升级/降级/TTL/排序

- **Milvus**\
  向量召回 + 标量过滤

- **Ollama**\
  Embedding + 分类辅助（可选）

---

## 4️⃣ 主要 API（稳定）

### Memory Service

| 端点               | 功能       |
| ---------------- | -------- |
| `/qa/search`     | 检索 QA    |
| `/qa/candidates` | 写入候选（L1） |
| `/qa/hit`        | 使用/曝光行为  |
| `/qa/validate`   | 执行验证信号   |
| `/qa/{qa_id}`    | 详情       |

---

## 5️⃣ 自动化流程（闭环）

```
检索 → 注入 → 使用 → 执行 → 验证 → 排名提升
```

### 1. 生成前

`retrieve_qa_kb` → `/qa/search`

### 2. 生成中

Wrapper 注入 QA，并添加：

```
[QA_REF qa-xxxx]
```

### 3. 生成后

Wrapper 扫描引用 → `/qa/hit`

### 4. 执行阶段

codecli 运行命令/测试 → `/qa/validate`

---

## 6️⃣ 升级 / 降级策略（核心）

### 升级（L1 → L2）

- 执行 **pass + strong**
- confidence ↑
- TTL 延长
- status=active

### 降级/废弃

- fail ×2 → stale
- fail ×3 → deprecated

> 避免幻觉固化，同时不过早丢弃。

---

## 7️⃣ 排序策略（稳定）

最终打分：

```
final = 0.55 * relevance
       + 0.30 * trust
       + 0.15 * freshness
```

来源：

- relevance：Milvus 距离
- trust：validation + confidence + success rate
- freshness：时间衰减（按 time\_sensitivity）

---

## 8️⃣ MCP Wrapper 的职责（不可精简）

必须包含：

- retrieve\_qa\_kb 工具
- QA 引用注入 (`QA_REF`)
- used/shown 解析
- `/qa/hit` 自动上报
- `/qa/validate` 自动上报
- 不承载业务逻辑

---

## 9️⃣ codecli 自动进入流程（关键）

**无需配置额外按钮**

只要：

1. CLI 支持 MCP
2. CLI 允许运行命令/测试

它就会自然触发：

- 检索
- 注入
- hit
- validate

所有行为都在 **后台自行完成**。