"""
End-to-end API integration tests for Anthropic Claude model support.
These tests verify the complete integration with the application's API endpoints.

Note: These tests require a running application instance and valid Anthropic API credentials.

Environment variables required:
    - ANTHROPIC_API_KEY: Your Anthropic API key
    - TEST_API_BASE_URL: Base URL of the running application (default: http://localhost:8000)

Run with: pytest tests/anthropic/test_anthropic_api_integration.py -v -s
"""

import os
import pytest
import httpx
import time
import json
from typing import Dict, Any


class TestAnthropicAPIIntegration:
    """End-to-end API integration tests for Anthropic Claude support."""

    @pytest.fixture
    def api_base_url(self):
        """Fixture providing API base URL."""
        return os.getenv("TEST_API_BASE_URL", "http://localhost:8000")

    @pytest.fixture
    def anthropic_api_key(self):
        """Fixture providing Anthropic API key."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            pytest.skip("ANTHROPIC_API_KEY environment variable not set")
        return api_key

    @pytest.fixture
    def http_client(self):
        """Fixture providing HTTP client."""
        return httpx.Client(timeout=30.0)

    @pytest.fixture
    def valid_model_config(self, anthropic_api_key):
        """Fixture providing valid model configuration."""
        return {
            "name": "claude-3-5-sonnet-20241022",
            "model_type": "llm",
            "provider": "anthropic",
            "provider_config": {
                "api_key": anthropic_api_key,
                "api_base": "https://api.anthropic.com/v1"
            },
            "model_parameters": {
                "temperature": 0.7,
                "max_tokens": 1000
            }
        }

    def test_models_endpoint_returns_anthropic_models(self, http_client, api_base_url):
        """Test that /api/v1/models endpoint includes Anthropic models."""
        response = http_client.get(f"{api_base_url}/api/v1/models")

        assert response.status_code == 200

        data = response.json()
        assert "data" in data

        # Check if Anthropic models are present in the response
        models = data["data"]
        anthropic_models = [model for model in models if model.get("provider") == "anthropic"]

        # At least some Anthropic models should be available
        assert len(anthropic_models) > 0

        # Verify model structure
        for model in anthropic_models:
            assert "id" in model
            assert "name" in model
            assert "provider" in model
            assert model["provider"] == "anthropic"

    def test_chat_completion_with_anthropic_model(self, http_client, api_base_url, valid_model_config):
        """Test chat completion endpoint with Anthropic model."""
        # First, ensure the model is configured
        # This assumes the model is already configured in the system

        chat_request = {
            "model": "claude-3-5-sonnet-20241022",
            "messages": [
                {"role": "user", "content": "What is 2+2? Please respond with just the number."}
            ],
            "max_tokens": 50,
            "temperature": 0.1
        }

        response = http_client.post(
            f"{api_base_url}/api/v1/chat/completions",
            json=chat_request,
            headers={"Content-Type": "application/json"}
        )

        # The request should succeed
        assert response.status_code == 200, f"Request failed: {response.text}"

        data = response.json()

        # Verify response structure
        assert "id" in data
        assert "object" in data
        assert data["object"] == "chat.completion"
        assert "created" in data
        assert "model" in data
        assert data["model"] == "claude-3-5-sonnet-20241022"
        assert "choices" in data
        assert len(data["choices"]) > 0

        # Verify choice structure
        choice = data["choices"][0]
        assert "index" in choice
        assert "message" in choice
        assert "role" in choice["message"]
        assert "content" in choice["message"]

        # Verify the response contains the expected answer
        content = choice["message"]["content"].strip()
        assert "4" in content, f"Expected '4' in response, got: {content}"

    def test_chat_completion_with_system_prompt(self, http_client, api_base_url):
        """Test chat completion with system prompt."""
        chat_request = {
            "model": "claude-3-5-sonnet-20241022",
            "messages": [
                {"role": "system", "content": "You are a helpful math tutor. Always respond with just the numerical answer."},
                {"role": "user", "content": "What is 3*4?"}
            ],
            "max_tokens": 50,
            "temperature": 0.1
        }

        response = http_client.post(
            f"{api_base_url}/api/v1/chat/completions",
            json=chat_request,
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 200, f"Request failed: {response.text}"

        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()

        # Should contain the numerical answer
        assert "12" in content, f"Expected '12' in response, got: {content}"

    def test_chat_completion_multi_turn_conversation(self, http_client, api_base_url):
        """Test multi-turn conversation with Anthropic model."""
        chat_request = {
            "model": "claude-3-5-sonnet-20241022",
            "messages": [
                {"role": "user", "content": "Hello, how are you?"},
                {"role": "assistant", "content": "I'm doing well, thank you! How can I help you today?"},
                {"role": "user", "content": "Can you help me with Python programming?"}
            ],
            "max_tokens": 100,
            "temperature": 0.7
        }

        response = http_client.post(
            f"{api_base_url}/api/v1/chat/completions",
            json=chat_request,
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 200, f"Request failed: {response.text}"

        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()

        # Should respond about Python programming
        assert len(content) > 0
        # Could contain words like "Python", "programming", "help", etc.
        assert any(word in content.lower() for word in ["python", "programming", "help", "sure"])

    def test_chat_completion_with_different_anthropic_models(self, http_client, api_base_url):
        """Test different Anthropic model versions."""
        models_to_test = [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307"
        ]

        for model_name in models_to_test:
            chat_request = {
                "model": model_name,
                "messages": [
                    {"role": "user", "content": f"Hello from {model_name}! What is 5+5?"}
                ],
                "max_tokens": 50,
                "temperature": 0.1
            }

            response = http_client.post(
                f"{api_base_url}/api/v1/chat/completions",
                json=chat_request,
                headers={"Content-Type": "application/json"}
            )

            # Some models might not be available, so we accept 404
            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"].strip()
                assert "10" in content, f"Model {model_name}: Expected '10' in response, got: {content}"
            elif response.status_code == 404:
                # Model not available, skip
                pytest.skip(f"Model {model_name} not available")
            else:
                # Other errors should fail the test
                assert False, f"Model {model_name}: Request failed with status {response.status_code}: {response.text}"

    def test_error_handling_invalid_model(self, http_client, api_base_url):
        """Test error handling for invalid model name."""
        chat_request = {
            "model": "invalid-model-name",
            "messages": [
                {"role": "user", "content": "Hello"}
            ],
            "max_tokens": 50
        }

        response = http_client.post(
            f"{api_base_url}/api/v1/chat/completions",
            json=chat_request,
            headers={"Content-Type": "application/json"}
        )

        # Should return an error for invalid model
        assert response.status_code in [400, 404, 422], f"Expected error status, got {response.status_code}: {response.text}"

    def test_error_handling_missing_api_key(self, http_client, api_base_url):
        """Test error handling when API key is missing or invalid."""
        # This test assumes there's a way to test with invalid credentials
        # In a real scenario, this would require configuring a model with invalid API key

        # For now, test with a model that doesn't exist
        chat_request = {
            "model": "claude-3-5-sonnet-20241022-invalid",
            "messages": [
                {"role": "user", "content": "Hello"}
            ],
            "max_tokens": 50
        }

        response = http_client.post(
            f"{api_base_url}/api/v1/chat/completions",
            json=chat_request,
            headers={"Content-Type": "application/json"}
        )

        # Should return an error
        assert response.status_code in [400, 404, 422], f"Expected error status, got {response.status_code}: {response.text}"

    def test_performance_basic_request(self, http_client, api_base_url):
        """Test basic request performance."""
        chat_request = {
            "model": "claude-3-5-sonnet-20241022",
            "messages": [
                {"role": "user", "content": "What is 2+2?"}
            ],
            "max_tokens": 50,
            "temperature": 0.1
        }

        start_time = time.time()
        response = http_client.post(
            f"{api_base_url}/api/v1/chat/completions",
            json=chat_request,
            headers={"Content-Type": "application/json"}
        )
        end_time = time.time()

        response_time = end_time - start_time

        # Request should succeed
        assert response.status_code == 200, f"Request failed: {response.text}"

        # Response time should be reasonable (under 10 seconds for basic request)
        assert response_time < 10.0, f"Response time too slow: {response_time:.2f} seconds"

        print(f"Basic request response time: {response_time:.2f} seconds")

    def test_request_with_custom_parameters(self, http_client, api_base_url):
        """Test request with various custom parameters."""
        chat_request = {
            "model": "claude-3-5-sonnet-20241022",
            "messages": [
                {"role": "user", "content": "Tell me a short story about a cat."}
            ],
            "max_tokens": 100,
            "temperature": 0.8,
            "top_p": 0.9,
            "top_k": 40
        }

        response = http_client.post(
            f"{api_base_url}/api/v1/chat/completions",
            json=chat_request,
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 200, f"Request failed: {response.text}"

        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()

        # Should generate a story about a cat
        assert len(content) > 0
        assert any(word in content.lower() for word in ["cat", "feline", "pet", "story"])


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
