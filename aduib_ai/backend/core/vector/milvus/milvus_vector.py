from backend.core.util.factory import auto_register, Factory
from backend.core.vector.base_vector import AbstractVector
from backend.core.vector.milvus.milvus_client import Milvus

@auto_register('milvus_vector')
class MilvusVector(AbstractVector):
    def search(self,**kwargs):
        if 'vectors' not in kwargs:
            if 'text' not in kwargs:
                raise ValueError('text or vectors must be provided')
            if 'EMBEDDING_MODEL_TYPE' not in kwargs:
                raise ValueError('EMBEDDING_MODEL_TYPE must be provided')
            kwargs['vectors'] = Factory.get_instance(kwargs['EMBEDDING_MODEL_TYPE']).embedding(**kwargs)
        return self.client.hybrid_search(**kwargs)

    def vectorize(self,**kwargs):
        if 'vectors' not in kwargs:
            if 'text' not in kwargs:
                raise ValueError('text or vectors must be provided')
            if 'EMBEDDING_MODEL_TYPE' not in kwargs:
                raise ValueError('EMBEDDING_MODEL_TYPE must be provided')
            kwargs['vectors'] = Factory.get_instance(kwargs['EMBEDDING_MODEL_TYPE']).embedding(**kwargs)[0]
        return self.client.insert(**kwargs)

    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.client = Milvus(**kwargs)


