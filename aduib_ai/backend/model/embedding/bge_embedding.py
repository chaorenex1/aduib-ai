import concurrent
import os
from concurrent.futures import ThreadPoolExecutor

import torch
from tqdm import tqdm

from backend.model.embedding.base_embedding import AbstractEmbedding
from FlagEmbedding import BGEM3FlagModel

from backend.core.util.factory import auto_register


@auto_register('bge_embedding')
class BgeEmbedding(AbstractEmbedding):
    def embedding(self, sentences: list[str], **kwargs):
        if len(sentences) >12:
            sentences = [sentences[i:i + 12] for i in range(0, len(sentences), 12)]
            process_count = 30 if os.cpu_count() > 60 else (os.cpu_count() - 2 if os.cpu_count() > 4 else 1)
            embeddings = []
            with ThreadPoolExecutor(max_workers=process_count) as executor:
                for sentence in sentences:
                    futures = [executor.submit(self.do_embedding, sentence)]
                    for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures)):
                        embeddings.append(future.result())
            return [item for sublist in embeddings for item in sublist]
        else:
            embeddings = self.do_embedding(sentences)
        # embeddings_2 = model.encode(sentences_2)['dense_vecs']
        # similarity = embeddings_1 @ embeddings_2.T
        # print(similarity)
        # [[0.6265, 0.3477], [0.3499, 0.678 ]]
        if kwargs.get('dense_vecs', False):
            return embeddings['dense_vecs']
        elif kwargs.get('sparse_vecs', False):
            return embeddings['lexical_weights']

    def do_embedding(self, sentences):
        return self.embedding_model.encode(sentences,
                                           batch_size=12,
                                           max_length=self.max_length,
                                           return_sparse=True)

    def similarity(self, sentence1: list[str], sentence2: list[str], **kwargs):
        embeddings_1 = self.embedding(sentence1)
        embeddings_2 = self.embedding(sentence2)
        similarity = embeddings_1 @ embeddings_2.T
        return similarity

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model_path = kwargs['model_path']
        self.max_length = 8192
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.embedding_model = BGEM3FlagModel(self.model_path,
                                              use_fp16=False,
                                              device=self.device)
        self.rank_model = BGEM3FlagModel(self.model_path,
                                         use_fp16=False,
                                         device=self.device)