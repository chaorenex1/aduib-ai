# QA Memory Service 基础使用示例

## 环境准备

### 1. 依赖安装

确保项目中包含以下依赖：

```toml
# pyproject.toml
[project]
dependencies = [
    "aduib_rpc>=1.0.10",
    "sqlalchemy==2.0.39",
    "pgvecto_rs>=0.2.0",  # 或其他向量数据库
]
```

### 2. 服务配置

```python
# configs/qa_memory.py
QA_MEMORY_CONFIG = {
    "default_ttl_days": 14,
    "max_ttl_days": 180,
    "search_limit": 8,
    "min_score_threshold": 0.2,
    "vector_dimension": 1536,
}
```

### 3. 数据库初始化

```bash
# 运行数据库迁移
alembic -c ./alembic/alembic.ini upgrade head

# 验证表结构
python -c "
from models import Base, engine
Base.metadata.create_all(engine)
print('QA Memory 表结构就绪')
"
```

## 快速开始

### 示例 1：创建 QA 客户端

```python
# client.py
import asyncio
from typing import Dict, Any

from aduib_rpc.client.rpc_client import RpcClient


class QAMemoryClient:
    """QA Memory Service 客户端封装"""

    def __init__(self, rpc_client: RpcClient):
        self.client = rpc_client
        self.service_name = "QaMemoryService"

    async def retrieve(self, query: str, namespace: str, top_k: int = 8):
        """检索 QA 记忆库"""
        return await self.client.call(
            service=self.service_name,
            method="retrieve_qa_kb",
            args={
                "query": query,
                "namespace": namespace,
                "top_k": top_k,
                "filters": None,
            }
        )

    async def upsert(self, question: str, answer: str, namespace: str, **kwargs):
        """创建/更新 QA 记录"""
        return await self.client.call(
            service=self.service_name,
            method="qa_upsert_candidate",
            args={
                "question_raw": question,
                "answer_raw": answer,
                "namespace": namespace,
                **kwargs
            }
        )

    async def validate(self, qa_id: str, namespace: str, result: str, **kwargs):
        """验证 QA 记录"""
        return await self.client.call(
            service=self.service_name,
            method="qa_validate_and_update",
            args={
                "qa_id": qa_id,
                "namespace": namespace,
                "result": result,
                **kwargs
            }
        )

    async def detail(self, qa_id: str, namespace: str):
        """获取 QA 记录详情"""
        return await self.client.call(
            service=self.service_name,
            method="qa_detail",
            args={
                "qa_id": qa_id,
                "namespace": namespace,
            }
        )

    async def record_hit(self, qa_id: str, namespace: str, **kwargs):
        """记录 QA 使用命中"""
        return await self.client.call(
            service=self.service_name,
            method="qa_record_hit",
            args={
                "qa_id": qa_id,
                "namespace": namespace,
                **kwargs
            }
        )

    async def expire(self, batch_size: int = 200):
        """清理过期记录"""
        return await self.client.call(
            service=self.service_name,
            method="qa_expire",
            args={"batch_size": batch_size}
        )


# 创建客户端实例
async def create_client() -> QAMemoryClient:
    from aduib_rpc.client.rpc_client import RpcClient
    client = RpcClient(
        endpoint="localhost:50051",  # RPC 服务器地址
        timeout=30.0,
        retries=3
    )
    await client.connect()
    return QAMemoryClient(client)
```

### 示例 2：完整的 CRUD 操作流程

