from typing import Any

from pydantic import BaseModel
from pymilvus import MilvusClient, DataType, Function, FunctionType
from pymilvus.orm.types import infer_dtype_bydata
from typing_extensions import Optional

from component.vdb.base_vector import BaseVector
from component.vdb.fields import Field
from component.vdb.vector_factory import AbstractVectorFactory
from component.vdb.vector_type import VectorType
from models import KnowledgeBase
from runtime.entities.document_entities import Document
from runtime.rag.embeddings.embeddings import Embeddings
from configs import config


import logging
logger = logging.getLogger(__name__)


class MilvusConfig(BaseModel):
    uri: str
    token: str
    user: str
    password: str
    database: str = "milvus"
    enable_hybrid: bool = False


class MilvusVector(BaseVector):
    def __init__(self, collection_name, config: MilvusConfig):
        super().__init__(collection_name)
        self.collection_name = collection_name
        self.config = config
        self.client = MilvusClient(
            uri=self.config.uri,
            token=self.config.token,
            user=config.user,
            password=config.password,
            database=config.database,
        )
        self.enable_hybrid = config.enable_hybrid
        self.fields = []
        self.consisency_level = "Session"

    def get_type(self) -> str:
        return VectorType.MILVUS

    def save(self, texts: list[Document], embeddings: list[list[float]], **kwargs):
        index_params = {"metric_type": "IP", "index_type": "HNSW", "params": {"M": 8, "efConstruction": 64}}
        metadatas = [d.metadata if d.metadata is not None else {} for d in texts]
        self.create_collection(embeddings, metadatas, index_params)
        self.add_texts(texts, embeddings)

    def delete_by_ids(self, ids: list[str]):
        res = self.client.query(self.collection_name, filter=f'metadata["doc_id"] in {ids}', output_fields=["id"])
        if res:
            self.client.delete(collection_name=self.collection_name, ids=[r["id"] for r in res])

    def exists(self, id: str) -> bool:
        res = self.client.query(self.collection_name, filter=f'metadata["doc_id"] == "{id}"', output_fields=["id"])
        return len(res) > 0

    def get_ids_by_metadata_field(self, key: str, value: str):
        """
        Get document IDs by metadata field key and value.
        """
        result = self.client.query(
            collection_name=self.collection_name, filter=f'metadata["{key}"] == "{value}"', output_fields=["id"]
        )
        if result:
            return [item["id"] for item in result]
        else:
            return None

    def delete_all(self):
        self.client.drop_collection(self.collection_name)

    def delete_by_metadata_field(self, key: str, value: str):
        """
        Delete documents by metadata field key and value.
        """
        if self.client.has_collection(self.collection_name):
            ids = self.get_ids_by_metadata_field(key, value)
            if ids:
                self.client.delete(collection_name=self.collection_name, pks=ids)

    def search_by_vector(self, vector: list[float], **kwargs) -> list[Document]:
        knowledge_ids_filter = kwargs.get("knowledge_ids_filter")
        filter = ""
        if knowledge_ids_filter:
            knowledge_ids = ", ".join(f'"{id}"' for id in knowledge_ids_filter)
            filter = f'metadata["knowledge_id"] in [{knowledge_ids}]'
        results = self.client.search(
            collection_name=self.collection_name,
            data=[vector],
            anns_field=Field.VECTOR.value,
            limit=kwargs.get("top_k", 4),
            output_fields=[Field.CONTENT_KEY.value, Field.METADATA_KEY.value],
            filter=filter,
        )

        return self.process_search_results(
            results,
            output_fields=[Field.CONTENT_KEY.value, Field.METADATA_KEY.value],
            score_threshold=float(kwargs.get("score_threshold") or 0.0),
        )

    def search_by_full_text(self, text: str, **kwargs) -> list[Document]:
        if not self.enable_hybrid:
            logger.warning(
                "Full-text search is disabled: set MILVUS_ENABLE_HYBRID_SEARCH=true (requires Milvus >= 2.5.0)."
            )
            return []
        knowledge_ids_filter = kwargs.get("knowledge_ids_filter")
        filter = ""
        if knowledge_ids_filter:
            knowledge_ids = ", ".join(f"'{id}'" for id in knowledge_ids_filter)
            filter = f'metadata["knowledge_id"] in [{knowledge_ids}]'

        results = self.client.search(
            collection_name=self.collection_name,
            data=[text],
            anns_field=Field.SPARSE_VECTOR.value,
            limit=kwargs.get("top_k", 4),
            output_fields=[Field.CONTENT_KEY.value, Field.METADATA_KEY.value],
            filter=filter,
        )

        return self.process_search_results(
            results,
            output_fields=[Field.CONTENT_KEY.value, Field.METADATA_KEY.value],
            score_threshold=float(kwargs.get("score_threshold") or 0.0),
        )

    def create_collection(
        self, embeddings, metadatas: Optional[list[dict]] = None, index_params: Optional[dict] = None
    ):
        if not self.client.has_collection(self.collection_name):
            dimension = len(embeddings[0])
            # Create schema
            schema = self.client.create_schema(auto_id=True, enable_dynamic_field=True)
            if metadatas:
                schema.add_field(field_name=Field.METADATA_KEY.value, datatype=DataType.JSON, max_length=65535)
            schema.add_field(field_name=Field.PRIMARY_KEY.value, datatype=DataType.INT64, auto_id=True, is_primary=True)
            schema.add_field(
                field_name=Field.CONTENT_KEY.value,
                datatype=DataType.VARCHAR,
                max_length=65535,
                enable_analyzer=self.enable_hybrid,
            )

            schema.add_field(field_name=Field.VECTOR.value, datatype=infer_dtype_bydata(embeddings[0]), dim=dimension)
            if self.enable_hybrid:
                schema.add_field(field_name=Field.SPARSE_VECTOR.value, datatype=DataType.SPARSE_FLOAT_VECTOR)
                schema.add_function(
                    Function(
                        name="text_bm25",
                        input_field_names=[Field.CONTENT_KEY.value],
                        output_field_names=[Field.SPARSE_VECTOR.value],
                        function_type=FunctionType.BM25,
                    )
                )
            # Create index
            index_params_obj = self.client.prepare_index_params()
            index_params_obj.add_index(Field.VECTOR.value, **index_params)
            if self.enable_hybrid:
                index_params_obj.add_index(
                    field_name=Field.SPARSE_VECTOR.value, index_type="AUTOINDEX", metric_type="BM25"
                )
            return self.client.create_collection(
                collection_name=self.collection_name,
                schema=schema,
                index_params=index_params_obj,
                consistency_level=self.consisency_level,
            )

    def add_texts(self, texts: list[Document], embeddings: list[list[float]]):
        insert_data_list = []
        for i, text in enumerate(texts):
            insert_data = {
                Field.CONTENT_KEY.value: text.content,
                Field.METADATA_KEY.value: text.metadata,
                Field.VECTOR.value: embeddings[i],
            }
            insert_data_list.append(insert_data)

        return self.client.insert(collection_name=self.collection_name, data=insert_data_list)

    def process_search_results(
        self, results: list[Any], output_fields: list[str], score_threshold: float = 0.0
    ) -> list[Document]:
        docs = []
        for result in results[0]:
            metadata = result["entity"].get(output_fields[1], {})
            metadata["score"] = result["distance"]

            if result["distance"] > score_threshold:
                doc = Document(content=result["entity"].get(output_fields[0], ""), metadata=metadata)
                docs.append(doc)

        return docs


class MilvusVectorFactory(AbstractVectorFactory):
    def init_vector(self, knowledge: KnowledgeBase, attributes: list, embeddings: Embeddings) -> BaseVector:
        collection_name = "kb_" + str(knowledge.rag_type) + "_vector"
        milvus_config = MilvusConfig(
            uri=config.MILVUS_URI or "",
            token=config.MILVUS_TOKEN or "",
            user=config.MILVUS_USER or "",
            password=config.MILVUS_PASSWORD or "",
            database=config.MILVUS_DATABASE or "",
            enable_hybrid=config.MILVUS_ENABLE_HYBRID_SEARCH or False,
        )
        return MilvusVector(collection_name=collection_name, config=milvus_config)
