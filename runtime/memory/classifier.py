"""基于规则与可选LLM的记忆分类器。"""

from __future__ import annotations

import asyncio
from datetime import datetime
import re
from typing import Any, Optional
from uuid import uuid4

from runtime.memory.types.base import (
    DomainHierarchy,
    FrequencyLevel,
    ImportanceLevel,
    MemoryClassification,
    MemoryDomain,
    MemoryLifecycle,
    MemoryScope,
    MemorySource,
    QAClassification,
    SourceMetadata,
    TimeSensitivity,
)

# 领域关键词，用于快速规则匹配。
DOMAIN_KEYWORDS: dict[MemoryDomain, list[str]] = {
    MemoryDomain.WORK: ["工作", "项目", "会议", "需求", "任务", "职场", "汇报", "OKR"],
    MemoryDomain.LEARNING: ["学习", "课程", "作业", "考试", "课堂", "培训", "教程", "笔记"],
    MemoryDomain.RESEARCH: ["研究", "论文", "实验", "数据集", "假设", "模型", "发表"],
    MemoryDomain.LIFE: ["生活", "家务", "购物", "旅行", "日常", "租房", "搬家", "家庭"],
    MemoryDomain.HEALTH: ["健康", "锻炼", "运动", "饮食", "体检", "睡眠", "生病", "药"],
    MemoryDomain.FINANCE: ["理财", "投资", "股票", "基金", "预算", "开销", "账单", "保险"],
    MemoryDomain.HOBBY: ["爱好", "摄影", "音乐", "绘画", "手工", "烹饪", "园艺", "游戏"],
    MemoryDomain.ENTERTAINMENT: ["电影", "电视剧", "综艺", "演唱会", "娱乐", "追剧", "动漫", "游戏"],
}

# 技术关键词，用于识别技术栈标签。
TECH_PATTERNS: list[str] = [
    "python",
    "javascript",
    "typescript",
    "java",
    "go",
    "rust",
    "fastapi",
    "flask",
    "django",
    "react",
    "vue",
    "redis",
    "milvus",
    "neo4j",
    "postgresql",
    "mysql",
    "docker",
    "kubernetes",
    "aws",
    "git",
    "api",
    "rest",
    "graphql",
]


