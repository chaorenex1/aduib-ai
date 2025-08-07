from backend.core.vector.milvus.milvus_client import Milvus
from backend.model.embedding.jina_embedding import JinaEmbedding as Jina

if __name__ == '__main__':
    milvus = Milvus(uri='http://10.0.0.96:19530',user='root',password='123456',db_name='aduib_vector')
    # collection = milvus.delete_collection('test')
    # collection2 = milvus.delete_collection('test2')
    # collection3 = milvus.delete_collection('test3')
    # print(milvus.load_collection_state('test'))
    # create_collection = milvus.create_collection('test', 1024)
    print(milvus.load_collection_state('test'))
    # milvus.create_collection('test2', 1024)
    print(milvus.load_collection_state('test2'))
    # milvus.create_spars_collection('test3')
    print(milvus.load_collection_state('test3'))
    # bge embedding
    # 密集向量
    # bge = Bge(model_path='L:\\llmmodels\\bge-m3')
    # bge_embedding = bge.embedding(['Python is a programming language'],dense_vecs=True)
    # print(bge_embedding)
    # print(milvus.insert('test2', bge_embedding[0],'Python is a programming language'))
    # 稀疏向量
    # bge_embedding2 = bge.embedding(['Python is a programming language'],sparse_vecs=True)
    # print(bge_embedding2)
    # print(milvus.insert('test3', bge_embedding2[0],'Python is a programming language'))
    # 密集向量相似度搜索
    # print(milvus.search('test2', bge_embedding,output_fields=['id','desc']))
    # 稀疏向量相似度搜索
    # print(milvus.search('test3', bge_embedding2,output_fields=['id','desc'],search_params={"params": {"drop_ratio_search": 0.5}}))
    # jina embedding

    # 文本分类嵌入
    # jina = Jina(model_path='L:\\llmmodels\\jina-embeddings-v3')
    # jina_embedding = jina.embedding(['paris is the capital of france'],task='text-matching')
    # jina_embedding2 = jina.embedding(['Python is a programming language'],task='text-matching')
    # print(jina_embedding)
    # print(milvus.insert('test2', jina_embedding[0],'paris is the capital of france'))
    # print(milvus.search('test2', jina_embedding,1,output_fields=['id','desc']))
    # print(jina_embedding2)
    # print(milvus.search(collection_name='test2', vectors=jina_embedding2,limit=1,output_fields=['id','desc']))
    # print(milvus.hybrid_search(collection_name='test2', vectors=jina_embedding2,limit=1,output_fields=['id','desc']))