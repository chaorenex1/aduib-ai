from ..entities.model_entities import ModelType
from ..entities.rerank_entities import RerankRequest, RerankResponse
from ..providers.base import AiModel


class RerankModel(AiModel):
    """
    Base Model class for rerank model.
    """

    model_type: ModelType = ModelType.RANKER

    def invoke(
        self,
        query: RerankRequest
    ) -> RerankResponse:
        """
        Invoke rerank model

        :param model: model name
        :param credentials: model credentials
        :param query: search query
        :param docs: docs for reranking
        :param score_threshold: score threshold
        :param top_n: top n
        :param user: unique user id
        :return: rerank result
        """
        try:
            from ..transformation import get_llm_transformation
            transformation = get_llm_transformation(
                self.credentials.get("sdk_type", "openai_like"))

            credentials = transformation.setup_validate_credentials(self.credentials)
            # if not query.score_threshold:
            #     query.score_threshold = 0.8
            result: RerankResponse = transformation.transform_rerank(
                query=query,
                credentials=credentials,
            )
            return result
        except Exception as e:
            raise e