```python
# crud_example.py
import asyncio
import uuid
from datetime import datetime
from qa_memory_client import QAMemoryClient, create_client


async def demonstrate_crud_operations():
    """演示完整的 CRUD 操作流程"""

    # 1. 创建客户端
    client = await create_client()
    namespace = "project-demo"

    print("=" * 50)
    print("QA Memory Service CRUD 操作演示")
    print("=" * 50)

    try:
        # 2. 创建 QA 记录
        print("\n1. 创建 QA 记录...")
        create_result = await client.upsert(
            question="如何配置数据库连接池？",
            answer="""
            配置数据库连接池的步骤：
            1. 在应用配置中设置连接池参数
            2. 指定最小/最大连接数
            3. 配置连接超时和空闲时间
            4. 启用连接健康检查
            """,
            namespace=namespace,
            tags=["database", "configuration", "performance"],
            scope={"module": "database", "environment": "production"},
            time_sensitivity="low",
            evidence_refs=["docs/db-config.md", "ops/guidelines.md"]
        )

        qa_id = create_result["record"]["qa_id"]
        print(f"✓ 创建成功，QA ID: {qa_id}")
        print(f"  状态: {create_result['record']['status']}")
        print(f"  信任评分: {create_result['record']['trust_score']:.2f}")
        print(f"  TTL 过期: {create_result['record']['ttl_expire_at']}")

        # 3. 记录使用命中（展示给用户）
        print("\n2. 记录展示命中...")
        hit_result = await client.record_hit(
            qa_id=qa_id,
            namespace=namespace,
            shown=True,
            used=False,
            client={
                "user_id": "user-123",
                "session_id": str(uuid.uuid4()),
                "user_agent": "Mozilla/5.0"
            }
        )
        print(f"✓ 命中记录成功: {hit_result['status']}")

        # 4. 检索相关 QA
        print("\n3. 检索相关 QA 记录...")
        search_result = await client.retrieve(
            query="数据库连接配置",
            namespace=namespace,
            top_k=3
        )

        print(f"✓ 检索到 {search_result['meta']['count']} 条结果:")
        for i, item in enumerate(search_result["results"], 1):
            print(f"  {i}. {item['question'][:50]}...")
            print(f"     相关度: {item['relevance_score']:.2f}")
            print(f"     置信度: {item['confidence']:.2f}")

        # 5. 获取记录详情
        print("\n4. 获取记录详情...")
        detail_result = await client.detail(qa_id=qa_id, namespace=namespace)

        if detail_result.get("status") == "not_found":
            print("✗ 记录不存在")
        else:
            record = detail_result["record"]
            print(f"✓ 获取成功")
            print(f"  问题: {record['question'][:60]}...")
            print(f"  答案长度: {len(record['answer'])} 字符")
            print(f"  使用次数: {record['usage_count']}")
            print(f"  成功验证: {record['success_count']}")
            print(f"  失败验证: {record['failure_count']}")

        # 6. 验证记录（用户反馈）
        print("\n5. 验证记录（用户确认正确）...")
        validate_result = await client.validate(
            qa_id=qa_id,
            namespace=namespace,
            result="pass",
            signal_strength="strong",
            reason="用户确认答案正确且完整",
            evidence_refs=["user-feedback-2025-12-26"],
            client={
                "validator": "user-123",
                "validation_method": "manual_review"
            }
        )

        if validate_result.get("status") == "not_found":
            print("✗ 记录不存在")
        else:
            updated = validate_result["record"]
            print(f"✓ 验证成功")
            print(f"  新状态: {updated['status']}")
            print(f"  新信任评分: {updated['trust_score']:.2f}")
            print(f"  验证级别: {updated['level']}")
            print(f"  新 TTL: {updated['ttl_expire_at']}")

        # 7. 记录使用命中（实际使用）
        print("\n6. 记录实际使用命中...")
        use_result = await client.record_hit(
            qa_id=qa_id,
            namespace=namespace,
            shown=True,
            used=True,
            client={
                "user_id": "user-123",
                "action": "copy_answer",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        print(f"✓ 使用记录成功: {use_result['status']}")

        # 8. 再次获取详情查看统计更新
        print("\n7. 查看更新后的统计...")
        final_detail = await client.detail(qa_id=qa_id, namespace=namespace)
        if final_detail.get("record"):
            final_record = final_detail["record"]
            print(f"  最终使用次数: {final_record['usage_count']}")
            print(f"  最后使用时间: {final_record['last_used_at']}")

        # 9. 执行过期清理（演示）
        print("\n8. 执行过期记录清理...")
        expire_result = await client.expire(batch_size=100)
        print(f"✓ 清理了 {expire_result['expired']} 条过期记录")

    except Exception as e:
        print(f"✗ 操作失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # 清理资源
        await client.client.disconnect()
        print("\n" + "=" * 50)
        print("演示完成")
        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(demonstrate_crud_operations())
```

