"""
Unit tests for OllamaTransformation class.
Tests Ollama API specific behavior:
- Default API base (http://localhost:11434)
- Chat endpoint (/api/chat)
- Embeddings endpoint (/api/embeddings)
- Optional API key (Ollama doesn't require it)
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import asyncio

from runtime.transformation.ollama.transformation import OllamaTransformation
from runtime.entities.llm_entities import ChatCompletionRequest


class TestOllamaTransformation(unittest.TestCase):
    """Test cases for OllamaTransformation class."""

    def setUp(self):
        """Set up test fixtures."""
        self.valid_credentials = {
            "credentials": {
                "api_key": "test-api-key-123",
                "api_base": "http://localhost:11434"
            },
            "sdk_type": "ollama"
        }
        self.model_params = {
            "temperature": 0.7,
            "max_tokens": 1000
        }

    def test_setup_environment_default_api_base(self):
        """Test environment setup with default API base (http://localhost:11434)."""
        credentials_without_base = {
            "credentials": {},
            "sdk_type": "ollama"
        }

        result = OllamaTransformation.setup_environment(credentials_without_base)

        self.assertEqual(result["api_base"], "http://localhost:11434")

    def test_setup_environment_custom_api_base(self):
        """Test environment setup with custom API base."""
        credentials_with_custom_base = {
            "credentials": {
                "api_base": "http://192.168.1.100:11434"
            },
            "sdk_type": "ollama"
        }

        result = OllamaTransformation.setup_environment(credentials_with_custom_base)

        self.assertEqual(result["api_base"], "http://192.168.1.100:11434")

    def test_setup_environment_no_api_key_required(self):
        """Test that Ollama does not require API key."""
        credentials_without_key = {
            "credentials": {
                "api_base": "http://localhost:11434"
            },
            "sdk_type": "ollama"
        }

        # Should not raise an error
        result = OllamaTransformation.setup_environment(credentials_without_key)

        self.assertIsNotNone(result)
        self.assertEqual(result["api_base"], "http://localhost:11434")
        # API key should be None or empty, not required
        self.assertFalse(result.get("api_key"))

    def test_provider_type_is_ollama(self):
        """Test that provider_type is set to 'ollama'."""
        self.assertEqual(OllamaTransformation.provider_type, "ollama")

    def test_default_api_base_constant(self):
        """Test that DEFAULT_API_BASE is set correctly."""
        self.assertEqual(OllamaTransformation.DEFAULT_API_BASE, "http://localhost:11434")

    @patch('runtime.transformation.ollama.transformation.LLMHttpHandler')
    def test_transform_message_uses_correct_path(self, mock_handler_class):
        """Test that transform_message uses /api/chat endpoint."""
        # Set up the mock chain properly with AsyncMock for async methods
        mock_handler_instance = MagicMock()
        mock_handler_instance.completion_request = AsyncMock(return_value=MagicMock())
        mock_handler_class.return_value = mock_handler_instance

        credentials = OllamaTransformation.setup_environment(self.valid_credentials)
        request = ChatCompletionRequest(
            model="llama2",
            messages=[
                {"role": "user", "content": "Hello, how are you?"}
            ],
            max_tokens=1000,
            temperature=0.7
        )

        # Call the async method
        asyncio.run(OllamaTransformation.transform_message(
            model_params=self.model_params,
            prompt_messages=request,
            credentials=credentials,
            stream=False
        ))

        # Verify the handler was initialized with correct path
        mock_handler_class.assert_called_once()
        call_args = mock_handler_class.call_args
        self.assertEqual(call_args[0][0], "/api/chat")

    @patch('runtime.transformation.ollama.transformation.LLMHttpHandler')
    def test_transform_embeddings_uses_correct_path(self, mock_handler_class):
        """Test that transform_embeddings uses /api/embeddings endpoint."""
        from runtime.entities.text_embedding_entities import EmbeddingRequest

        # Set up the mock chain properly with AsyncMock for async methods
        mock_handler_instance = MagicMock()
        mock_handler_instance.embedding_request = AsyncMock(return_value=MagicMock())
        mock_handler_class.return_value = mock_handler_instance

        credentials = OllamaTransformation.setup_environment(self.valid_credentials)

        embedding_request = EmbeddingRequest(
            model="llama2",
            input=["Hello world"]
        )

        # Call the async method
        asyncio.run(OllamaTransformation.transform_embeddings(
            texts=embedding_request,
            credentials=credentials
        ))

        # Verify the handler was initialized with correct path
        mock_handler_class.assert_called_once()
        call_args = mock_handler_class.call_args
        self.assertEqual(call_args[0][0], "/api/embeddings")


if __name__ == "__main__":
    unittest.main()
