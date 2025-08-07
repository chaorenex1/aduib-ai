# import uuid
# from typing import Any, AsyncGenerator
#
# from fastapi import APIRouter
# from ollama import EmbeddingsResponse
# from starlette.responses import StreamingResponse
#
# from aduib_ai.api.params import CompletionRequestDTO, EmbeddingRequestDTO
# from aduib_ai.core.config import settings
# from aduib_ai.core.crud import bulk_save_embedding
# from aduib_ai.core.db import Chunk, FileChunk, Embedding
# from ...backend.core.serving.ollama import OllamaServing
# from ...backend.core.util.factory import Factory
# from ...backend.model.embedding.base_embedding import AbstractEmbedding
# from ...model.engine import SessionDep
#
# router=APIRouter(tags=['ollama'],prefix='/api')
# ollama = OllamaServing(base_url=settings.OLLAMA_BASE_URL)
#
#
# @router.post('/chat')
# async def chat_complete(chat:CompletionRequestDTO) -> Any:
#     """
#     chat complete
#     :return:
#     """
#     response = ollama.chat(model=chat.model,
#                        messages=chat.messages,
#                        tools=chat.tools,
#                        stream=chat.stream,
#                        format=chat.format,
#                        options=chat.options,
#                        keep_alive=chat.keep_alive)
#
#     async def completion_stream_generator()-> AsyncGenerator[bytes, None]:
#         for chunk in response:
#             yield f'{chunk.model_dump_json(exclude_none=True)}\n'
#             if chunk.done:
#                 break
#     if chat.stream:
#         return StreamingResponse(completion_stream_generator(), media_type='text/event-stream')
#     else:
#         return response
#
#
# @router.get('/tags')
# def tags():
#     """
#     tags
#     :return:
#     """
#     return ollama.tags()
#
#
# @router.post('/embeddings')
# async def embeddings(session:SessionDep,embeddingReq:EmbeddingRequestDTO)->EmbeddingsResponse:
#     """
#     embedding
#     :return:
#     """
#     embedding_model:AbstractEmbedding = Factory.get_instance(class_name=settings.EMBEDDING_MODEL_TYPE)
#     prompt = embeddingReq.prompt
#     # 是否是file开头
#     if prompt.startswith('file_'):
#         #1.从数据库查询所有文件块
#         """
#         const data = await this.db
#       .select()
#       .from(chunks)
#       .innerJoin(fileChunks, eq(chunks.id, fileChunks.chunkId))
#       .where(eq(fileChunks.fileId, id));
#         """
#         file_id=prompt.split(':')[0]
#         user_id=prompt.split(':')[1]
#         result = session.query(Chunk) \
#             .join(FileChunk, Chunk.id == FileChunk.chunk_id) \
#             .filter(FileChunk.file_id == file_id) \
#             .all()
#         embeddings = embedding_model.embedding(sentences=[chunk.text for chunk in result], dense_vecs=True)
#         #2. 循环embedding写入数据库
#         embedding_models = [Embedding(id=uuid.uuid4(), chunk_id=chunk.id, embeddings=embedding.tolist(),
#                                       model=settings.EMBEDDING_MODEL_TYPE, user_id=user_id) for chunk, embedding in zip(result, embeddings)]
#         bulk_save_embedding(session, embedding_models)
#         return EmbeddingsResponse(embedding=[0])
#     else:
#         embeddings = embedding_model.embedding(sentences=[prompt], dense_vecs=True)
#         return EmbeddingsResponse(embedding=embeddings[0].tolist())