### 示例 3：批量操作

```python
# batch_operations.py
import asyncio
from typing import List, Dict, Any
from qa_memory_client import QAMemoryClient, create_client


class QAMemoryBatchProcessor:
    """QA Memory 批量操作处理器"""

    def __init__(self, client: QAMemoryClient):
        self.client = client

    async def batch_upsert(
        self,
        namespace: str,
        items: List[Dict[str, Any]],
        concurrency: int = 5
    ) -> List[Dict[str, Any]]:
        """批量创建 QA 记录"""
        import aiohttp

        async def upsert_item(item: Dict[str, Any]) -> Dict[str, Any]:
            try:
                return await self.client.upsert(
                    question=item["question"],
                    answer=item["answer"],
                    namespace=namespace,
                    tags=item.get("tags", []),
                    scope=item.get("scope", {}),
                    time_sensitivity=item.get("time_sensitivity", "medium"),
                    evidence_refs=item.get("evidence_refs", [])
                )
            except Exception as e:
                return {
                    "error": str(e),
                    "item": item,
                    "success": False
                }

        # 使用信号量控制并发
        semaphore = asyncio.Semaphore(concurrency)

        async def upsert_with_semaphore(item):
            async with semaphore:
                return await upsert_item(item)

        tasks = [upsert_with_semaphore(item) for item in items]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        success_count = sum(1 for r in results if not r.get("error"))
        print(f"批量创建完成: {success_count}/{len(items)} 成功")
        return results

    async def batch_validate(
        self,
        namespace: str,
        validations: List[Dict[str, Any]],
        concurrency: int = 3
    ) -> List[Dict[str, Any]]:
        """批量验证 QA 记录"""
        async def validate_item(val: Dict[str, Any]) -> Dict[str, Any]:
            try:
                return await self.client.validate(
                    qa_id=val["qa_id"],
                    namespace=namespace,
                    result=val["result"],
                    signal_strength=val.get("signal_strength", "weak"),
                    reason=val.get("reason", ""),
                    evidence_refs=val.get("evidence_refs", []),
                    client=val.get("client", {})
                )
            except Exception as e:
                return {
                    "error": str(e),
                    "validation": val,
                    "success": False
                }

        semaphore = asyncio.Semaphore(concurrency)

        async def validate_with_semaphore(val):
            async with semaphore:
                return await validate_item(val)

        tasks = [validate_with_semaphore(val) for val in validations]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        success_count = sum(1 for r in results if not r.get("error"))
        print(f"批量验证完成: {success_count}/{len(validations)} 成功")
        return results

    async def export_qa_data(
        self,
        namespace: str,
        query: str = "",
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """导出 QA 数据"""
        all_records = []
        offset = 0
        page_size = 100

        while True:
            # 注意：当前版本不支持分页，这是模拟实现
            # 实际可能需要修改服务端支持分页
            result = await self.client.retrieve(
                query=query if query else "*",
                namespace=namespace,
                top_k=page_size
            )

            if not result["results"]:
                break

            all_records.extend(result["results"])
            offset += len(result["results"])

            print(f"已导出 {len(all_records)} 条记录...")

            if len(result["results"]) < page_size or len(all_records) >= limit:
                break

            # 模拟分页延迟
            await asyncio.sleep(0.1)

        print(f"导出完成，共 {len(all_records)} 条记录")
        return all_records[:limit]


async def batch_operations_demo():
    """批量操作演示"""
    client = await create_client()
    processor = QAMemoryBatchProcessor(client)
    namespace = "project-batch"

    # 1. 批量创建
    print("1. 批量创建 QA 记录...")
    items = [
        {
            "question": f"问题示例 {i}",
            "answer": f"答案示例 {i}，这是详细的解答内容。",
            "tags": [f"tag-{i % 5}", "batch", "demo"],
            "scope": {"batch_id": "batch-2025-12-26", "index": i},
            "time_sensitivity": "low" if i % 3 == 0 else "medium",
        }
        for i in range(1, 11)  # 创建10条记录
    ]

    create_results = await processor.batch_upsert(
        namespace=namespace,
        items=items,
        concurrency=3
    )

    # 提取创建的 QA ID
    qa_ids = []
    for result in create_results:
        if "record" in result:
            qa_ids.append(result["record"]["qa_id"])

    print(f"创建了 {len(qa_ids)} 条记录的 ID")

    # 2. 批量验证（模拟用户反馈）
    print("\n2. 批量验证记录...")
    validations = []
    for i, qa_id in enumerate(qa_ids):
        # 模拟验证结果：80% 通过，20% 失败
        result = "pass" if i % 5 != 0 else "fail"
        signal = "strong" if i % 3 == 0 else "weak"

        validations.append({
            "qa_id": qa_id,
            "result": result,
            "signal_strength": signal,
            "reason": f"批量验证示例 {i+1}",
            "client": {"batch_validation": True, "validator": "auto-batch"}
        })

    validate_results = await processor.batch_validate(
        namespace=namespace,
        validations=validations,
        concurrency=2
    )

    # 3. 导出数据
    print("\n3. 导出 QA 数据...")
    exported = await processor.export_qa_data(
        namespace=namespace,
        query="示例",
        limit=50
    )

    print(f"导出了 {len(exported)} 条记录")
    if exported:
        print("示例记录:")
        for i, record in enumerate(exported[:3], 1):
            print(f"  {i}. ID: {record['qa_id'][:8]}...")
            print(f"     问题: {record['question'][:40]}...")
            print(f"     置信度: {record['confidence']:.2f}")
            print(f"     状态: {record.get('validation_level', 'N/A')}")

    await client.client.disconnect()


if __name__ == "__main__":
    asyncio.run(batch_operations_demo())
```

