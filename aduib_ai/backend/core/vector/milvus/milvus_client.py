import logging as log

import torch
from milvus_model.reranker import BGERerankFunction, JinaRerankFunction, CrossEncoderRerankFunction
from pymilvus import MilvusClient, DataType, AnnSearchRequest, RRFRanker, WeightedRanker

from backend.core.util.factory import Factory


class Milvus:
    def __init__(self,**kwargs):
        self.client = MilvusClient(uri=kwargs['uri'],
                                   user=kwargs['user'] if 'user' in kwargs else '',
                                   password=kwargs['password'] if 'password' in kwargs else '')
        # db_name = kwargs['db_name'] if 'db_name' in kwargs else 'aduib_vector', # 默认数据库名
        # self.client.create_database(db_name, timeout=30)
        self.snowflake = kwargs['id_generator']
        self.ranker = RRFRanker()
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.ranker_model_type = kwargs['ranker_model_type'] if 'ranker_model_type' in kwargs else ''
        self.ranker_model_path = kwargs['ranker_model_path'] if 'ranker_model_path' in kwargs else ''
        if self.ranker_model_type == 'bge_ranking':
            self.ranker_rf = BGERerankFunction(
                model_name=self.ranker_model_path,  # Specify the model name. Defaults to `BAAI/bge-reranker-v2-m3`.
                device=self.device,  # Specify the device to use. Defaults to `cuda` if available, otherwise `cpu`.
            )
        elif self.ranker_model_type == 'jina_ranking':
            self.ranker_rf = JinaRerankFunction(
                model_name=self.ranker_model_path,  # Specify the model name. Defaults to `jina-ai/jina-embeddings-v2-small-en`.
                device=self.device,  # Specify the device to use. Defaults to `cuda` if available, otherwise `cpu`.
            )

    """
    创建集合
    :param collection_name: 集合名称
    :param dimension: 向量维度
    :return: collection
    """
    def create_collection(self, collection_name, dimension):
        # Create schema
        schema = self.client.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=dimension)
        schema.add_field(field_name="id", datatype=DataType.VARCHAR, is_primary=True, max_length=50)
        schema.add_field(field_name="desc", datatype=DataType.VARCHAR,max_length=512)
        # Create index
        index_params = self.client.prepare_index_params()
        index_params.add_index(index_name="index_id", field_name="id", index_type="AUTOINDEX")
        index_params.add_index(index_name="index_vector", field_name="vector", index_type="IVF_FLAT", metric_type="IP",params={"nlist": 128})
        return self.client.create_collection(collection_name=collection_name, schema=schema, index_params=index_params)

    """
    创建稀疏集合
    :param collection_name: 集合名称
    :return: collection
    """
    def create_spars_collection(self, collection_name):
        # Create schema
        schema = self.client.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field(field_name="vector", datatype=DataType.SPARSE_FLOAT_VECTOR)
        schema.add_field(field_name="id", datatype=DataType.VARCHAR, is_primary=True, max_length=50)
        schema.add_field(field_name="doc", datatype=DataType.VARCHAR,max_length=65535)
        schema.add_field(field_name="desc", datatype=DataType.VARCHAR,max_length=512)
        # Create index
        index_params = self.client.prepare_index_params()
        index_params.add_index(index_name="index_id", field_name="id", index_type="AUTOINDEX")
        index_params.add_index(index_name="index_vector", field_name="vector", index_type="SPARSE_INVERTED_INDEX", metric_type="IP")
        return self.client.create_collection(collection_name=collection_name, schema=schema, index_params=index_params)
    """
    删除集合
    :param collection_name: 集合名称
    :return: collection
    """
    def delete_collection(self, collection_name):
        return self.client.drop_collection(collection_name=collection_name)

    """
    释放集合
    :param collection_name: 集合名称
    :return: collection
    """
    def release_collection(self, collection_name):
        return self.client.release_collection(collection_name=collection_name)

    """
    修改集合
    """
    def alter_collection(self, collection_name):
        pass

    """
    加载集合状态
    :param collection_name: 集合名称
    :return: collection
    """
    def load_collection_state(self, collection_name):
        return self.client.get_load_state(collection_name=collection_name)

    def insert(self, collection_name:str, vectors,desc:str):
        log.info(f'Inserting {len(vectors)} vectors into collection {collection_name}')
        return self.client.insert(collection_name=collection_name, data={"vector": vectors, "id": str(self.snowflake.generate()), "desc": desc})

    """
    搜索
    :param collection_name: 集合名称
    :param vectors: 向量
    :param query: 查询语句
    :param limit: 返回数量
    :param output_fields: 输出字段
    :param search_params: 搜索参数
    :param filter_params: 过滤参数
    """
    def search(self, collection_name, vectors,query, limit:int=5, output_fields=None, search_params=None, filter_params=None):
        if search_params is None:
            search_params = {"params": {"nprobe": 10}, "metric_type": "IP"}
        res = self.client.search(
            collection_name=collection_name,
            data=vectors,
            anns_field="vector",
            search_params= search_params,
            limit=limit,
            output_fields=output_fields,
            filter_params=filter_params,
        )
        ranker_result = self.ranker_rf(query=query, documents=[hit['entity'].get("doc") for hit in res[0]], top_k=limit)
        log.info(f'Searching {len(vectors)} vectors in collection {collection_name}')
        return ranker_result

    """
    混合搜索
    :param collection_name: 集合名称
    :param vectors: 向量
    :param query: 查询语句
    :param search_fields: 搜索字段
    :param limit: 返回数量
    :param search_params: 搜索参数
    :param output_fields: 输出字段
    """
    def hybrid_search(self, collection_name, vectors,query, search_fields=None, limit:int=5, search_params=None, output_fields=None):
        if search_fields is None:
            search_fields = ['vector']
        if search_params is None:
            search_params = {"params": {"nprobe": 10}, "metric_type": "IP"}
        req_list = []
        for i in range(len(search_fields)):
            search_param={
                "data": vectors,
                "anns_field": search_fields[i],
                "limit": limit,
                "param": search_params
            }
            ann=AnnSearchRequest(**search_param)
            req_list.append(ann)
        res = self.client.hybrid_search(collection_name=collection_name, reqs=req_list,ranker=WeightedRanker(),limit=limit, output_fields=output_fields)
        log.info(f'Searching {len(res)} vectors in collection {collection_name}')
        ranker_result = self.ranker_rf(query=query, documents=[hit['entity'].get("doc") for hit in res[0]], top_k=limit)
        return ranker_result

    def delete(self, collection_name, ids):
        # return self.client.delete_entity_by_id(collection_name=collection_name, id_array=ids)
        pass
