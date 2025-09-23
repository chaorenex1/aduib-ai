import json
from typing import Any

from aduib_rpc.server.rpc_execution.service_call import service

from runtime.rag.rag_type import RagType
from service import KnowledgeBaseService


@service(service_name="RagService")
class RagService:
    """RAG Service for handling retrieval-augmented generation requests."""
    async def retrieval_from_paragraph(self, query: str) -> str:
        docs = await KnowledgeBaseService.retrieve_from_knowledge_base(RagType.PARAGRAPH,query)
        return self.create_context(docs,RagType.PARAGRAPH)

    async def retrieval_from_qa(self, query: str) -> str:
        docs = await KnowledgeBaseService.retrieve_from_knowledge_base(RagType.QA,query)
        return self.create_context(docs,RagType.QA)

    async def retrieval_from_browser_history(self, query: str,start_time: str = None,end_time: str = None) -> str:
        docs = await KnowledgeBaseService.retrieval_from_browser_history(query,start_time,end_time)
        return docs

    def create_context(self,results: list,rag_type: str) -> str:
        context=""
        contexts: list[dict[str, Any]] = []
        if rag_type == "paragraph":
            for result in results:
                contexts.append({"doc_id": result.metadata.get("doc_id"), "content": result.content})
            context = json.dumps(contexts, ensure_ascii=False, indent=2)
        else:
            for result in results:
                contexts.append({"doc_id": result.metadata.get("doc_id"), "question": result.content,
                                 "answer": result.metadata.get("answer")})
            context = json.dumps(contexts, ensure_ascii=False, indent=2)
        return context
