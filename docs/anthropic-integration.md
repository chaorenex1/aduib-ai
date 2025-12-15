# Anthropic Claude Model Integration Guide

## Overview

This document provides comprehensive documentation for integrating Anthropic's Claude models into the LLM application framework. The implementation follows the existing architecture patterns and provides seamless integration with the current model management system.

## Features

- **x-api-key Authentication**: Secure authentication using Anthropic's API key format
- **Multiple Model Support**: Support for all major Claude model versions (Sonnet, Haiku, Opus)
- **Error Handling**: Comprehensive error mapping and retry strategies
- **OpenAI Compatibility**: Transparent integration with existing OpenAI-like API interfaces
- **Streaming Support**: Support for streaming responses (Phase 2)

## Supported Models

| Model Name | Description | Status |
|------------|-------------|---------|
| `claude-3-5-sonnet-20241022` | Latest Claude 3.5 Sonnet | ✅ Supported |
| `claude-3-5-haiku-20241022` | Latest Claude 3.5 Haiku | ✅ Supported |
| `claude-3-opus-20240229` | Claude 3 Opus | ✅ Supported |
| `claude-3-sonnet-20240229` | Claude 3 Sonnet | ✅ Supported |
| `claude-3-haiku-20240307` | Claude 3 Haiku | ✅ Supported |

## Configuration

### Provider Configuration

To add Anthropic as a provider, configure the provider with the following JSON structure:

```json
{
  "name": "anthropic",
  "provider_type": "anthropic",
  "support_model_type": ["LLM"],
  "provider_config": {
    "api_key": "your-anthropic-api-key-here",
    "api_base": "https://api.anthropic.com/v1"
  }
}
```

### Model Configuration

For each Claude model, configure it with the following structure:

```json
{
  "name": "claude-3-5-sonnet-20241022",
  "type": "LLM",
  "provider_name": "anthropic",
  "max_tokens": 4096,
  "model_params": {
    "temperature": 0.7,
    "max_tokens": 4096
  }
}
```

## API Usage

### Chat Completion

The Anthropic integration provides OpenAI-compatible chat completion endpoints:

```python
# Example usage
from runtime.model_manager import ModelManager

manager = ModelManager()
model_instance = manager.get_model_instance("claude-3-5-sonnet-20241022")

response = model_instance.invoke_llm({
    "model": "claude-3-5-sonnet-20241022",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"}
    ],
    "max_tokens": 1000,
    "temperature": 0.7
})
```

### Request Format

Requests are automatically transformed from OpenAI format to Anthropic format:

**OpenAI Format:**
```json
{
  "model": "claude-3-5-sonnet-20241022",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
  ],
  "max_tokens": 1000,
  "temperature": 0.7
}
```

**Transformed to Anthropic Format:**
```json
{
  "model": "claude-3-5-sonnet-20241022",
  "system": "You are a helpful assistant.",
  "messages": [
    {"role": "user", "content": "Hello!"}
  ],
  "max_tokens": 1000,
  "temperature": 0.7
}
```

## Error Handling

### Error Types

The integration provides comprehensive error handling:

| Error Type | HTTP Status | Description | Retry Strategy |
|------------|-------------|-------------|----------------|
| `AnthropicAuthenticationError` | 401, 403 | Invalid API key or permissions | ❌ No retry |
| `AnthropicRateLimitError` | 429 | Rate limit exceeded | ✅ Exponential backoff |
| `AnthropicModelNotFoundError` | 404 | Model not found | ❌ No retry |
| `AnthropicInvalidRequestError` | 400 | Invalid request parameters | ❌ No retry |
| `AnthropicServerError` | 500-504 | Server errors | ✅ Exponential backoff |

### Retry Strategy

The default retry strategy uses exponential backoff with jitter:

- **Max Retries**: 3
- **Base Delay**: 1 second
- **Max Delay**: 60 seconds
- **Jitter**: Enabled (to avoid thundering herd)

## Security

### API Key Management

- API keys are stored encrypted in the database
- Keys are transmitted securely using HTTPS
- Authentication uses `x-api-key` header format

### Data Privacy

- All API calls are made directly to Anthropic's servers
- No user data is stored permanently
- Prompt data is handled according to Anthropic's privacy policy

## Performance

### Response Times

- **Average Response Time**: < 2 seconds
- **Throughput**: Supports concurrent requests
- **Caching**: Leverages existing caching infrastructure

### Limitations

- **Embeddings**: Anthropic does not provide embeddings API
- **Reranking**: Anthropic does not provide reranking API
- **Streaming**: Currently supported in non-streaming mode (Phase 2 will add streaming)

## Testing

### Unit Tests

Run the comprehensive test suite:

```bash
python -m pytest tests/anthropic/ -v
```

### Integration Tests

To test with actual Anthropic API:

1. Set environment variables:
   ```bash
   export ANTHROPIC_API_KEY="your-test-api-key"
   ```

2. Run integration tests:
   ```bash
   python -m pytest tests/integration/test_anthropic_integration.py -v
   ```

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Verify API key is correct and active
   - Check that the provider configuration is properly set

2. **Model Not Found**
   - Verify model name matches supported models exactly
   - Check that the model is properly configured in the database

3. **Rate Limiting**
   - Implement exponential backoff in your application
   - Consider caching responses for repeated queries

### Logging

Enable debug logging for detailed troubleshooting:

```python
import logging
logging.getLogger("runtime.transformation.anthropic").setLevel(logging.DEBUG)
```

## Migration Guide

### From External Claude Integration

If you were previously using external Claude integration:

1. Remove any external Claude API clients
2. Configure Anthropic provider in the system
3. Update model configurations to use the new provider
4. Update API calls to use the standard model interface

### API Changes

No breaking changes to the existing API. The integration maintains full compatibility with the existing OpenAI-like interface.

## Future Enhancements

### Phase 2 Features

- **Streaming Support**: Real-time streaming responses
- **Tool Calling**: Support for Claude's tool calling capabilities
- **Advanced Caching**: Enhanced response caching strategies
- **Batch Processing**: Support for batch API requests

### Roadmap

- [ ] Streaming response support
- [ ] Tool calling integration
- [ ] Performance optimizations
- [ ] Advanced monitoring and metrics

## Support

For issues and questions:

1. Check the troubleshooting section above
2. Review the unit tests for usage examples
3. Check Anthropic's official API documentation
4. Contact the development team for technical support

---

*Last Updated: 2025-10-09*
*Version: 1.0*