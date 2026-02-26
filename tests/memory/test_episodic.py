"""测试 EpisodicMemory 类型模块。"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

import pytest

from runtime.memory.storage.adapter import StorageAdapter
from runtime.memory.types import Memory, MemoryMetadata, MemoryType
from runtime.memory.types.episodic import EpisodicMemory


class MockStorageAdapter(StorageAdapter):
    """模拟存储适配器用于测试。"""

    def __init__(self) -> None:
        self.memories: dict[str, Memory] = {}
        self.save_calls: list[Memory] = []
        self.get_calls: list[str] = []
        self.list_calls: list[str] = []

    async def save(self, memory: Memory) -> str:
        """保存记忆。"""
        self.save_calls.append(memory)
        self.memories[memory.id] = memory
        return memory.id

    async def get(self, memory_id: str) -> Optional[Memory]:
        """获取记忆。"""
        self.get_calls.append(memory_id)
        return self.memories.get(memory_id)

    async def update(self, memory_id: str, updates: dict) -> Optional[Memory]:
        """更新记忆。"""
        if memory_id in self.memories:
            memory = self.memories[memory_id]
            for key, value in updates.items():
                setattr(memory, key, value)
            return memory
        return None

    async def delete(self, memory_id: str) -> bool:
        """删除记忆。"""
        if memory_id in self.memories:
            del self.memories[memory_id]
            return True
        return False

    async def exists(self, memory_id: str) -> bool:
        """检查记忆是否存在。"""
        return memory_id in self.memories

    async def list_by_session(self, session_id: str) -> list[Memory]:
        """按会话列出记忆。"""
        self.list_calls.append(session_id)
        return [
            memory for memory in self.memories.values()
            if memory.metadata.session_id == session_id and memory.type == MemoryType.EPISODIC
        ]


def _make_episode(
    episode_id: Optional[str] = None,
    content: str = "用户问了关于 Python 的问题",
    session_id: str = "session-1",
    event_type: str = "chat_interaction",
    duration: float = 30.0,
    sequence: int = 1
) -> Memory:
    """创建一个测试用的 episode 记忆。"""
    memory_id = episode_id or str(uuid4())
    metadata = MemoryMetadata(
        session_id=session_id,
        user_id="user-123",
        extra={
            "event_type": event_type,
            "duration": duration,
            "sequence_number": sequence
        }
    )
    return Memory(
        id=memory_id,
        type=MemoryType.EPISODIC,
        content=content,
        metadata=metadata,
        importance=0.7
    )


@pytest.mark.asyncio
async def test_add_episode() -> None:
    """测试添加新的 episode。"""
    adapter = MockStorageAdapter()
    episodic = EpisodicMemory(adapter)

    content = "用户询问了如何使用 FastAPI"
    session_id = "sess-1"
    event_type = "question"
    duration = 45.0

    episode_id = await episodic.add_episode(
        content=content,
        session_id=session_id,
        user_id="user-456",
        event_type=event_type,
        duration=duration,
        importance=0.8
    )

    # 验证保存调用
    assert len(adapter.save_calls) == 1
    saved_memory = adapter.save_calls[0]

    assert saved_memory.type == MemoryType.EPISODIC
    assert saved_memory.content == content
    assert saved_memory.metadata.session_id == session_id
    assert saved_memory.metadata.user_id == "user-456"
    assert saved_memory.metadata.extra["event_type"] == event_type
    assert saved_memory.metadata.extra["duration"] == duration
    assert saved_memory.metadata.extra["sequence_number"] == 1
    assert saved_memory.importance == 0.8
    assert episode_id == saved_memory.id


@pytest.mark.asyncio
async def test_add_episode_with_auto_sequence() -> None:
    """测试自动生成序列号。"""
    adapter = MockStorageAdapter()
    episodic = EpisodicMemory(adapter)
    session_id = "sess-2"

    # 添加第一个 episode
    await episodic.add_episode(
        content="第一个交互",
        session_id=session_id,
        event_type="start"
    )

    # 添加第二个 episode
    await episodic.add_episode(
        content="第二个交互",
        session_id=session_id,
        event_type="continue"
    )

    # 验证序列号自动递增
    assert adapter.save_calls[0].metadata.extra["sequence_number"] == 1
    assert adapter.save_calls[1].metadata.extra["sequence_number"] == 2


@pytest.mark.asyncio
async def test_get_timeline_empty() -> None:
    """测试获取空时间线。"""
    adapter = MockStorageAdapter()
    episodic = EpisodicMemory(adapter)

    timeline = await episodic.get_timeline(session_id="empty-session")

    assert timeline == []
    assert len(adapter.list_calls) == 1
    assert adapter.list_calls[0] == "empty-session"


@pytest.mark.asyncio
async def test_get_timeline_ordered() -> None:
    """测试获取按时间排序的时间线。"""
    adapter = MockStorageAdapter()
    episodic = EpisodicMemory(adapter)
    session_id = "sess-3"

    # 创建不同时间的 episodes
    now = datetime.now()
    episode1 = _make_episode("ep-1", "第一个事件", session_id, sequence=1)
    episode1.created_at = now - timedelta(minutes=10)

    episode2 = _make_episode("ep-2", "第二个事件", session_id, sequence=2)
    episode2.created_at = now - timedelta(minutes=5)

    episode3 = _make_episode("ep-3", "第三个事件", session_id, sequence=3)
    episode3.created_at = now

    # 乱序添加到存储
    adapter.memories[episode2.id] = episode2
    adapter.memories[episode1.id] = episode1
    adapter.memories[episode3.id] = episode3

    timeline = await episodic.get_timeline(session_id=session_id)

    # 验证按时间排序
    assert len(timeline) == 3
    assert [ep.id for ep in timeline] == ["ep-1", "ep-2", "ep-3"]
    assert timeline[0].content == "第一个事件"
    assert timeline[1].content == "第二个事件"
    assert timeline[2].content == "第三个事件"


@pytest.mark.asyncio
async def test_get_timeline_with_user_filter() -> None:
    """测试按用户过滤时间线。"""
    adapter = MockStorageAdapter()
    episodic = EpisodicMemory(adapter)
    session_id = "sess-4"

    # 不同用户的 episodes
    episode_user1 = _make_episode("ep-u1", "用户1的事件", session_id)
    episode_user1.metadata.user_id = "user-1"

    episode_user2 = _make_episode("ep-u2", "用户2的事件", session_id)
    episode_user2.metadata.user_id = "user-2"

    adapter.memories[episode_user1.id] = episode_user1
    adapter.memories[episode_user2.id] = episode_user2

    timeline = await episodic.get_timeline(session_id=session_id, user_id="user-1")

    assert len(timeline) == 1
    assert timeline[0].id == "ep-u1"
    assert timeline[0].content == "用户1的事件"


@pytest.mark.asyncio
async def test_get_timeline_with_time_range() -> None:
    """测试时间范围查询。"""
    adapter = MockStorageAdapter()
    episodic = EpisodicMemory(adapter)
    session_id = "sess-5"

    now = datetime.now()
    start_time = now - timedelta(hours=1)
    end_time = now - timedelta(minutes=30)

    # 在范围外的 episode（太早）
    episode_early = _make_episode("ep-early", "太早的事件", session_id)
    episode_early.created_at = now - timedelta(hours=2)

    # 在范围内的 episode
    episode_in_range = _make_episode("ep-range", "范围内的事件", session_id)
    episode_in_range.created_at = now - timedelta(minutes=45)

    # 在范围外的 episode（太晚）
    episode_late = _make_episode("ep-late", "太晚的事件", session_id)
    episode_late.created_at = now - timedelta(minutes=15)

    adapter.memories[episode_early.id] = episode_early
    adapter.memories[episode_in_range.id] = episode_in_range
    adapter.memories[episode_late.id] = episode_late

    timeline = await episodic.get_timeline(
        session_id=session_id,
        start_time=start_time,
        end_time=end_time
    )

    assert len(timeline) == 1
    assert timeline[0].id == "ep-range"
    assert timeline[0].content == "范围内的事件"


@pytest.mark.asyncio
async def test_generate_session_summary() -> None:
    """测试生成会话摘要。"""
    adapter = MockStorageAdapter()
    episodic = EpisodicMemory(adapter)
    session_id = "sess-summary"

    # 创建一系列 episodes
    episodes_data = [
        ("用户询问如何使用 FastAPI", "question"),
        ("助手提供了详细的代码示例", "answer"),
        ("用户请求解释路由装饰器", "follow_up"),
        ("助手解释了 @app.get() 的用法", "explanation")
    ]

    for i, (content, event_type) in enumerate(episodes_data):
        episode = _make_episode(f"ep-{i}", content, session_id, event_type=event_type, sequence=i+1)
        adapter.memories[episode.id] = episode

    summary = await episodic.generate_session_summary(session_id)

    # 验证摘要包含关键信息
    assert "FastAPI" in summary
    assert "4个事件" in summary
    assert "question" in summary
    assert "answer" in summary


@pytest.mark.asyncio
async def test_generate_session_summary_empty() -> None:
    """测试空会话的摘要生成。"""
    adapter = MockStorageAdapter()
    episodic = EpisodicMemory(adapter)

    summary = await episodic.generate_session_summary("empty-session")

    assert summary == "该会话暂无记录的事件。"


@pytest.mark.asyncio
async def test_get_episode() -> None:
    """测试获取单个 episode。"""
    adapter = MockStorageAdapter()
    episodic = EpisodicMemory(adapter)

    episode = _make_episode("ep-single", "单个事件测试")
    adapter.memories[episode.id] = episode

    result = await episodic.get_episode("ep-single")

    assert result is not None
    assert result.id == "ep-single"
    assert result.content == "单个事件测试"
    assert len(adapter.get_calls) == 1
    assert adapter.get_calls[0] == "ep-single"


@pytest.mark.asyncio
async def test_get_episode_not_found() -> None:
    """测试获取不存在的 episode。"""
    adapter = MockStorageAdapter()
    episodic = EpisodicMemory(adapter)

    result = await episodic.get_episode("missing")

    assert result is None
    assert len(adapter.get_calls) == 1
    assert adapter.get_calls[0] == "missing"