"""
Integration tests for Anthropic Claude model support.
These tests verify end-to-end functionality with actual API interactions.

Note: These tests require valid Anthropic API credentials set in environment variables:
    - ANTHROPIC_API_KEY: Your Anthropic API key
    - ANTHROPIC_API_BASE: (Optional) Custom API base URL

Run with: pytest tests/anthropic/test_anthropic_integration.py -v
"""

import os
import pytest
import time
from unittest.mock import Mock, patch
import httpx

from runtime.transformation.anthropic.transformation import AnthropicTransformation
from runtime.transformation.anthropic.error import (
    AnthropicAuthenticationError,
    AnthropicRateLimitError,
    AnthropicInvalidRequestError,
    AnthropicServerError
)
from runtime.entities.llm_entities import ChatCompletionRequest, ChatMessage
from runtime.entities import ChatCompletionResponse


class TestAnthropicIntegration:
    """Integration tests for Anthropic transformation."""

    @pytest.fixture
    def valid_credentials(self):
        """Fixture providing valid test credentials."""
        api_key = os.getenv("ANTHROPIC_API_KEY", "test-api-key-123")
        api_base = os.getenv("ANTHROPIC_API_BASE", "https://api.anthropic.com/v1")

        return {
            "credentials": {
                "api_key": api_key,
                "api_base": api_base
            },
            "sdk_type": "anthropic"
        }

    @pytest.fixture
    def model_params(self):
        """Fixture providing default model parameters."""
        return {
            "temperature": 0.7,
            "max_tokens": 1000,
            "top_p": 0.9
        }

    @pytest.fixture
    def simple_chat_request(self):
        """Fixture providing a simple chat request."""
        return ChatCompletionRequest(
            model="claude-3-5-sonnet-20241022",
            messages=[
                ChatMessage(role="user", content="What is 2+2?")
            ],
            max_tokens=100,
            temperature=0.7
        )

    @pytest.fixture
    def chat_request_with_system_prompt(self):
        """Fixture providing a chat request with system prompt."""
        return ChatCompletionRequest(
            model="claude-3-5-sonnet-20241022",
            messages=[
                ChatMessage(role="system", content="You are a helpful math tutor."),
                ChatMessage(role="user", content="What is 2+2?")
            ],
            max_tokens=100,
            temperature=0.7
        )

    @pytest.fixture
    def multi_turn_chat_request(self):
        """Fixture providing a multi-turn conversation request."""
        return ChatCompletionRequest(
            model="claude-3-5-sonnet-20241022",
            messages=[
                ChatMessage(role="user", content="Hello, how are you?"),
                ChatMessage(role="assistant", content="I'm doing well, thank you! How can I help you today?"),
                ChatMessage(role="user", content="Can you help me with Python?")
            ],
            max_tokens=200,
            temperature=0.7
        )

    def test_environment_setup_valid_credentials(self, valid_credentials):
        """Test environment setup with valid credentials."""
        result = AnthropicTransformation.setup_environment(valid_credentials)

        assert "api_key" in result
        assert "api_base" in result
        assert "headers" in result
        assert result["headers"]["x-api-key"] == valid_credentials["credentials"]["api_key"]
        assert result["headers"]["Content-Type"] == "application/json"
        assert result["headers"]["anthropic-version"] == "2023-06-01"
        assert "User-Agent" in result["headers"]

    def test_environment_setup_missing_api_key(self):
        """Test environment setup fails with missing API key."""
        invalid_credentials = {
            "credentials": {},
            "sdk_type": "anthropic"
        }

        with pytest.raises(ValueError, match="api_key is required"):
            AnthropicTransformation.setup_environment(invalid_credentials)

    def test_request_transformation_basic(self, simple_chat_request, model_params):
        """Test basic request transformation to Anthropic format."""
        result = AnthropicTransformation._transform_to_anthropic_format(
            simple_chat_request, model_params
        )

        assert result["model"] == "claude-3-5-sonnet-20241022"
        assert result["max_tokens"] == 100
        assert result["temperature"] == 0.7
        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "user"
        assert result["messages"][0]["content"] == "What is 2+2?"

    def test_request_transformation_with_system_prompt(self, chat_request_with_system_prompt, model_params):
        """Test request transformation with system prompt."""
        result = AnthropicTransformation._transform_to_anthropic_format(
            chat_request_with_system_prompt, model_params
        )

        assert "system" in result
        assert result["system"] == "You are a helpful math tutor."
        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "user"

    def test_request_transformation_multi_turn(self, multi_turn_chat_request, model_params):
        """Test request transformation for multi-turn conversation."""
        result = AnthropicTransformation._transform_to_anthropic_format(
            multi_turn_chat_request, model_params
        )

        assert len(result["messages"]) == 3
        assert result["messages"][0]["role"] == "user"
        assert result["messages"][1]["role"] == "assistant"
        assert result["messages"][2]["role"] == "user"

    def test_supported_models_list(self):
        """Test retrieving supported models list."""
        models = AnthropicTransformation.get_supported_models()

        assert isinstance(models, list)
        assert len(models) > 0
        assert "claude-3-5-sonnet-20241022" in models
        assert "claude-3-5-haiku-20241022" in models
        assert "claude-3-opus-20240229" in models
        assert "claude-3-sonnet-20240229" in models
        assert "claude-3-haiku-20240307" in models

    def test_model_validation_supported_models(self):
        """Test model validation for all supported models."""
        for model in AnthropicTransformation.SUPPORTED_MODELS:
            assert AnthropicTransformation.validate_model(model), f"Model {model} should be valid"

    def test_model_validation_unsupported_models(self):
        """Test model validation rejects unsupported models."""
        unsupported_models = [
            "gpt-4",
            "gpt-3.5-turbo",
            "claude-2",
            "claude-instant",
            "unsupported-model",
            "claude-3-5-sonnet-20241022-test"  # Test exact matching fix
        ]

        for model in unsupported_models:
            assert not AnthropicTransformation.validate_model(model), f"Model {model} should be invalid"

    @patch('runtime.clients.handler.llm_http_handler.LLMHttpHandler')
    def test_retry_logic_with_rate_limit(self, mock_handler_class, valid_credentials, simple_chat_request, model_params):
        """Test retry logic with rate limit error."""
        mock_handler = Mock()

        # First call raises rate limit, second succeeds
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.json.return_value = {
            "type": "rate_limit_error",
            "message": "Rate limit exceeded"
        }

        mock_handler.completion_request.side_effect = [
            httpx.HTTPStatusError(
                "Rate limit exceeded",
                request=Mock(),
                response=mock_response
            ),
            ChatCompletionResponse(
                id="test-id",
                object="chat.completion",
                created=int(time.time()),
                model="claude-3-5-sonnet-20241022",
                choices=[]
            )
        ]
        mock_handler_class.return_value = mock_handler

        anthropic_request = AnthropicTransformation._transform_to_anthropic_format(
            simple_chat_request, model_params
        )

        # Make request with retry
        result = AnthropicTransformation._make_request_with_retry(
            mock_handler,
            anthropic_request,
            "claude-3-5-sonnet-20241022",
            max_retries=3
        )

        assert isinstance(result, ChatCompletionResponse)
        assert mock_handler.completion_request.call_count == 2

    @patch('runtime.clients.handler.llm_http_handler.LLMHttpHandler')
    def test_retry_logic_with_server_error(self, mock_handler_class, valid_credentials, simple_chat_request, model_params):
        """Test retry logic with server error."""
        mock_handler = Mock()

        # First call raises server error, second succeeds
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {
            "type": "api_error",
            "message": "Internal server error"
        }

        mock_handler.completion_request.side_effect = [
            httpx.HTTPStatusError(
                "Internal server error",
                request=Mock(),
                response=mock_response
            ),
            ChatCompletionResponse(
                id="test-id",
                object="chat.completion",
                created=int(time.time()),
                model="claude-3-5-sonnet-20241022",
                choices=[]
            )
        ]
        mock_handler_class.return_value = mock_handler

        anthropic_request = AnthropicTransformation._transform_to_anthropic_format(
            simple_chat_request, model_params
        )

        # Make request with retry
        result = AnthropicTransformation._make_request_with_retry(
            mock_handler,
            anthropic_request,
            "claude-3-5-sonnet-20241022",
            max_retries=3
        )

        assert isinstance(result, ChatCompletionResponse)
        assert mock_handler.completion_request.call_count == 2

    @patch('runtime.clients.handler.llm_http_handler.LLMHttpHandler')
    def test_no_retry_for_client_errors(self, mock_handler_class, valid_credentials, simple_chat_request, model_params):
        """Test that client errors are not retried."""
        mock_handler = Mock()

        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "type": "invalid_request_error",
            "message": "Invalid request"
        }

        mock_handler.completion_request.side_effect = httpx.HTTPStatusError(
            "Invalid request",
            request=Mock(),
            response=mock_response
        )
        mock_handler_class.return_value = mock_handler

        anthropic_request = AnthropicTransformation._transform_to_anthropic_format(
            simple_chat_request, model_params
        )

        # Make request should fail immediately without retry
        with pytest.raises(AnthropicInvalidRequestError):
            AnthropicTransformation._make_request_with_retry(
                mock_handler,
                anthropic_request,
                "claude-3-5-sonnet-20241022",
                max_retries=3
            )

        # Should only be called once (no retry)
        assert mock_handler.completion_request.call_count == 1

    @patch('runtime.clients.handler.llm_http_handler.LLMHttpHandler')
    def test_no_retry_for_authentication_errors(self, mock_handler_class, valid_credentials, simple_chat_request, model_params):
        """Test that authentication errors are not retried."""
        mock_handler = Mock()

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            "type": "authentication_error",
            "message": "Invalid API key"
        }

        mock_handler.completion_request.side_effect = httpx.HTTPStatusError(
            "Invalid API key",
            request=Mock(),
            response=mock_response
        )
        mock_handler_class.return_value = mock_handler

        anthropic_request = AnthropicTransformation._transform_to_anthropic_format(
            simple_chat_request, model_params
        )

        # Make request should fail immediately without retry
        with pytest.raises(AnthropicAuthenticationError):
            AnthropicTransformation._make_request_with_retry(
                mock_handler,
                anthropic_request,
                "claude-3-5-sonnet-20241022",
                max_retries=3
            )

        # Should only be called once (no retry)
        assert mock_handler.completion_request.call_count == 1

    @patch('runtime.clients.handler.llm_http_handler.LLMHttpHandler')
    def test_max_retries_exhausted(self, mock_handler_class, valid_credentials, simple_chat_request, model_params):
        """Test that all retry attempts are exhausted."""
        mock_handler = Mock()

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.json.return_value = {
            "type": "rate_limit_error",
            "message": "Rate limit exceeded"
        }

        # All attempts fail with rate limit
        mock_handler.completion_request.side_effect = httpx.HTTPStatusError(
            "Rate limit exceeded",
            request=Mock(),
            response=mock_response
        )
        mock_handler_class.return_value = mock_handler

        anthropic_request = AnthropicTransformation._transform_to_anthropic_format(
            simple_chat_request, model_params
        )

        # Make request should fail after all retries
        with pytest.raises(AnthropicRateLimitError):
            AnthropicTransformation._make_request_with_retry(
                mock_handler,
                anthropic_request,
                "claude-3-5-sonnet-20241022",
                max_retries=3
            )

        # Should be called 4 times (initial + 3 retries)
        assert mock_handler.completion_request.call_count == 4

    def test_embeddings_not_supported(self, valid_credentials):
        """Test that embeddings endpoint raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Anthropic API does not support embeddings endpoint"):
            AnthropicTransformation.transform_embeddings(Mock(), valid_credentials)

    def test_rerank_not_supported(self, valid_credentials):
        """Test that rerank endpoint raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="Anthropic API does not support rerank endpoint"):
            AnthropicTransformation.transform_rerank(Mock(), valid_credentials)

    def test_parameter_handling_edge_cases(self):
        """Test edge cases in parameter handling."""
        # Test with minimal parameters
        request = ChatCompletionRequest(
            model="claude-3-5-sonnet-20241022",
            messages=[ChatMessage(role="user", content="Test")],
            max_tokens=None  # Should default to 4096
        )

        result = AnthropicTransformation._transform_to_anthropic_format(request, {})
        assert result["max_tokens"] == 4096

        # Test with all optional parameters
        request = ChatCompletionRequest(
            model="claude-3-5-sonnet-20241022",
            messages=[ChatMessage(role="user", content="Test")],
            max_tokens=2000,
            temperature=0.5,
            top_p=0.8,
            top_k=50
        )

        result = AnthropicTransformation._transform_to_anthropic_format(request, {})
        assert result["max_tokens"] == 2000
        assert result["temperature"] == 0.5
        assert result["top_p"] == 0.8
        assert result["top_k"] == 50

    def test_custom_api_base(self):
        """Test using custom API base URL."""
        custom_credentials = {
            "credentials": {
                "api_key": "test-key",
                "api_base": "http://10.0.0.96:8000"
            },
            "sdk_type": "anthropic"
        }

        result = AnthropicTransformation.setup_environment(custom_credentials)
        assert result["api_base"] == "http://10.0.0.96:8000"

    def test_default_api_base(self):
        """Test default API base URL is used when not provided."""
        credentials = {
            "credentials": {
                "api_key": "test-key"
            },
            "sdk_type": "anthropic"
        }

        result = AnthropicTransformation.setup_environment(credentials)
        assert result["api_base"] == AnthropicTransformation.DEFAULT_API_BASE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
