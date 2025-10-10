"""
Error handling module for Anthropic Claude API integration.
Provides Claude-specific error classes and mapping for API error responses.
"""

import logging
from typing import Dict, Any, Optional

from service.error.base import BaseServiceError

logger = logging.getLogger(__name__)


class AnthropicAPIError(BaseServiceError):
    """Base class for Anthropic API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, error_type: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type
        self.message = message


class AnthropicAuthenticationError(AnthropicAPIError):
    """Authentication error for Anthropic API."""
    pass


class AnthropicRateLimitError(AnthropicAPIError):
    """Rate limit error for Anthropic API."""
    pass


class AnthropicModelNotFoundError(AnthropicAPIError):
    """Model not found error for Anthropic API."""
    pass


class AnthropicInvalidRequestError(AnthropicAPIError):
    """Invalid request error for Anthropic API."""
    pass


class AnthropicServerError(AnthropicAPIError):
    """Server error for Anthropic API."""
    pass


class AnthropicTransformationError(BaseServiceError):
    """Error during transformation of requests/responses."""
    pass


class AnthropicErrorMapper:
    """
    Maps Anthropic API error responses to appropriate error classes.
    """

    # Mapping of HTTP status codes to error classes
    STATUS_CODE_MAPPING = {
        400: AnthropicInvalidRequestError,
        401: AnthropicAuthenticationError,
        403: AnthropicAuthenticationError,
        404: AnthropicModelNotFoundError,
        429: AnthropicRateLimitError,
        500: AnthropicServerError,
        502: AnthropicServerError,
        503: AnthropicServerError,
        504: AnthropicServerError,
    }

    # Mapping of Anthropic error types to error classes
    ERROR_TYPE_MAPPING = {
        "authentication_error": AnthropicAuthenticationError,
        "rate_limit_error": AnthropicRateLimitError,
        "model_not_found": AnthropicModelNotFoundError,
        "invalid_request_error": AnthropicInvalidRequestError,
        "api_error": AnthropicServerError,
        "overloaded_error": AnthropicServerError,
    }

    @classmethod
    def map_error(
        cls,
        status_code: int,
        error_response: Optional[Dict[str, Any]] = None,
        default_message: str = "Anthropic API request failed"
    ) -> AnthropicAPIError:
        """
        Map HTTP status code and error response to appropriate error class.

        Args:
            status_code: HTTP status code from response
            error_response: Error response body from Anthropic API
            default_message: Default error message

        Returns:
            Appropriate AnthropicAPIError subclass
        """
        # Extract error details from response
        error_type = None
        error_message = default_message

        if error_response:
            error_type = error_response.get("type")
            error_message = error_response.get("message", default_message)

        # Try to map by error type first
        if error_type and error_type in cls.ERROR_TYPE_MAPPING:
            error_class = cls.ERROR_TYPE_MAPPING[error_type]
            return error_class(
                message=error_message,
                status_code=status_code,
                error_type=error_type
            )

        # Fall back to status code mapping
        if status_code in cls.STATUS_CODE_MAPPING:
            error_class = cls.STATUS_CODE_MAPPING[status_code]
            return error_class(
                message=error_message,
                status_code=status_code,
                error_type=error_type
            )

        # Default to generic API error
        return AnthropicAPIError(
            message=error_message,
            status_code=status_code,
            error_type=error_type
        )

    @classmethod
    def should_retry(cls, error: AnthropicAPIError) -> bool:
        """
        Determine if an error should be retried.

        Args:
            error: The error to check

        Returns:
            True if the error should be retried, False otherwise
        """
        # Retry on rate limits and server errors
        if isinstance(error, (AnthropicRateLimitError, AnthropicServerError)):
            return True

        # Don't retry on client errors (except rate limits)
        if error.status_code and 400 <= error.status_code < 500:
            return False

        # Default to retry for other errors
        return True


class AnthropicRetryStrategy:
    """
    Retry strategy for Anthropic API requests.
    Implements exponential backoff with jitter.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter: bool = True
    ):
        """
        Initialize retry strategy.

        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds for exponential backoff
            max_delay: Maximum delay in seconds
            jitter: Whether to add jitter to avoid thundering herd
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """
        Calculate delay for a retry attempt.

        Args:
            attempt: Current retry attempt (0-indexed)

        Returns:
            Delay in seconds
        """
        # Exponential backoff
        delay = self.base_delay * (2 ** attempt)

        # Add jitter if enabled
        if self.jitter:
            import random
            delay = delay * (0.5 + random.random() * 0.5)

        # Cap at maximum delay
        return min(delay, self.max_delay)

    def should_retry(self, attempt: int, error: AnthropicAPIError) -> bool:
        """
        Determine if a retry should be attempted.

        Args:
            attempt: Current retry attempt (0-indexed)
            error: The error that occurred

        Returns:
            True if retry should be attempted, False otherwise
        """
        # Check if we've exceeded max retries
        if attempt >= self.max_retries:
            return False

        # Check if this error type should be retried
        return AnthropicErrorMapper.should_retry(error)