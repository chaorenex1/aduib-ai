"""
llama3 NLP module
"""
from backend.core.util.factory import auto_register
from backend.model.llm.nlp.base_nlp import AbstractNlp, TaskType

@auto_register('llama3_nlp')
class Llama3NLP(AbstractNlp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model_path = kwargs['model_path']

    def generate(self, task: TaskType,text:str, **kwargs):
        """
        :param task:
        :param text:
        :param kwargs:
        :return:
        """
        pass