# from embedding.base_embedding import AbstractEmbedding
# import torch
# import torch.nn.functional as F
#
# from torch import Tensor
# from modelscope import AutoTokenizer, AutoModel
#
# class GteQw27b(AbstractEmbedding):
#     def embedding(self, sentences: list[str], **kwargs):
#         """
#         :param sentences:
#         :param kwargs:
#         :return:
#         """
#         batch_dict = self.tokenizer(sentences, max_length=self.max_length, padding=True, truncation=True,
#                                    return_tensors='pt')
#         outputs = self.model(**batch_dict)
#         embeddings = last_token_pool(outputs.last_hidden_state, batch_dict['attention_mask'])
#         embeddings = F.normalize(embeddings, p=2, dim=1)
#         return embeddings
#
#     def compare(self, sentence1: list[str], sentence2: list[str], **kwargs):
#         pass
#
#     def __init__(self, model_path):
#         super().__init__(model_path)
#         self.model_path = model_path
#         self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
#         self.model = AutoModel.from_pretrained(model_path, trust_remote_code=True)
#         self.max_length = 8192
#
#
# def last_token_pool(last_hidden_states: Tensor,
#                  attention_mask: Tensor) -> Tensor:
#     left_padding = (attention_mask[:, -1].sum() == attention_mask.shape[0])
#     if left_padding:
#         return last_hidden_states[:, -1]
#     else:
#         sequence_lengths = attention_mask.sum(dim=1) - 1
#         batch_size = last_hidden_states.shape[0]
#         return last_hidden_states[torch.arange(batch_size, device=last_hidden_states.device), sequence_lengths]
#
#
# def get_detailed_instruct(task_description: str, query: str) -> str:
#     return f'Instruct: {task_description}\nQuery: {query}'