import json
from typing import Any

from aduib_rpc.server.rpc_execution.service_call import service

from runtime.rag.rag_type import RagType
from service import KnowledgeBaseService


@service(service_name="RagService")
class RagService:
    """RAG Service for handling retrieval-augmented generation requests."""
    async def retrieval_from_paragraph(self, query: str) -> dict[str, Any]:
        docs = await KnowledgeBaseService.retrieve_from_knowledge_base(RagType.PARAGRAPH, query)
        return self._build_response(docs, RagType.PARAGRAPH)

    async def retrieval_from_qa(self, query: str) -> dict[str, Any]:
        docs = await KnowledgeBaseService.retrieve_from_knowledge_base(RagType.QA, query)
        return self._build_response(docs, RagType.QA)

    async def retrieval_from_browser_history(
        self, query: str, start_time: str | None = None, end_time: str | None = None
    ) -> dict[str, Any]:
        docs = await KnowledgeBaseService.retrieval_from_browser_history(query, start_time, end_time)
        return self._build_response(docs, "browser_history")

    def _build_response(self, results: list, rag_type: RagType | str) -> dict[str, Any]:
        rag_value = rag_type.value if isinstance(rag_type, RagType) else rag_type
        contexts: list[dict[str, Any]] = []
        if rag_value == RagType.PARAGRAPH:
            for result in results:
                contexts.append({"doc_id": result.metadata.get("doc_id"), "content": result.content})
        elif rag_value == RagType.QA:
            for result in results:
                contexts.append(
                    {
                        "doc_id": result.metadata.get("doc_id"),
                        "question": result.content,
                        "answer": result.metadata.get("answer"),
                    }
                )
        else:
            contexts = results

        return {
            "rag_type": rag_value,
            "count": len(contexts),
            "documents": contexts,
            "context": json.dumps(contexts, ensure_ascii=False, indent=2),
        }
