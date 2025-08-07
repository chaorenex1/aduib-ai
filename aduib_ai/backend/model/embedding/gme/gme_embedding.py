import torch

from backend.model.embedding.base_embedding import AbstractEmbedding
from backend.model.embedding.gme.gme_inference import GmeQwen2VL

"""
gme 多模态嵌入
"""
class GmeEmbedding(AbstractEmbedding):
    def similarity(self, sentence1: list[str], sentence2: list[str], **kwargs):
        pass

    def embedding(self, sentence: list[str], **kwargs):
        if sentence:
            e_text = self.model.get_text_embeddings(texts=sentence)
            return e_text
        elif kwargs.get('images', []):
            images = kwargs.get('images')
            e_image = self.model.get_image_embeddings(images=images)
            return e_image
        elif sentence and kwargs.get('images', []):
            e_text = self.model.get_text_embeddings(texts=sentence)
            images = kwargs.get('images')
            e_image = self.model.get_image_embeddings(images=images)
            return e_text*e_image.sum(-1)

    def __init__(self, model_path):
        super().__init__()
        self.model_path = model_path
        self.max_length = 8192
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model= GmeQwen2VL(model_path=self.model_path,device=self.device)