from event.event_manager import event_manager_context

event_manager = event_manager_context.get()


@event_manager.subscribe(event="paragraph_rag_from_web_memo")
def paragraph_rag_from_web_memo(crawl_text: str, crawl_type: str) -> None:
    """
    Create a knowledge document from web crawl text and store it in the default paragraph knowledge base.
    """
    import hashlib

    from models import KnowledgeBase, get_db
    from models import KnowledgeDocument
    from runtime.rag.rag_type import RagType
    from service import FileService, KnowledgeBaseService
    from runtime.rag_manager import RagManager

    file_hash = hashlib.sha256(crawl_text.encode('utf-8')).hexdigest()
    file_name = f"/web_memo/{file_hash}.{crawl_type}"
    file_record = FileService.upload_bytes(file_name, crawl_text.encode('utf-8'))

    from runtime.generator.generator import LLMGenerator
    # name,language = LLMGenerator.generate_conversation_name(crawl_text)
    name, language = "", "chinese"
    with get_db() as session:
        existing_kb = session.query(KnowledgeBase).filter_by(default_base=1, rag_type=RagType.PARAGRAPH).one_or_none()
        if not existing_kb:
            existing_kb = KnowledgeBaseService.create_knowledge_base("Default Paragraph KB", RagType.PARAGRAPH, 1)

        doc = session.query(KnowledgeDocument).filter_by(
            knowledge_base_id=existing_kb.id,
            file_id=str(file_record.id),
        ).one_or_none()
        if not doc:
            doc = KnowledgeDocument(knowledge_base_id=existing_kb.id,
                                    title=name,
                                    file_id=file_record.id,
                                    doc_language=language,
                                    doc_from="web_memo",
                                    rag_type=RagType.PARAGRAPH,
                                    data_source_type='file',
                                    rag_status="pending", )

            session.add(doc)
            session.commit()
            session.refresh(doc)

    RagManager().run([doc])
