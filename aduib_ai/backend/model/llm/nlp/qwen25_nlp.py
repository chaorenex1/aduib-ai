"""
qwen25 nlp module
"""
from backend.core.util.factory import auto_register
from backend.model.llm.nlp.base_nlp import AbstractNlp, TaskType

@auto_register('qwen25_nlp')
class Qwen25Nlp(AbstractNlp):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model_path = kwargs['model_path']

    def generate(self, task: TaskType,text:str, **kwargs):
        """
        :param task:
        :param text:
        :param kwargs:
        :return: result
        """
        pass