### 示例 4：集成到现有应用

```python
# integration_example.py
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

from aduib_rpc.client.rpc_client import RpcClient
from qa_memory_client import QAMemoryClient


class ApplicationWithQAMemory:
    """集成 QA Memory 的示例应用"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.qa_client: Optional[QAMemoryClient] = None
        self.namespace = config.get("qa_namespace", "default-app")

    @asynccontextmanager
    async def qa_context(self):
        """QA Memory 上下文管理器"""
        if self.qa_client is None:
            rpc_client = RpcClient(
                endpoint=self.config["rpc_endpoint"],
                timeout=self.config.get("rpc_timeout", 30.0)
            )
            await rpc_client.connect()
            self.qa_client = QAMemoryClient(rpc_client)

        try:
            yield self.qa_client
        finally:
            # 保持连接，不在这里断开
            pass

    async def shutdown(self):
        """关闭连接"""
        if self.qa_client and self.qa_client.client:
            await self.qa_client.client.disconnect()
            self.qa_client = None

    async def handle_user_query(self, user_id: str, query: str) -> Dict[str, Any]:
        """处理用户查询 - 集成 QA Memory"""

        async with self.qa_context() as qa:
            # 1. 检索相关知识
            search_result = await qa.retrieve(
                query=query,
                namespace=self.namespace,
                top_k=3
            )

            # 2. 构建响应
            response = {
                "query": query,
                "suggested_answers": [],
                "context_from_memory": [],
                "found_exact_match": False
            }

            # 3. 处理检索结果
            for item in search_result["results"]:
                # 记录展示命中
                await qa.record_hit(
                    qa_id=item["qa_id"],
                    namespace=self.namespace,
                    shown=True,
                    used=False,
                    client={
                        "user_id": user_id,
                        "query": query,
                        "context": "search_result"
                    }
                )

                response["context_from_memory"].append({
                    "id": item["qa_id"],
                    "question": item["question"],
                    "answer_preview": item["answer"][:100] + "..." if len(item["answer"]) > 100 else item["answer"],
                    "confidence": item["confidence"],
                    "relevance": item["relevance_score"]
                })

                # 检查是否有精确匹配
                if item["relevance_score"] > 0.9:
                    response["found_exact_match"] = True
                    response["suggested_answers"].append(item["answer"])

            # 4. 如果没有找到答案，创建新的候选记录
            if not response["found_exact_match"] and search_result["meta"]["count"] == 0:
                # 这里可以调用 LLM 生成答案
                llm_answer = await self._generate_answer_with_llm(query)

                # 创建新的 QA 候选记录
                create_result = await qa.upsert(
                    question=query,
                    answer=llm_answer,
                    namespace=self.namespace,
                    tags=["user-generated", "pending-validation"],
                    scope={"source": "user_query", "user_id": user_id},
                    time_sensitivity="medium",
                    client={"user_id": user_id, "query": query}
                )

                qa_id = create_result["record"]["qa_id"]
                response["suggested_answers"].append(llm_answer)
                response["new_candidate_created"] = True
                response["new_qa_id"] = qa_id

            return response

    async def collect_user_feedback(
        self,
        user_id: str,
        qa_id: str,
        helpful: bool,
        comments: str = ""
    ) -> Dict[str, Any]:
        """收集用户反馈并更新 QA 记录"""

        async with self.qa_context() as qa:
            result = "pass" if helpful else "fail"
            signal = "strong" if len(comments) > 20 else "weak"

            validation_result = await qa.validate(
                qa_id=qa_id,
                namespace=self.namespace,
                result=result,
                signal_strength=signal,
                reason=f"用户反馈: {comments}" if comments else "用户反馈",
                evidence_refs=[f"user-feedback-{user_id}"],
                client={
                    "user_id": user_id,
                    "feedback_type": "explicit",
                    "comments_length": len(comments)
                }
            )

            # 记录实际使用（因为用户查看了反馈对应的答案）
            await qa.record_hit(
                qa_id=qa_id,
                namespace=self.namespace,
                shown=True,
                used=True,
                client={
                    "user_id": user_id,
                    "action": "provide_feedback",
                    "feedback_helpful": helpful
                }
            )

            return {
                "validation_recorded": True,
                "qa_id": qa_id,
                "new_trust_score": validation_result.get("record", {}).get("trust_score"),
                "new_level": validation_result.get("record", {}).get("level")
            }

    async def get_qa_insights(self) -> Dict[str, Any]:
        """获取 QA 记忆库洞察"""

        async with self.qa_context() as qa:
            # 搜索一些示例查询来获取统计
            test_queries = ["配置", "错误", "如何", "步骤"]
            all_results = []

            for query in test_queries:
                result = await qa.retrieve(
                    query=query,
                    namespace=self.namespace,
                    top_k=5
                )
                all_results.extend(result["results"])

            # 简单分析
            if not all_results:
                return {"total_records": 0, "avg_confidence": 0}

            total_confidence = sum(r["confidence"] for r in all_results)
            avg_confidence = total_confidence / len(all_results)

            levels = {}
            for r in all_results:
                level = r.get("validation_level", 0)
                levels[level] = levels.get(level, 0) + 1

            return {
                "sample_size": len(all_results),
                "average_confidence": round(avg_confidence, 3),
                "level_distribution": levels,
                "suggested_maintenance": levels.get(0, 0) > len(all_results) * 0.5  # 如果超过50%是L0，建议维护
            }

    async def _generate_answer_with_llm(self, query: str) -> str:
        """模拟 LLM 生成答案（实际应集成真实 LLM）"""
        # 这里简化为返回模板答案
        templates = [
            f"关于'{query}'，建议参考官方文档和最佳实践。",
            f"处理'{query}'的常见方法包括：1. 检查配置 2. 查看日志 3. 联系支持",
            f"对于'{query}'问题，通常的解决步骤是：首先确认问题现象，然后排查可能原因，最后实施解决方案。"
        ]
        import random
        return random.choice(templates)


async def integration_demo():
    """集成演示"""

    config = {
        "rpc_endpoint": "localhost:50051",
        "rpc_timeout": 30.0,
        "qa_namespace": "demo-app-integration"
    }

    app = ApplicationWithQAMemory(config)

    try:
        # 模拟用户交互
        user_id = "user-789"

        print("1. 用户查询处理...")
        query = "如何配置应用日志级别"
        response = await app.handle_user_query(user_id, query)

        print(f"查询: {query}")
        print(f"找到匹配: {response['found_exact_match']}")
        print(f"相关记忆: {len(response['context_from_memory'])} 条")
        if response.get('suggested_answers'):
            print(f"建议答案: {response['suggested_answers'][0][:60]}...")

        # 如果有新创建的候选记录，模拟用户反馈
        if response.get("new_candidate_created"):
            qa_id = response["new_qa_id"]
            print(f"\n2. 新记录创建 (ID: {qa_id[:8]}...)，模拟用户反馈...")

            feedback = await app.collect_user_feedback(
                user_id=user_id,
                qa_id=qa_id,
                helpful=True,
                comments="这个答案很有帮助，解决了我的问题"
            )

            print(f"反馈记录: {feedback['validation_recorded']}")
            print(f"新信任评分: {feedback['new_trust_score']}")
            print(f"新级别: {feedback['new_level']}")

        # 获取洞察
        print("\n3. 获取 QA 记忆库洞察...")
        insights = await app.get_qa_insights()
        print(f"样本大小: {insights['sample_size']}")
        print(f"平均置信度: {insights['average_confidence']}")
        print(f"级别分布: {insights['level_distribution']}")
        print(f"建议维护: {insights['suggested_maintenance']}")

    finally:
        await app.shutdown()
        print("\n应用已关闭")


if __name__ == "__main__":
    asyncio.run(integration_demo())
```

