from langchain_text_splitters import RecursiveCharacterTextSplitter, TokenTextSplitter

from backend.core.util.factory import auto_register
from backend.core.splitter.base_splitter import AbstractSplitter
"""
按语义切分文本
"""
@auto_register('text_splitter')
class RecursiveTextSplitter(AbstractSplitter):
    def __init__(self, chunk_size=512, chunk_overlap=0):
        super().__init__()
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            model_name="gpt-4",
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def split(self, text:str, **kwargs):
        return self.text_splitter.split_text(text)


class TokenSplitter(AbstractSplitter):
    def __init__(self, chunk_size=512, chunk_overlap=0):
        super().__init__()
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = TokenTextSplitter(encoding_name="o200k_base",chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    def split(self, text:str, **kwargs):
        return self.text_splitter.split_text(text)


