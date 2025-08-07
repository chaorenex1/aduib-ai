from openai import AsyncOpenAI

from backend.core.util.factory import auto_register
from backend.core.serving.base_serving import AbstractServing


@auto_register('openai_chat')
class OpenAiServing(AbstractServing):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.api_key = kwargs['api_key']
        self.model = kwargs['model']
        self.base_url = kwargs['base_url'] if 'base_url' in kwargs else 'http://localhost:11434/v1'
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    def chat(self, text: str, **kwargs):
        params={
            'model': self.model,
            'message': [{'role': 'user', 'content': text},{'role': 'system', 'content': kwargs.get('system_message') if 'system_message' in kwargs else 'you are a assistant, please help me to do something'}],
            'temperature': kwargs.get('temperature') if 'temperature' in kwargs else 1,
            'top_p': kwargs.get('top_p') if 'top_p' in kwargs else 0.9
        }
        return self.client.chat.completions.create(**params)