## 常见使用场景

### 场景 1：客服机器人集成

```python
class CustomerServiceBot:
    async def answer_question(self, user_question: str, context: Dict[str, Any]):
        # 1. 检索现有知识
        results = await self.qa_client.retrieve(
            query=user_question,
            namespace="customer-service",
            top_k=3
        )

        # 2. 如果有高置信度答案，直接返回
        for item in results["results"]:
            if item["confidence"] > 0.8 and item["relevance_score"] > 0.7:
                await self.qa_client.record_hit(
                    qa_id=item["qa_id"],
                    namespace="customer-service",
                    shown=True,
                    used=True,
                    client={"customer_id": context["customer_id"]}
                )
                return {
                    "answer": item["answer"],
                    "source": "knowledge_base",
                    "confidence": item["confidence"]
                }

        # 3. 否则转人工或生成新答案
        return {"answer": "让我为您查询相关信息...", "source": "escalation"}
```

### 场景 2：开发文档助手

```python
class DevDocAssistant:
    async def search_documentation(self, error_message: str, tech_stack: List[str]):
        # 构建查询
        query = f"{error_message} {' '.join(tech_stack)}"

        results = await self.qa_client.retrieve(
            query=query,
            namespace="dev-docs",
            top_k=5
        )

        # 返回格式化结果
        formatted = []
        for item in results["results"]:
            formatted.append({
                "title": item["question"],
                "solution": item["answer"],
                "tags": item["tags"],
                "confidence": f"{item['confidence']*100:.0f}%",
                "source": item.get("source", {}).get("label", "unknown")
            })

        return formatted
```

