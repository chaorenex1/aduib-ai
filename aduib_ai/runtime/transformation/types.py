from runtime.entities.provider_entities import ProviderSDKType
from runtime.transformation.base import LLMTransformation
from runtime.transformation.openai_like.openai_like import OpenAILikeTransformation
from runtime.transformation.transformers.transformers import TransformersTransformation

LLMTransformations:dict[ProviderSDKType, type[LLMTransformation]] = {
    ProviderSDKType.OPENAI_LIKE: OpenAILikeTransformation,
    ProviderSDKType.TRANSFORMER: TransformersTransformation
}


def get_llm_transformation(provider_type: ProviderSDKType) -> type[LLMTransformation]:
    """Get the LLM transformation class based on the provider type.
    Args:
        provider_type (ProviderSDKType): The provider type.
    Returns:
        type[LLMTransformation]: The LLM transformation class.
    """
    return LLMTransformations.get(provider_type, OpenAILikeTransformation)