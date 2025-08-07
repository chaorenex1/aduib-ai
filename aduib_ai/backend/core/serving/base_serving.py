"""
ai chat serving
"""
from abc import ABC, abstractmethod


class AbstractServing(ABC):
    """
    chat serving
    """
    def __init__(self, **kwargs):
        pass

    @abstractmethod
    def chat(self, text: str, **kwargs):
        """
        chat
        :param text: str
        :param kwargs: other parameters
        :return: str
        """
        pass

    def tags(self,**kwargs):
        """
        chat
        :param kwargs: other parameters
        :return: str
        """
        pass