### 场景 3：培训知识库

```python
class TrainingKnowledgeBase:
    async def add_training_material(self, topic: str, content: str, trainer: str):
        # 将培训材料拆分为 Q&A 对
        qa_pairs = self._extract_qa_pairs(content)

        for question, answer in qa_pairs:
            await self.qa_client.upsert(
                question=question,
                answer=answer,
                namespace="training",
                tags=[topic, "training-material"],
                scope={"trainer": trainer, "topic": topic},
                time_sensitivity="low",
                evidence_refs=[f"training-session-{datetime.now().date()}"]
            )

    async def assess_knowledge_gap(self, test_results: List[Dict[str, Any]]):
        """根据测试结果识别知识缺口"""
        weak_areas = []

        for result in test_results:
            if result["score"] < 0.7:  # 得分低于70%
                # 搜索相关知识
                related = await self.qa_client.retrieve(
                    query=result["topic"],
                    namespace="training",
                    top_k=3
                )

                weak_areas.append({
                    "topic": result["topic"],
                    "score": result["score"],
                    "suggested_materials": [
                        {"question": item["question"], "answer_preview": item["answer"][:100]}
                        for item in related["results"]
                    ]
                })

        return weak_areas
```

## 故障排除

### 常见问题 1：连接失败

```python
# 错误现象：ConnectionError 或 TimeoutError
# 解决方案：

async def connect_with_retry(endpoint: str, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            client = RpcClient(endpoint=endpoint, timeout=10.0)
            await client.connect()
            return client
        except (ConnectionError, TimeoutError) as e:
            if attempt == max_retries - 1:
                raise
            print(f"连接失败，重试 {attempt + 1}/{max_retries}: {e}")
            await asyncio.sleep(2 ** attempt)  # 指数退避
```

