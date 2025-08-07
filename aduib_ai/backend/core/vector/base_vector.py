from abc import ABC, abstractmethod


class AbstractVector(ABC):
    def __init__(self,**kwargs):
        pass

    """
    存储向量
    :param vectors: list of vectors
    :param kwargs: other parameters
    """
    @abstractmethod
    def vectorize(self, *args, **kwargs):
        pass
    """
    搜索
    :param args: other parameters
    :param kwargs: other parameters
    :return: list of vectors
    """
    @abstractmethod
    def search(self, *args, **kwargs):
        pass