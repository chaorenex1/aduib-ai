from abc import abstractmethod, ABC


class AbstractSplitter(ABC):
    """
    切分文本
    :param text: str
    :param kwargs: other parameters
    :return: list of words
    """
    @abstractmethod
    def split(self, text: str, **kwargs) -> list[str]:
        pass