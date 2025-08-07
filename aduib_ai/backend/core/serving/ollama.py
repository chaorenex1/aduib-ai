from ollama import Client

from backend.core.util.factory import auto_register
from backend.core.serving.base_serving import AbstractServing

@auto_register('ollama_chat')
class OllamaServing(AbstractServing):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.base_url = kwargs['base_url'] if 'base_url' in kwargs else 'http://localhost:11434'
        self.ollama = Client(host=self.base_url,headers={
            'api_key': kwargs['api_key'] if 'api_key' in kwargs else 'default'
        })

    def chat(self, **kwargs):
        return self.ollama.chat(**kwargs)

    def tags(self, **kwargs):
        return self.ollama.list()