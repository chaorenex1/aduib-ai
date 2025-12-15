from runtime.entities.provider_entities import ProviderSDKType
from runtime.transformation.base import LLMTransformation
from runtime.transformation.deepseek.transformation import DeepseekTransformation
from runtime.transformation.github.transformation import GithubCopilotTransformation
from runtime.transformation.openai_like.transformation import OpenAILikeTransformation
from runtime.transformation.anthropic.transformation import AnthropicTransformation
from runtime.transformation.openrouter.transformation import OpenRouterTransformation

LLMTransformations: dict[ProviderSDKType, type[LLMTransformation]] = {
    ProviderSDKType.OPENAI_LIKE: OpenAILikeTransformation,
    ProviderSDKType.GITHUB_COPILOT: GithubCopilotTransformation,
    ProviderSDKType.DEEPSEEK: DeepseekTransformation,
    ProviderSDKType.ANTHROPIC: AnthropicTransformation,
    ProviderSDKType.OPENROUTER: OpenRouterTransformation,
}

try:
    from runtime.transformation.transformers.transformation import TransformersTransformation

    LLMTransformations[ProviderSDKType.TRANSFORMER] = TransformersTransformation
except Exception as e:
    pass


def get_llm_transformation(provider_type: ProviderSDKType) -> type[LLMTransformation]:
    """Get the LLM transformation class based on the provider type.
    Args:
        provider_type (ProviderSDKType): The provider type.
    Returns:
        type[LLMTransformation]: The LLM transformation class.
    """
    return LLMTransformations.get(provider_type, OpenAILikeTransformation)
