from runtime.entities.provider_entities import ProviderSDKType
from runtime.transformation.base import LLMTransformation
from runtime.transformation.openai_like import OpenAILikeTransformation

LLMTransformations:dict[ProviderSDKType, type[LLMTransformation]] = {
    ProviderSDKType.OPENAI_LIKE: OpenAILikeTransformation
}


def get_llm_transformation(provider_type: ProviderSDKType) -> type[LLMTransformation]:
    """Get the LLM transformation class based on the provider type.
    Args:
        provider_type (ProviderSDKType): The provider type.
    Returns:
        type[LLMTransformation]: The LLM transformation class.
    """
    return LLMTransformations.get(provider_type, OpenAILikeTransformation)