"""
代码切分
"""


from langchain_text_splitters import RecursiveCharacterTextSplitter, Language

from backend.core.util.factory import auto_register
from backend.core.splitter.base_splitter import AbstractSplitter


def getLang(language)-> Language:
    return Language(language)

@auto_register('code_splitter')
class CodeSplitter(AbstractSplitter):
    def __init__(self,language,chunk_size=512, chunk_overlap=0):
        language = getLang(language)
        self.language = language
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = RecursiveCharacterTextSplitter.from_language(language,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def split(self,text, **kwargs) -> list[str]:
        return self.text_splitter.split_text(text)
