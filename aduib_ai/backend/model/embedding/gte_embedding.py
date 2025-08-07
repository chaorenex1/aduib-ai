from modelscope import pipeline, Tasks

from backend.model.embedding.base_embedding import AbstractEmbedding
from backend.core.util.factory import auto_register


def load_model(model_path:str)-> pipeline:
    return pipeline(Tasks.sentence_embedding,
                           model=model_path,
                           sequence_length=1024
                           )  # sequence_length 代表最大文本长度，默认值为128

@auto_register('gte_embedding')
class GteEmbedding(AbstractEmbedding):
    def similarity(self, sentence1: list[str], sentence2: list[str], **kwargs):
        """
        :param sentence1:
        :param sentence2:
        :param kwargs:
        :return: similarity
        """
        return self.model(input={"source_sentence": sentence1, "sentences_to_compare": sentence2})['scores']

    def embedding(self,sentence:list[str] , **kwargs):
        """
        :param sentence:
        :param kwargs:
        :return: vector
        """
        return self.model(input={"source_sentence": sentence})['text_embedding']

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model_path = kwargs['model_path']
        self.model = load_model(self.model_path)