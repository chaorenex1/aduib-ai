"""
 向量化父类 提供一个抽象方法 embedding
"""
from abc import abstractmethod

from backend.base_model import BaseModel


class AbstractEmbedding(BaseModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        pass

    """ 
    向量化句子
    :param sentences: list of sentences
    :param kwargs: other parameters
    :return: list of vectors
    """
    @abstractmethod
    def embedding(self, sentences:list[str], **kwargs):
        pass

    """
    计算句子相似度
    :param sentence1: list of sentences
    :param sentence2: list of sentences
    :param kwargs: other parameters
    :return: similarity scores
    """
    @abstractmethod
    def similarity(self, sentence1:list[str], sentence2:list[str], **kwargs):
        pass