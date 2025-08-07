# import torch
# from BCEmbedding import RerankerModel, EmbeddingModel
# from transformers import AutoTokenizer, AutoModel
#
# from embedding.base_embedding import AbstractEmbedding
#
#
# class Bce(AbstractEmbedding):
#     def embedding(self, sentences: list[str], **kwargs):
#         # extract embeddings
#         embeddings = self.embedding_model.encode(sentences)
#         return embeddings
#
#     def similarity(self, sentence1: list[str], sentence2: list[str], **kwargs):
#         query_ = kwargs['query']
#
#         # construct sentence pairs
#         sentence_pairs = [[query_, s1] for s1 in sentence1]
#
#         # method 0: calculate scores of sentence pairs
#         scores = self.reranker_model.compute_score(sentence_pairs)
#
#         # method 1: rerank passages
#         # rerank_results = model.rerank(query, passages)
#         return scores
#
#     def __init__(self, model_path):
#         super().__init__(model_path)
#         self.model_path = model_path
#         # self.tokenizer = AutoTokenizer.from_pretrained(model_path)
#         # self.model = AutoModel.from_pretrained(model_path)
#         self.device='cuda' if torch.cuda.is_available() else 'cpu'
#         self.max_length = 512
#         self.embedding_model = EmbeddingModel(model_name_or_path=self.model_path,device=self.device,use_fp16=True)
#         self.reranker_model = RerankerModel(model_name_or_path=self.model_path,device=self.device,use_fp16=True)