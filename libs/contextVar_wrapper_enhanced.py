"""
Enhanced ContextVar wrapper with improved safety, type checking, and convenience methods.

Key improvements:
- Safe get() with default values
- Type-safe clear() that doesn't assume dict type
- Context manager support for automatic cleanup
- Temporary value setting with automatic restoration
- Better debugging and repr
"""

from contextvars import ContextVar, Token
from typing import Generic, TypeVar, Optional, Generator, Any
from contextlib import contextmanager

T = TypeVar("T")


class ContextVarWrapper(Generic[T]):
    """
    Generic request context storage utility, similar to ThreadLocal.
    Based on contextvars, supports async FastAPI.

    Features:
    - Safe access with default values
    - Type-safe cleanup
    - Context manager support
    - Temporary value setting
    - Debugging utilities

    Example:
        # Create with factory method
        user_ctx = ContextVarWrapper.create("user_id", default=None)

        # Basic usage
        user_ctx.set("user123")
        user_id = user_ctx.get()  # "user123"

        # Safe access
        user_id = user_ctx.get_or_none()  # None if not set
        user_id = user_ctx.get(default="anonymous")  # "anonymous" if not set

        # Temporary value
        with user_ctx.temporary_set("temp_user"):
            # user_ctx.get() returns "temp_user"
            process_request()
        # Automatically restored to previous value

        # Auto cleanup
        with user_ctx:
            user_ctx.set("user456")
            process_request()
        # Automatically cleared on exit
    """

    def __init__(self, context_var: ContextVar[T]):
        """
        Initialize wrapper with a ContextVar instance.

        Args:
            context_var: The ContextVar to wrap
        """
        self._storage = context_var

    def set(self, value: T) -> Token[T]:
        """
        Set the context value.

        Args:
            value: The value to set

        Returns:
            Token that can be used to reset to the previous value

        Example:
            token = ctx.set("value")
            # ... do work ...
            ctx.reset(token)  # Restore previous value
        """
        return self._storage.set(value)

    def get(self, default: Optional[T] = None) -> Optional[T]:
        """
        Get the context value with optional default.

        Args:
            default: Value to return if context is not set

        Returns:
            The context value or default if not set

        Example:
            value = ctx.get(default="fallback")
        """
        try:
            return self._storage.get()
        except LookupError:
            return default

    def get_or_none(self) -> Optional[T]:
        """
        Get the context value or None.

        Returns:
            The context value or None if not set

        Example:
            value = ctx.get_or_none()
            if value is not None:
                process(value)
        """
        return self.get(default=None)

    def get_or_raise(self) -> T:
        """
        Get the context value or raise LookupError.

        Returns:
            The context value

        Raises:
            LookupError: If context value is not set

        Example:
            try:
                value = ctx.get_or_raise()
            except LookupError:
                handle_missing_context()
        """
        return self._storage.get()

    def has_value(self) -> bool:
        """
        Check if a value is set in the context.

        Returns:
            True if a value is set, False otherwise

        Example:
            if ctx.has_value():
                value = ctx.get()
        """
        try:
            self._storage.get()
            return True
        except LookupError:
            return False

    def clear(self) -> None:
        """
        Clear the context value (set to None).

        This is type-safe and doesn't assume the type is a dict.

        Example:
            ctx.set("value")
            ctx.clear()
            assert ctx.get_or_none() is None
        """
        self._storage.set(None)  # type: ignore

    def reset(self, token: Token[T]) -> None:
        """
        Reset to a previous value using a token.

        Args:
            token: Token returned from set()

        Example:
            token = ctx.set("new_value")
            # ... do work ...
            ctx.reset(token)  # Restore previous value
        """
        self._storage.reset(token)

    @contextmanager
    def temporary_set(self, value: T) -> Generator[None, None, None]:
        """
        Temporarily set a value, automatically restoring the previous value.

        Args:
            value: The temporary value to set

        Yields:
            None

        Example:
            ctx.set("original")
            with ctx.temporary_set("temporary"):
                assert ctx.get() == "temporary"
            assert ctx.get() == "original"
        """
        token = self.set(value)
        try:
            yield
        finally:
            self.reset(token)

    def __enter__(self) -> "ContextVarWrapper[T]":
        """
        Enter context manager (for manual set/clear pattern).

        Returns:
            Self

        Example:
            with ctx:
                ctx.set("value")
                # ... do work ...
            # Automatically cleared
        """
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        Exit context manager, clearing the value.

        Args:
            exc_type: Exception type (if any)
            exc_val: Exception value (if any)
            exc_tb: Exception traceback (if any)
        """
        self.clear()

    def __repr__(self) -> str:
        """
        Return a debugging-friendly string representation.

        Returns:
            String representation showing name and current value

        Example:
            >>> repr(ctx)
            '<ContextVarWrapper(user_id="user123")>'
        """
        name = self.get_name()
        try:
            value = self._storage.get()
            return f"<ContextVarWrapper({name}={value!r})>"
        except LookupError:
            return f"<ContextVarWrapper({name}=<unset>)>"

    def get_name(self) -> str:
        """
        Get the name of the context variable.

        Returns:
            The variable name or "<unnamed>" if not set

        Example:
            name = ctx.get_name()
        """
        return getattr(self._storage, "name", "<unnamed>")

    @classmethod
    def create(cls, name: str) -> "ContextVarWrapper[T]":
        """
        Factory method to create a named context variable.

        Args:
            name: Name for the context variable (useful for debugging)

        Returns:
            A new ContextVarWrapper instance

        Example:
            user_ctx = ContextVarWrapper.create("user_id")
        """
        context_var = ContextVar(name)
        return cls(context_var)


class DictContextVar(ContextVarWrapper[dict]):
    """
    Specialized wrapper for dict-type context variables.

    Provides dict-specific operations like update, get_item, set_item.

    Example:
        ctx = DictContextVar.create("request_data")
        ctx.update(user_id="123", session_id="abc")
        user_id = ctx.get_item("user_id")
        ctx.set_item("timestamp", time.time())
    """

    def update(self, **kwargs: Any) -> None:
        """
        Update the dict with key-value pairs.

        Args:
            **kwargs: Key-value pairs to update

        Example:
            ctx.update(user_id="123", role="admin")
        """
        current = self.get_or_none() or {}
        current.update(kwargs)
        self.set(current)

    def get_item(self, key: str, default: Any = None) -> Any:
        """
        Get a single item from the dict.

        Args:
            key: The key to retrieve
            default: Default value if key doesn't exist

        Returns:
            The value or default

        Example:
            user_id = ctx.get_item("user_id", default="anonymous")
        """
        current = self.get_or_none() or {}
        return current.get(key, default)

    def set_item(self, key: str, value: Any) -> None:
        """
        Set a single item in the dict.

        Args:
            key: The key to set
            value: The value to set

        Example:
            ctx.set_item("user_id", "123")
        """
        current = self.get_or_none() or {}
        current[key] = value
        self.set(current)

    def remove_item(self, key: str) -> None:
        """
        Remove a single item from the dict.

        Args:
            key: The key to remove

        Example:
            ctx.remove_item("temp_data")
        """
        current = self.get_or_none() or {}
        current.pop(key, None)
        self.set(current)

    def clear(self) -> None:
        """
        Clear the dict (set to empty dict).

        This overrides the parent clear() to set {} instead of None,
        which is more appropriate for dict types.

        Example:
            ctx.clear()
            assert ctx.get() == {}
        """
        self._storage.set({})


# Legacy alias for backward compatibility
ContextVarWrappers = ContextVarWrapper
