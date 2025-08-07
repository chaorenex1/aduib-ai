from abc import ABC


class BaseModel(ABC):
    model_path: str
    def __init__(self, **kwargs):
        if 'model_path' not in kwargs:
            raise ValueError('model_path is required')
        self.model_path = kwargs['model_path']
        pass