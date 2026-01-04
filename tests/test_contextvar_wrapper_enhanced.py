"""
Tests for enhanced ContextVarWrapper.

Run with: uv run pytest tests/test_contextvar_wrapper_enhanced.py -v
"""

import asyncio
import pytest
from libs.contextVar_wrapper_enhanced import ContextVarWrapper, DictContextVar


class TestContextVarWrapperBasics:
    """Test basic get/set/clear operations."""

    def test_set_and_get(self):
        """Test basic set and get operations."""
        ctx = ContextVarWrapper.create("test")
        ctx.set("value")
        assert ctx.get() == "value"

    def test_get_with_default(self):
        """Test get with default value when not set."""
        ctx = ContextVarWrapper.create("test")
        assert ctx.get(default="fallback") == "fallback"

    def test_get_or_none(self):
        """Test get_or_none returns None when not set."""
        ctx = ContextVarWrapper.create("test")
        assert ctx.get_or_none() is None

        ctx.set("value")
        assert ctx.get_or_none() == "value"

    def test_get_or_raise(self):
        """Test get_or_raise throws LookupError when not set."""
        ctx = ContextVarWrapper.create("test")

        with pytest.raises(LookupError):
            ctx.get_or_raise()

        ctx.set("value")
        assert ctx.get_or_raise() == "value"

    def test_has_value(self):
        """Test has_value correctly detects presence."""
        ctx = ContextVarWrapper.create("test")
        assert ctx.has_value() is False

        ctx.set("value")
        assert ctx.has_value() is True

        ctx.clear()
        assert ctx.has_value() is True  # Clear sets to None, which is still a value

    def test_clear_type_safety(self):
        """Test clear works with non-dict types."""
        # Test with string
        ctx_str = ContextVarWrapper.create("string_ctx")
        ctx_str.set("string_value")
        ctx_str.clear()
        assert ctx_str.get_or_none() is None  # Not {}

        # Test with custom object
        class CustomObj:
            pass

        ctx_obj = ContextVarWrapper.create("obj_ctx")
        ctx_obj.set(CustomObj())
        ctx_obj.clear()
        assert ctx_obj.get_or_none() is None  # Not {}


class TestContextManager:
    """Test context manager functionality."""

    def test_temporary_set(self):
        """Test temporary_set restores previous value."""
        ctx = ContextVarWrapper.create("test")
        ctx.set("original")

        with ctx.temporary_set("temporary"):
            assert ctx.get() == "temporary"

        assert ctx.get() == "original"

    def test_temporary_set_without_initial_value(self):
        """Test temporary_set works when no initial value."""
        ctx = ContextVarWrapper.create("test")

        with ctx.temporary_set("temporary"):
            assert ctx.get() == "temporary"

        # Should restore to unset state
        assert ctx.has_value() is False

    def test_temporary_set_with_exception(self):
        """Test temporary_set restores value even on exception."""
        ctx = ContextVarWrapper.create("test")
        ctx.set("original")

        with pytest.raises(ValueError):
            with ctx.temporary_set("temporary"):
                assert ctx.get() == "temporary"
                raise ValueError("test error")

        # Should still restore
        assert ctx.get() == "original"

    def test_with_statement_auto_clear(self):
        """Test __enter__/__exit__ auto-clears value."""
        ctx = ContextVarWrapper.create("test")

        with ctx:
            ctx.set("value")
            assert ctx.get() == "value"

        # Should be cleared
        assert ctx.get_or_none() is None


class TestTokenReset:
    """Test token-based reset functionality."""

    def test_reset_with_token(self):
        """Test reset restores previous value using token."""
        ctx = ContextVarWrapper.create("test")
        ctx.set("first")

        token = ctx.set("second")
        assert ctx.get() == "second"

        ctx.reset(token)
        assert ctx.get() == "first"

    def test_multiple_token_reset(self):
        """Test multiple nested resets."""
        ctx = ContextVarWrapper.create("test")
        ctx.set("level0")

        token1 = ctx.set("level1")
        token2 = ctx.set("level2")
        token3 = ctx.set("level3")

        assert ctx.get() == "level3"
        ctx.reset(token3)
        assert ctx.get() == "level2"
        ctx.reset(token2)
        assert ctx.get() == "level1"
        ctx.reset(token1)
        assert ctx.get() == "level0"