### 常见问题 2：查询无结果

```python
# 错误现象：检索结果为空
# 检查步骤：

async def diagnose_empty_results(namespace: str, query: str):
    client = await create_client()

    # 1. 检查命名空间是否存在记录
    test_query = "*"  # 通配符查询，如果有实现的话
    # 或者查询一个常见词
    test_result = await client.retrieve(
        query="配置",
        namespace=namespace,
        top_k=1
    )

    if test_result["meta"]["count"] == 0:
        print(f"命名空间 '{namespace}' 中没有任何记录")
        # 可能原因：1) 命名空间错误 2) 没有数据 3) 向量数据库未初始化
        return {"issue": "empty_namespace", "suggestion": "检查命名空间或添加初始数据"}

    # 2. 检查查询词
    if len(query.strip()) < 2:
        print(f"查询词过短: '{query}'")
        return {"issue": "short_query", "suggestion": "使用更具体的查询词"}

    # 3. 检查最小分数阈值
    # 尝试降低阈值
    low_threshold_result = await client.retrieve(
        query=query,
        namespace=namespace,
        top_k=5
    )

    if low_threshold_result["meta"]["count"] > 0:
        print(f"降低阈值后找到 {low_threshold_result['meta']['count']} 条结果")
        # 显示分数以供调试
        for item in low_threshold_result["results"]:
            print(f"  - 相关度: {item['relevance_score']:.3f}, 置信度: {item['confidence']:.3f}")
        return {"issue": "high_threshold", "suggestion": "考虑降低min_score参数"}

    return {"issue": "no_matches", "suggestion": "添加相关QA记录或重新表述查询"}
```

### 常见问题 3：性能问题

```python
# 错误现象：响应缓慢
# 优化建议：

async def optimize_performance():
    optimizations = []

    # 1. 检查向量索引
    optimizations.append("确保向量数据库有适当的索引")

    # 2. 批量操作
    optimizations.append("使用批量操作减少网络往返")

    # 3. 适当使用缓存
    optimizations.append("对频繁查询实施客户端缓存")

    # 4. 调整参数
    optimizations.extend([
        "减少top_k参数（如从10降到5）",
        "增加min_score过滤低质量结果",
        "使用更具体的命名空间"
    ])

    # 5. 异步并发
    optimizations.append("使用asyncio.gather并行独立查询")

    return optimizations
```

### 常见问题 4：数据不一致

```python
# 错误现象：数据库记录与向量索引不匹配
# 修复脚本：

async def fix_data_inconsistency(namespace: str):
    """修复数据不一致问题"""
    client = await create_client()

    # 1. 导出所有QA ID
    print("导出所有记录...")
    all_records = []
    # 这里需要实现遍历所有记录的方法
    # 当前版本可能需要分页查询或直接数据库查询

    # 2. 检查向量索引
    print("检查向量索引...")
    # 需要向量数据库的检查方法

    # 3. 重新同步
    print("重新同步不一致的记录...")
    # 对于缺失的记录，重新创建向量索引

    print("修复完成")
    await client.client.disconnect()
```

## 最佳实践总结

1. **连接管理**: 使用连接池和重试机制
2. **错误处理**: 优雅降级，避免单点故障
3. **性能监控**: 记录关键指标和响应时间
4. **数据质量**: 定期验证和清理数据
5. **安全隔离**: 使用不同命名空间隔离项目数据
6. **版本控制**: 记录接口版本和数据结构变更

---

**示例版本**: 1.0
**最后更新**: 2025-12-26
**适用版本**: QA Memory Service v1.0+