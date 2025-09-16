
class RAGProcessorFactory:
    @staticmethod
    def get_rag_processor(rag_type: str):
        if rag_type == "paragraph":
            from .processor.paragraph_rag_processor import ParagraphRAGProcessor
            return ParagraphRAGProcessor()
        elif rag_type == "qa":
            from .processor.qa_rag_processor import QARAGProcessor
            return QARAGProcessor()
        else:
            raise ValueError(f"Unknown RAG processor type: {rag_type}")