class TestDictContextVar:
    """Test dict-specific wrapper."""

    def test_update(self):
        """Test dict update operation."""
        ctx = DictContextVar.create("test_dict")
        ctx.update(key1="value1", key2="value2")

        result = ctx.get()
        assert result == {"key1": "value1", "key2": "value2"}

    def test_get_item(self):
        """Test get single item from dict."""
        ctx = DictContextVar.create("test_dict")
        ctx.set({"user_id": "123", "role": "admin"})

        assert ctx.get_item("user_id") == "123"
        assert ctx.get_item("role") == "admin"
        assert ctx.get_item("missing", default="N/A") == "N/A"

    def test_set_item(self):
        """Test set single item in dict."""
        ctx = DictContextVar.create("test_dict")
        ctx.set({})

        ctx.set_item("user_id", "123")
        assert ctx.get_item("user_id") == "123"

        ctx.set_item("role", "admin")
        assert ctx.get() == {"user_id": "123", "role": "admin"}

    def test_remove_item(self):
        """Test remove item from dict."""
        ctx = DictContextVar.create("test_dict")
        ctx.set({"key1": "value1", "key2": "value2"})

        ctx.remove_item("key1")
        assert ctx.get() == {"key2": "value2"}

        # Removing non-existent key should not error
        ctx.remove_item("non_existent")
        assert ctx.get() == {"key2": "value2"}

    def test_clear_dict(self):
        """Test clear sets to empty dict, not None."""
        ctx = DictContextVar.create("test_dict")
        ctx.set({"key": "value"})

        ctx.clear()
        assert ctx.get() == {}  # Empty dict, not None


class TestAsyncIsolation:
    """Test context isolation in async tasks."""

    @pytest.mark.asyncio
    async def test_async_task_isolation(self):
        """Test that context is isolated between async tasks."""
        ctx = ContextVarWrapper.create("test_async")

        async def task1():
            ctx.set("task1_value")
            await asyncio.sleep(0.01)
            assert ctx.get() == "task1_value"

        async def task2():
            ctx.set("task2_value")
            await asyncio.sleep(0.01)
            assert ctx.get() == "task2_value"

        # Both tasks should have isolated contexts
        await asyncio.gather(task1(), task2())

    @pytest.mark.asyncio
    async def test_async_context_propagation(self):
        """Test that context is propagated to child tasks."""
        ctx = ContextVarWrapper.create("test_propagation")
        ctx.set("parent_value")

        async def child_task():
            # Should inherit parent's value
            assert ctx.get() == "parent_value"

        await child_task()


class TestDebugging:
    """Test debugging utilities."""

    def test_repr_with_value(self):
        """Test __repr__ when value is set."""
        ctx = ContextVarWrapper.create("test_ctx")
        ctx.set("test_value")

        repr_str = repr(ctx)
        assert "test_ctx" in repr_str
        assert "test_value" in repr_str

    def test_repr_without_value(self):
        """Test __repr__ when value is not set."""
        ctx = ContextVarWrapper.create("test_ctx")

        repr_str = repr(ctx)
        assert "test_ctx" in repr_str
        assert "<unset>" in repr_str

    def test_get_name(self):
        """Test get_name returns variable name."""
        ctx = ContextVarWrapper.create("my_context")
        assert ctx.get_name() == "my_context"


class TestRealWorldScenarios:
    """Test real-world usage patterns."""

    def test_middleware_pattern(self):
        """Test typical middleware usage pattern."""
        request_ctx = ContextVarWrapper.create("request_id")

        # Simulate middleware
        def middleware(request_id: str, handler):
            with request_ctx.temporary_set(request_id):
                return handler()

        # Simulate handler
        def handler():
            return f"Processing request: {request_ctx.get()}"

        result = middleware("req-123", handler)
        assert result == "Processing request: req-123"

        # Context should be cleaned up
        assert request_ctx.has_value() is False

    @pytest.mark.asyncio
    async def test_async_middleware_pattern(self):
        """Test async middleware pattern."""
        trace_ctx = ContextVarWrapper.create("trace_id")

        async def middleware(trace_id: str, handler):
            with trace_ctx.temporary_set(trace_id):
                return await handler()

        async def handler():
            await asyncio.sleep(0.01)
            return f"Trace: {trace_ctx.get()}"

        result = await middleware("trace-456", handler)
        assert result == "Trace: trace-456"

    def test_nested_context_managers(self):
        """Test nested context managers for different scopes."""
        user_ctx = ContextVarWrapper.create("user")
        session_ctx = ContextVarWrapper.create("session")

        with user_ctx.temporary_set("user123"):
            assert user_ctx.get() == "user123"

            with session_ctx.temporary_set("session456"):
                assert user_ctx.get() == "user123"
                assert session_ctx.get() == "session456"

            # Session should be restored
            assert user_ctx.get() == "user123"
            assert session_ctx.has_value() is False

        # Both should be restored
        assert user_ctx.has_value() is False
        assert session_ctx.has_value() is False


class TestBackwardCompatibility:
    """Test backward compatibility with old ContextVarWrappers."""

    def test_legacy_alias(self):
        """Test ContextVarWrappers alias works."""
        from libs.contextVar_wrapper_enhanced import ContextVarWrappers

        ctx = ContextVarWrappers.create("legacy_test")
        ctx.set("value")
        assert ctx.get() == "value"

    def test_old_api_still_works(self):
        """Test that old API patterns still work."""
        from contextvars import ContextVar
        from libs.contextVar_wrapper_enhanced import ContextVarWrapper

        # Old pattern
        ctx = ContextVarWrapper(ContextVar("old_style"))
        ctx.set("value")

        # get() with no args should work with default=None
        result = ctx.get()
        assert result == "value"

        # clear() should work
        ctx.clear()
        assert ctx.get() is None