class MemoryClassifier:
    """基于轻量规则的分类器，可选结合LLM补充推理。"""

    def __init__(self, llm_generator: Optional[Any] = None, config_manager=None) -> None:
        """初始化分类器，llm_generator 可为异步/同步可调用对象。"""

        self._llm_generator = llm_generator
        self._config_manager = config_manager  # ClassificationConfigManager instance
        self._project_patterns: dict[str, str] = {}
        self._module_patterns: dict[str, str] = {}

        # Load initial patterns from config if available
        if self._config_manager:
            self._project_patterns.update(self._config_manager.get_project_patterns())
            self._module_patterns.update(self._config_manager.get_module_patterns())

    async def classify(
        self, content: str, source: MemorySource, context: Optional[dict] = None
    ) -> MemoryClassification:
        """主入口：若提供 LLM 则先尝试 LLM，失败则退化为规则。"""

        baseline = self.classify_sync(content, source, context)

        if self._llm_generator is None:
            return baseline

        try:
            maybe_coro = self._llm_generator(
                content=content,
                source=source,
                context=context or {},
                baseline=baseline.model_dump(mode="python"),
            )
            result = await maybe_coro if asyncio.iscoroutine(maybe_coro) else maybe_coro

            if isinstance(result, MemoryClassification):
                return result
            if isinstance(result, dict):
                # 防御性转换：字段缺失时继续使用基线结果。
                try:
                    return MemoryClassification(**result)
                except Exception:  # noqa: BLE001
                    return baseline
            return baseline
        except Exception:  # noqa: BLE001
            return baseline

    def classify_sync(
        self, content: str, source: MemorySource, context: Optional[dict] = None
    ) -> MemoryClassification:
        """同步规则分类，不依赖外部模型。"""

        ctx = context or {}
        domain = self._infer_domain(content)
        scope = self._infer_scope(ctx, source)
        importance = self._assess_importance(content, domain)
        time_sensitivity = self._infer_time_sensitivity(content, ctx)
        lifecycle = self._infer_lifecycle(importance, time_sensitivity)
        source_metadata = self._extract_source_metadata(source, ctx)

        tags: list[str] = list(dict.fromkeys(ctx.get("tags", [])))
        tech_stack = self._extract_tech_stack(content)
        if tech_stack:
            tags = list(dict.fromkeys(tags + tech_stack))

        project = self._match_project(content, ctx)
        module = self._match_module(content, ctx)

        # Auto-learning: Look for potential project/module patterns
        if self._config_manager and domain == MemoryDomain.WORK:
            self._auto_learn_patterns(content, project, module)

        domain_hierarchy = DomainHierarchy(
            domain=domain,
            project=project,
            module=module,
            topic=ctx.get("topic"),
            task_type=ctx.get("task_type"),
            tags=tags,
        )

        qa_classification = None
        if source == MemorySource.QA or ctx.get("force_qa"):
            qa_classification = self._build_qa_classification(
                content=content,
                context=ctx,
                domain=domain,
                importance=importance,
                time_sensitivity=time_sensitivity,
                tech_stack=tech_stack,
            )

        return MemoryClassification(
            source=source,
            domain=domain,
            scope=scope,
            lifecycle=lifecycle,
            source_metadata=source_metadata,
            domain_hierarchy=domain_hierarchy,
            qa_classification=qa_classification,
            tags=tags,
            inferred_topics=self._infer_topics(content),
            inferred_entities=self._infer_entities(content),
        )

    async def classify_qa(
        self, content: str, context: Optional[dict] = None
    ) -> QAClassification:
        """问答场景专用分类，异步签名便于未来接入 LLM。"""

        ctx = context or {}
        domain = self._infer_domain(content)
        importance = self._assess_importance(content, domain)
        time_sensitivity = self._infer_time_sensitivity(content, ctx)
        tech_stack = self._extract_tech_stack(content)

        return self._build_qa_classification(
            content=content,
            context=ctx,
            domain=domain,
            importance=importance,
            time_sensitivity=time_sensitivity,
            tech_stack=tech_stack,
        )

    def _extract_source_metadata(
        self, source: MemorySource, context: Optional[dict]
    ) -> SourceMetadata:
        """构造来源元数据，缺省字段自动填补。"""

        ctx = context or {}
        return SourceMetadata(
            source=source,
            source_id=str(ctx.get("source_id") or ctx.get("id") or uuid4()),
            source_uri=ctx.get("source_uri"),
            created_by=ctx.get("created_by", "user"),
            session_id=ctx.get("session_id"),
            timestamp=ctx.get("timestamp", datetime.now()),
        )

    def _infer_domain(self, content: str) -> MemoryDomain:
        """依据关键词推断领域，未命中时回退为 GENERAL。"""

        for domain, keywords in DOMAIN_KEYWORDS.items():
            if any(keyword in content for keyword in keywords):
                return domain
        return MemoryDomain.GENERAL

    def _infer_scope(self, context: dict, source: MemorySource) -> MemoryScope:
        """优先利用上下文字段，其次依据来源推断作用域。"""

        scope_val = context.get("scope")
        if isinstance(scope_val, MemoryScope):
            return scope_val
        if isinstance(scope_val, str):
            try:
                return MemoryScope(scope_val)
            except ValueError:
                pass

        if context.get("module"):
            return MemoryScope.MODULE
        if context.get("project"):
            return MemoryScope.PROJECT
        if source in {MemorySource.AGENT_TASK, MemorySource.ACTION, MemorySource.CODE}:
            return MemoryScope.WORK
        return MemoryScope.PERSONAL

    def _infer_lifecycle(
        self, importance: ImportanceLevel, time_sensitivity: TimeSensitivity
    ) -> MemoryLifecycle:
        """结合重要性与时间敏感度推断生命周期。"""

        if importance == ImportanceLevel.CRITICAL or time_sensitivity == TimeSensitivity.PERMANENT:
            return MemoryLifecycle.PERMANENT
        if importance == ImportanceLevel.HIGH or time_sensitivity == TimeSensitivity.STABLE:
            return MemoryLifecycle.LONG
        if time_sensitivity == TimeSensitivity.EVOLVING:
            return MemoryLifecycle.SHORT
        return MemoryLifecycle.TRANSIENT

    def _assess_importance(self, content: str, domain: MemoryDomain) -> ImportanceLevel:
        """基于词汇与领域的启发式重要性评估。"""

        critical_markers = ["紧急", "立即", "立刻", "崩溃", "故障", "停机", "deadline", "上线", "发布", "bug"]
        high_markers = ["风险", "合规", "审批", "签署", "交付", "目标", "里程碑", "设计", "方案"]

        if any(marker in content for marker in critical_markers):
            return ImportanceLevel.CRITICAL
        if domain in {MemoryDomain.HEALTH, MemoryDomain.FINANCE} and any(
            marker in content for marker in high_markers
        ):
            return ImportanceLevel.HIGH
        if len(content) > 400 or domain in {MemoryDomain.WORK, MemoryDomain.RESEARCH, MemoryDomain.LEARNING}:
            return ImportanceLevel.MEDIUM
        return ImportanceLevel.LOW

    def _infer_time_sensitivity(self, content: str, context: dict) -> TimeSensitivity:
        """解析时间相关词汇，无法识别时视为 STABLE。"""

        ctx_value = context.get("time_sensitivity")
        if isinstance(ctx_value, TimeSensitivity):
            return ctx_value
        if isinstance(ctx_value, str):
            try:
                return TimeSensitivity(ctx_value)
            except ValueError:
                pass

        lower_text = content.lower()
        if any(word in content for word in ["今天", "立即", "马上", "尽快", "今晚", "本周", "明天", "deadline", "截至"]):
            return TimeSensitivity.VOLATILE
        if any(word in content for word in ["迭代", "更新", "计划", "版本", "阶段", "季度", "下周", "本月"]):
            return TimeSensitivity.EVOLVING
        if any(word in content for word in ["长期", "规范", "标准", "永久", "归档", "最佳实践"]):
            return TimeSensitivity.PERMANENT
        if re.search(r"\beod\b|\bq[1-4]\b", lower_text):
            return TimeSensitivity.EVOLVING
        return TimeSensitivity.STABLE

    def _extract_tech_stack(self, content: str) -> list[str]:
        """提取技术关键词作为标签。"""

        lower_text = content.lower()
        found: list[str] = []
        for pattern in TECH_PATTERNS:
            if pattern in lower_text and pattern not in found:
                found.append(pattern)
        return found

    def register_project_pattern(self, pattern: str, project: str) -> None:
        """登记项目名匹配规则，pattern 为小写关键片段。"""

        self._project_patterns[pattern.lower()] = project

    def register_module_pattern(self, pattern: str, module: str) -> None:
        """登记模块匹配规则。"""

        self._module_patterns[pattern.lower()] = module

    def _match_project(self, content: str, context: dict) -> Optional[str]:
        """优先上下文，其次规则匹配。"""

        if context.get("project"):
            return context["project"]

        lowered = content.lower()
        for pattern, project in self._project_patterns.items():
            if pattern in lowered:
                return project
        return None

    def _match_module(self, content: str, context: dict) -> Optional[str]:
        """优先上下文，其次规则匹配模块。"""

        if context.get("module"):
            return context["module"]

        lowered = content.lower()
        for pattern, module in self._module_patterns.items():
            if pattern in lowered:
                return module
        return None

    def _build_qa_classification(
        self,
        content: str,
        context: dict,
        domain: MemoryDomain,
        importance: ImportanceLevel,
        time_sensitivity: TimeSensitivity,
        tech_stack: Optional[list[str]] = None,
    ) -> QAClassification:
        """生成问答分类结果，技术栈与频率自动补全。"""

        tech_stack = tech_stack or self._extract_tech_stack(content)
        frequency = self._infer_frequency(content, context)

        task_type = context.get("task_type")
        if task_type is None:
            lower_text = content.lower()
            if "bug" in lower_text or "故障" in content:
                task_type = "bugfix"
            elif "需求" in content or "feature" in lower_text:
                task_type = "feature"

        topic = context.get("topic") or (tech_stack[0] if tech_stack else None)

        return QAClassification(
            project=self._match_project(content, context),
            module=self._match_module(content, context),
            topic=topic,
            task_type=task_type,
            tech_stack=tech_stack,
            importance=importance,
            frequency=frequency,
            time_sensitivity=time_sensitivity,
        )

    def _infer_frequency(self, content: str, context: dict) -> FrequencyLevel:
        """基于习惯性词汇推测出现频率。"""

        freq_val = context.get("frequency")
        if isinstance(freq_val, FrequencyLevel):
            return freq_val
        if isinstance(freq_val, str):
            try:
                return FrequencyLevel(freq_val)
            except ValueError:
                pass

        if any(word in content for word in ["每天", "每日", "日常", "每天都", "早晚"]):
            return FrequencyLevel.DAILY
        if any(word in content for word in ["每周", "周会", "周报", "每周一次"]):
            return FrequencyLevel.WEEKLY
        if any(word in content for word in ["偶尔", "有时", "阶段性", "临时"]):
            return FrequencyLevel.OCCASIONAL
        if any(word in content for word in ["很少", "罕见", "极少"]):
            return FrequencyLevel.RARE
        return FrequencyLevel.OCCASIONAL

    def _infer_topics(self, content: str) -> list[str]:
        """极简主题提取：基于技术栈与标点切分的短片段。"""

        tech_stack = self._extract_tech_stack(content)
        if tech_stack:
            return tech_stack[:3]

        snippets = re.split(r"[。！？!?.，,\n]\s*", content)
        snippets = [s.strip() for s in snippets if s.strip()]
        return snippets[:2]

    def _infer_entities(self, content: str) -> list[str]:
        """通过简单模式抓取邮箱、@标记等实体。"""

        entities: list[str] = []
        for match in re.findall(r"[\w.-]+@[\w.-]+", content):
            entities.append(match)
        for match in re.findall(r"@([\w-]{2,40})", content):
            entities.append(match)
        return list(dict.fromkeys(entities))

    def _auto_learn_patterns(self, content: str, current_project: Optional[str], current_module: Optional[str]) -> None:
        """Auto-learn potential project/module patterns from content."""
        if not self._config_manager:
            return

        # Extract potential project names from content
        potential_projects = self._extract_potential_projects(content)
        potential_modules = self._extract_potential_modules(content)

        # Learn project patterns
        for candidate in potential_projects:
            if not current_project or candidate.lower() != current_project.lower():
                self._config_manager.add_candidate_pattern(
                    pattern=candidate.lower(),
                    project=candidate,
                    content_sample=content
                )

        # Learn module patterns
        for candidate in potential_modules:
            if not current_module or candidate.lower() != current_module.lower():
                self._config_manager.add_candidate_pattern(
                    pattern=candidate.lower(),
                    module=candidate,
                    content_sample=content
                )

    def _extract_potential_projects(self, content: str) -> list[str]:
        """Extract potential project names from content."""
        candidates = []

        # Look for project-like patterns
        patterns = [
            r'([a-z]+[-_][a-z]+(?:[-_][a-z]+)*)',  # multi-word with separators
            r'(\b[A-Z][a-z]+[A-Z][a-z]+\b)',      # CamelCase
            r'([a-z]+ (?:project|platform|system|service|app|application))',  # explicit project words
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content.lower())
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                if len(match) >= 3 and match not in ['the', 'and', 'for', 'with']:
                    candidates.append(match.strip())

        return list(set(candidates))[:5]  # Limit to top 5

    def _extract_potential_modules(self, content: str) -> list[str]:
        """Extract potential module names from content."""
        candidates = []

        # Look for module-like patterns
        patterns = [
            r'([a-z]+/[a-z]+(?:/[a-z]+)*)',       # path-like modules
            r'(runtime/[a-z]+)',                   # runtime modules
            r'(controllers?/[a-z]+)',              # controller modules
            r'(services?/[a-z]+)',                 # service modules
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content.lower())
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                if len(match) >= 3:
                    candidates.append(match.strip())

        return list(set(candidates))[:5]  # Limit to top 5

    def reload_patterns_from_config(self) -> None:
        """Reload patterns from configuration manager."""
        if self._config_manager:
            self._project_patterns = self._config_manager.get_project_patterns()
            self._module_patterns = self._config_manager.get_module_patterns()
