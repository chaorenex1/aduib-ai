import concurrent
import os
from concurrent.futures import ThreadPoolExecutor

import torch
from modelscope import AutoModel
from tqdm import tqdm

from backend.core.util.factory import auto_register
from backend.model.embedding.base_embedding import AbstractEmbedding



@auto_register('jina_embedding')
class JinaEmbedding(AbstractEmbedding):
    """
    Jina Embedding
    :param model_path: model path
    :param task: task type When calling the `encode` function, you can choose a `task` based on the use case: 'retrieval.query', 'retrieval.passage', 'separation', 'classification', 'text-matching' Alternatively, you can choose not to pass a `task`, and no specific LoRA adapter will be used.
    :return: List of vectors
    """
    def embedding(self, sentences: list[str], **kwargs):
        if 'task' not in kwargs:
            kwargs['task'] = 'text-matching'
        if len(sentences) > 45:
            process_count = 30 if os.cpu_count() > 60 else (os.cpu_count() - 2 if os.cpu_count() > 4 else 1)
            sentences = [sentences[i:i + 45] for i in range(0, len(sentences), 45)]
            embeddings = []
            with ThreadPoolExecutor(max_workers=process_count) as executor:
                for sentence in sentences:
                    futures = [executor.submit(self.do_embedding, sentence, **kwargs)]
                    for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures)):
                        embeddings.append(future.result())
            return [item for sublist in embeddings for item in sublist]
        else:
            return self.do_embedding(sentences, **kwargs)

    def do_embedding(self, sentences, **kwargs):
        return self.model.encode(sentences, task=kwargs['task'], max_length=self.max_length)

    """
    Jina Similarity
    :param sentence1: list of sentences
    :param sentence2: list of sentences
    :param kwargs: other parameters
    :return: similarity scores
    """
    def similarity(self, sentence1: list[str], sentence2: list[str], **kwargs):
        embeddings_1 = self.embedding(sentence1, **kwargs)
        embeddings_2 = self.embedding(sentence2, **kwargs)
        similarity = embeddings_1 @ embeddings_2.T
        return similarity

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model_path = kwargs['model_path']
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.max_length = 8192
        try:
            AutoModel.from_pretrained("jinaai/xlm-roberta-flash-implementation")
        except:
            pass
        self.model=AutoModel.from_pretrained(self.model_path, trust_remote_code=True).to(self.device)
