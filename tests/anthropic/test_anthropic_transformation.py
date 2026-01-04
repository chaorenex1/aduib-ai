"""
Unit tests for AnthropicTransformation class and related functionality.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import httpx

from runtime.transformation.anthropic.transformation import AnthropicTransformation
from runtime.transformation.anthropic.error import (
    AnthropicErrorMapper,
    AnthropicRetryStrategy,
    AnthropicAPIError,
    AnthropicAuthenticationError,
    AnthropicRateLimitError,
    AnthropicModelNotFoundError,
    AnthropicInvalidRequestError,
    AnthropicServerError
)
from runtime.entities.llm_entities import ChatCompletionRequest
from runtime.entities import ChatCompletionResponse


class TestAnthropicTransformation(unittest.TestCase):
    """Test cases for AnthropicTransformation class."""

    def setUp(self):
        """Set up test fixtures."""
        self.valid_credentials = {
            "credentials": {
                "api_key": "test-api-key-123",
                "api_base": "https://api.anthropic.com/v1"
            },
            "sdk_type": "anthropic"
        }
        self.model_params = {
            "temperature": 0.7,
            "max_tokens": 1000
        }

    def test_setup_environment_valid_credentials(self):
        """Test environment setup with valid credentials."""
        result = AnthropicTransformation.setup_environment(self.valid_credentials)

        self.assertEqual(result["api_key"], "test-api-key-123")
        self.assertEqual(result["api_base"], "https://api.anthropic.com/v1")
        self.assertEqual(result["headers"]["x-api-key"], "test-api-key-123")
        self.assertEqual(result["headers"]["Content-Type"], "application/json")
        self.assertEqual(result["headers"]["anthropic-version"], "2023-06-01")
        self.assertEqual(result["sdk_type"], "anthropic")

    def test_setup_environment_missing_api_key(self):
        """Test environment setup with missing API key."""
        invalid_credentials = {
            "credentials": {
                "api_base": "https://api.anthropic.com/v1"
            },
            "sdk_type": "anthropic"
        }

        with self.assertRaises(ValueError) as context:
            AnthropicTransformation.setup_environment(invalid_credentials)

        self.assertIn("api_key is required in credentials for Anthropic API", str(context.exception))

    def test_setup_environment_empty_api_key(self):
        """Test environment setup with empty API key."""
        invalid_credentials = {
            "credentials": {
                "api_key": "",
                "api_base": "https://api.anthropic.com/v1"
            },
            "sdk_type": "anthropic"
        }

        with self.assertRaises(ValueError) as context:
            AnthropicTransformation.setup_environment(invalid_credentials)

        self.assertIn("api_key is required in credentials for Anthropic API", str(context.exception))

    def test_setup_environment_default_api_base(self):
        """Test environment setup with default API base."""
        credentials_without_base = {
            "credentials": {
                "api_key": "test-api-key-123"
            },
            "sdk_type": "anthropic"
        }

        result = AnthropicTransformation.setup_environment(credentials_without_base)

        self.assertEqual(result["api_base"], AnthropicTransformation.DEFAULT_API_BASE)

    def test_transform_to_anthropic_format_basic(self):
        """Test transformation of basic OpenAI-like request to Anthropic format."""
        request = ChatCompletionRequest(
            model="claude-3-5-sonnet-20241022",
            messages=[
                {"role": "user", "content": "Hello, how are you?"}
            ],
            max_tokens=1000,
            temperature=0.7
        )

        result = AnthropicTransformation._transform_to_anthropic_format(request, self.model_params)

        self.assertEqual(result["model"], "claude-3-5-sonnet-20241022")
        self.assertEqual(result["max_tokens"], 1000)
        self.assertEqual(result["temperature"], 0.7)
        self.assertEqual(len(result["messages"]), 1)
        self.assertEqual(result["messages"][0]["role"], "user")
        self.assertEqual(result["messages"][0]["content"], "Hello, how are you?")

    def test_transform_to_anthropic_format_with_system_prompt(self):
        """Test transformation with system prompt."""
        request = ChatCompletionRequest(
            model="claude-3-5-sonnet-20241022",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello, how are you?"}
            ],
            max_tokens=1000
        )

        result = AnthropicTransformation._transform_to_anthropic_format(request, self.model_params)

        self.assertEqual(result["system"], "You are a helpful assistant.")
        self.assertEqual(len(result["messages"]), 1)
        self.assertEqual(result["messages"][0]["role"], "user")

    def test_transform_to_anthropic_format_with_streaming(self):
        """Test transformation with streaming enabled."""
        request = ChatCompletionRequest(
            model="claude-3-5-sonnet-20241022",
            messages=[
                {"role": "user", "content": "Hello, how are you?"}
            ],
            max_tokens=1000,
            stream=True
        )

        result = AnthropicTransformation._transform_to_anthropic_format(request, self.model_params)

        self.assertTrue(result["stream"])

    def test_get_supported_models(self):
        """Test getting list of supported models."""
        models = AnthropicTransformation.get_supported_models()

        self.assertIsInstance(models, list)
        self.assertGreater(len(models), 0)
        self.assertIn("claude-3-5-sonnet-20241022", models)
        self.assertIn("claude-3-5-haiku-20241022", models)

    def test_validate_model_supported(self):
        """Test model validation for supported models."""
        self.assertTrue(AnthropicTransformation.validate_model("claude-3-5-sonnet-20241022"))
        self.assertTrue(AnthropicTransformation.validate_model("claude-3-5-haiku-20241022"))

    def test_validate_model_unsupported(self):
        """Test model validation for unsupported models."""
        self.assertFalse(AnthropicTransformation.validate_model("gpt-4"))
        self.assertFalse(AnthropicTransformation.validate_model("unsupported-model"))

    @patch('runtime.clients.handler.llm_http_handler.LLMHttpHandler')
    def test_make_request_with_retry_success(self, mock_handler_class):
        """Test successful request without retries."""
        mock_handler = Mock()
        mock_handler.completion_request.return_value = ChatCompletionResponse(
            id="test-id",
            choices=[],
            created=1234567890
        )
        mock_handler_class.return_value = mock_handler

        anthropic_request = {
            "model": "claude-3-5-sonnet-20241022",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1000
        }

        result = AnthropicTransformation._make_request_with_retry(
            mock_handler, anthropic_request, "claude-3-5-sonnet-20241022"
        )

        self.assertIsInstance(result, ChatCompletionResponse)
        mock_handler.completion_request.assert_called_once_with(anthropic_request)

    @patch('runtime.clients.handler.llm_http_handler.LLMHttpHandler')
    @patch('asyncio.sleep')
    def test_make_request_with_retry_rate_limit(self, mock_sleep, mock_handler_class):
        """Test request with rate limit error that succeeds after retry."""
        mock_handler = Mock()
        # First call raises rate limit, second succeeds
        mock_handler.completion_request.side_effect = [
            httpx.HTTPStatusError(
                "Rate limit exceeded",
                request=Mock(),
                response=Mock(status_code=429)
            ),
            ChatCompletionResponse(
                id="test-id",
                choices=[],
                created=1234567890
            )
        ]
        mock_handler_class.return_value = mock_handler

        anthropic_request = {
            "model": "claude-3-5-sonnet-20241022",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1000
        }

        result = AnthropicTransformation._make_request_with_retry(
            mock_handler, anthropic_request, "claude-3-5-sonnet-20241022", max_retries=3
        )

        self.assertIsInstance(result, ChatCompletionResponse)
        self.assertEqual(mock_handler.completion_request.call_count, 2)
        mock_sleep.assert_called_once()

    @patch('runtime.clients.handler.llm_http_handler.LLMHttpHandler')
    def test_make_request_with_retry_client_error(self, mock_handler_class):
        """Test request with client error that should not be retried."""
        mock_handler = Mock()
        mock_handler.completion_request.side_effect = httpx.HTTPStatusError(
            "Invalid request",
            request=Mock(),
            response=Mock(status_code=400)
        )
        mock_handler_class.return_value = mock_handler

        anthropic_request = {
            "model": "claude-3-5-sonnet-20241022",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 1000
        }

        with self.assertRaises(AnthropicInvalidRequestError):
            AnthropicTransformation._make_request_with_retry(
                mock_handler, anthropic_request, "claude-3-5-sonnet-20241022"
            )

        # Should only be called once (no retry for client errors)
        mock_handler.completion_request.assert_called_once_with(anthropic_request)

    def test_transform_embeddings_not_implemented(self):
        """Test that embeddings transformation raises NotImplementedError."""
        with self.assertRaises(NotImplementedError) as context:
            AnthropicTransformation.transform_embeddings(
                Mock(), self.valid_credentials
            )

        self.assertIn("Anthropic API does not support embeddings endpoint", str(context.exception))

    def test_transform_rerank_not_implemented(self):
        """Test that rerank transformation raises NotImplementedError."""
        with self.assertRaises(NotImplementedError) as context:
            AnthropicTransformation.transform_rerank(
                Mock(), self.valid_credentials
            )

        self.assertIn("Anthropic API does not support rerank endpoint", str(context.exception))


class TestAnthropicErrorMapper(unittest.TestCase):
    """Test cases for AnthropicErrorMapper."""

    def test_map_error_by_status_code(self):
        """Test error mapping by HTTP status code."""
        # Test authentication error
        error = AnthropicErrorMapper.map_error(401)
        self.assertIsInstance(error, AnthropicAuthenticationError)
        self.assertEqual(error.status_code, 401)

        # Test rate limit error
        error = AnthropicErrorMapper.map_error(429)
        self.assertIsInstance(error, AnthropicRateLimitError)
        self.assertEqual(error.status_code, 429)

        # Test model not found error
        error = AnthropicErrorMapper.map_error(404)
        self.assertIsInstance(error, AnthropicModelNotFoundError)
        self.assertEqual(error.status_code, 404)

        # Test invalid request error
        error = AnthropicErrorMapper.map_error(400)
        self.assertIsInstance(error, AnthropicInvalidRequestError)
        self.assertEqual(error.status_code, 400)

        # Test server error
        error = AnthropicErrorMapper.map_error(500)
        self.assertIsInstance(error, AnthropicServerError)
        self.assertEqual(error.status_code, 500)

    def test_map_error_by_error_type(self):
        """Test error mapping by Anthropic error type."""
        error_response = {
            "type": "authentication_error",
            "message": "Invalid API key"
        }

        error = AnthropicErrorMapper.map_error(401, error_response)
        self.assertIsInstance(error, AnthropicAuthenticationError)
        self.assertEqual(error.error_type, "authentication_error")
        self.assertEqual(error.message, "Invalid API key")

    def test_map_error_default(self):
        """Test default error mapping."""
        error = AnthropicErrorMapper.map_error(999)  # Unknown status code
        self.assertIsInstance(error, AnthropicAPIError)
        self.assertEqual(error.status_code, 999)

    def test_should_retry(self):
        """Test retry decision logic."""
        # Should retry rate limit errors
        rate_limit_error = AnthropicRateLimitError("Rate limit exceeded", 429)
        self.assertTrue(AnthropicErrorMapper.should_retry(rate_limit_error))

        # Should retry server errors
        server_error = AnthropicServerError("Server error", 500)
        self.assertTrue(AnthropicErrorMapper.should_retry(server_error))

        # Should not retry client errors
        auth_error = AnthropicAuthenticationError("Invalid API key", 401)
        self.assertFalse(AnthropicErrorMapper.should_retry(auth_error))

        invalid_request_error = AnthropicInvalidRequestError("Invalid request", 400)
        self.assertFalse(AnthropicErrorMapper.should_retry(invalid_request_error))


class TestAnthropicRetryStrategy(unittest.TestCase):
    """Test cases for AnthropicRetryStrategy."""

    def test_get_delay_exponential_backoff(self):
        """Test exponential backoff delay calculation."""
        strategy = AnthropicRetryStrategy(base_delay=1.0)

        # Test exponential growth
        self.assertGreater(strategy.get_delay(1), strategy.get_delay(0))
        self.assertGreater(strategy.get_delay(2), strategy.get_delay(1))

        # Test within bounds
        delay = strategy.get_delay(0)
        self.assertGreaterEqual(delay, 0.5)  # With jitter, minimum is 0.5
        self.assertLessEqual(delay, 1.5)     # With jitter, maximum is 1.5

    def test_get_delay_without_jitter(self):
        """Test delay calculation without jitter."""
        strategy = AnthropicRetryStrategy(base_delay=1.0, jitter=False)

        # Without jitter, delay should be exact
        self.assertEqual(strategy.get_delay(0), 1.0)
        self.assertEqual(strategy.get_delay(1), 2.0)
        self.assertEqual(strategy.get_delay(2), 4.0)

    def test_get_delay_max_delay(self):
        """Test that delay is capped at maximum."""
        strategy = AnthropicRetryStrategy(base_delay=1.0, max_delay=2.0)

        # Delay should not exceed max_delay
        delay = strategy.get_delay(10)  # Large attempt number
        self.assertLessEqual(delay, 2.0)

    def test_should_retry(self):
        """Test retry decision logic."""
        strategy = AnthropicRetryStrategy(max_retries=3)

        # Should retry within max retries
        rate_limit_error = AnthropicRateLimitError("Rate limit exceeded", 429)
        self.assertTrue(strategy.should_retry(0, rate_limit_error))
        self.assertTrue(strategy.should_retry(2, rate_limit_error))

        # Should not retry beyond max retries
        self.assertFalse(strategy.should_retry(3, rate_limit_error))

        # Should not retry client errors
        auth_error = AnthropicAuthenticationError("Invalid API key", 401)
        self.assertFalse(strategy.should_retry(0, auth_error))


if __name__ == "__main__":
    unittest.main()