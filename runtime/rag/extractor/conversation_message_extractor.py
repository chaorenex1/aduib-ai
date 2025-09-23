import json
from collections import defaultdict

from models import get_db, ConversationMessage
from runtime.entities.document_entities import Document
from runtime.rag.extractor.extractor_base import BaseExtractor


class ConversationMessageExtractor(BaseExtractor):
    def extract(self) -> list[Document]:
        with get_db() as session:
            try:
                messages = (
                    session.query(ConversationMessage)
                    .order_by(ConversationMessage.message_id, ConversationMessage.created_at)
                    .all()
                )
                grouped = defaultdict(list)
                for msg in messages:
                    grouped[msg.message_id].append((msg.role, msg.content))
                    msg.extracted_state = 1
                    session.commit()

                documents = []
                for message_id, items in grouped.items():
                    # Pair consecutive user-assistant messages
                    for i in range(len(items) - 1):
                        if items[i][0] == "user" and items[i + 1][0] == "assistant":
                            documents.append(
                                Document(
                                    metadata={"message_id": message_id},
                                    content="question:" + items[i][1] + "\n\n" + "answer:" + items[i + 1][1] + "\n\n",
                                )
                            )
            except Exception as e:
                session.rollback()
                raise e
        return documents
