import json
import logging
import multiprocessing
import os
import signal
import sys
import threading
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Dict, Optional

import torch
import zmq
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForCausalLM

logger = logging.getLogger('transformers')


class TransformersConfig:
    """Configuration class for transformers"""
    FRONTEND_TCP_ADDRESS = "tcp://127.0.0.1:5555"
    BACKEND_TCP_ADDRESS = "tcp://127.0.0.1:5556"
    BACKEND_IPC_PATH = "ipc://" + os.path.expanduser("~/.aduib_ai/tmp/workers")
    CONNECTION_TIMEOUT = 2*60000  # milliseconds


class TaskReq(BaseModel):
    worker_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

class TaskResp(BaseModel):
    worker_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    success: bool = False


class TransformersLoader(ABC):
    """Abstract base class for loading transformer models."""

    def __init__(self, model: str, model_path: str,max_context_length:int=8192,
                 device: str = 'cpu',
                 instruction: Optional[str] = None,
                 system_prompt: Optional[str] = None):
        self.model = model.strip()
        self.model_path = model_path
        self.device = device
        self.instruction = instruction
        self.system_prompt = system_prompt
        self.worker_id = model.strip()
        self.model_instance = None
        self.tokenizer = None
        self.max_context_length = max_context_length

    @abstractmethod
    def init_model(self):
        """Initialize the transformer model"""
        pass

    @abstractmethod
    def transform(self, data: TaskReq) -> TaskResp:
        """Transform the input data"""
        pass


class EmbeddingTransformersLoader(TransformersLoader):
    """Concrete implementation of TransformersLoader for Embedding models using transformers"""

    def init_model(self):
        """Initialize the Embedding model"""
        try:
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model or self.model_path,
                trust_remote_code=True
            )

            # Load model
            from transformers import AutoModel
            self.model_instance = AutoModel.from_pretrained(
                self.model or self.model_path,
                trust_remote_code=True
            ).to(self.device).eval()

            # Set pad token if not exists
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token

            logger.info(f"Initializing Embedding model: {self.model} from {self.model_path} on {self.device}")

        except Exception as e:
            logger.error(f"Failed to initialize embedding model: {e}")
            raise

    def transform(self, data: TaskReq) -> TaskResp:
        """Transform the input data using the Embedding model"""
        try:
            logger.info(f"Transforming data with Embedding model: {self.model}")

            # Extract data
            request_data = data.data
            texts = request_data.get('texts', [])
            encoding_format = request_data.get('encoding_format', 'float')
            dimension = request_data.get('dimension', self._get_embedding_dimension())
            normalize_embeddings = request_data.get('normalize_embeddings', True)
            batch_size = request_data.get('batch_size', 32)

            # Validate input
            if not texts:
                raise ValueError("'texts' must be provided and non-empty")

            # Generate embeddings
            embeddings = self._generate_embeddings(texts, normalize_embeddings, batch_size,dimension)

            # Convert to requested format
            if encoding_format == 'base64':
                embeddings = self._encode_embeddings_base64(embeddings)

            return TaskResp(
                worker_id=str(self.worker_id),
                data={
                    'embeddings': embeddings,
                    'model': self.model,
                    'encoding_format': encoding_format,
                    'dimensions': dimension
                },
                success=True
            )

        except Exception as e:
            logger.error(f"Error in Embedding transform: {e}")
            return TaskResp(
                worker_id=str(self.worker_id),
                data={"error": str(e)},
                success=False
            )

    @torch.no_grad()
    def _generate_embeddings(self, texts: list, normalize: bool = True, batch_size: int = 32, target_dimension: int = None) -> list:
        """Generate embeddings using transformers model with batching"""
        all_embeddings = []

        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_embeddings = self._process_batch(batch_texts, normalize, target_dimension)
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    def _process_batch(self, batch_texts: list, normalize: bool,target_dimension:int) -> list:
        """Process a batch of texts"""
        # Tokenize batch
        inputs = self.tokenizer(
            batch_texts,
            padding=True,
            truncation=True,
            max_length=self.max_context_length,
            return_tensors="pt"
        )

        # Move to device
        for key in inputs:
            inputs[key] = inputs[key].to(self.device)

        # Get model outputs
        outputs = self.model_instance(**inputs)

        # Apply pooling strategy
        pooling_strategy = self._get_pooling_strategy()
        if pooling_strategy == 'mean':
            embeddings = self._mean_pooling(outputs.last_hidden_state, inputs['attention_mask'])
        elif pooling_strategy == 'cls':
            embeddings = self._cls_pooling(outputs.last_hidden_state)
        elif pooling_strategy == 'max':
            embeddings = self._max_pooling(outputs.last_hidden_state, inputs['attention_mask'])
        else:
            embeddings = self._mean_pooling(outputs.last_hidden_state, inputs['attention_mask'])

        # Normalize if requested
        if normalize:
            embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)

        # Truncate to target dimension if specified
        if target_dimension and embeddings.size(1) > target_dimension:
            embeddings = embeddings[:, :target_dimension]

        return embeddings.cpu().numpy().tolist()

    def _get_pooling_strategy(self) -> str:
        """Determine pooling strategy based on model type"""
        model_name = (self.model or self.model_path).lower()

        # Common embedding model patterns
        if any(name in model_name for name in ['sentence-transformers', 'all-minilm', 'all-mpnet']):
            return 'mean'
        elif any(name in model_name for name in ['bert', 'roberta', 'deberta']):
            return 'cls'
        elif 'bge' in model_name:
            return 'cls'
        else:
            return 'mean'  # Default to mean pooling

    def _mean_pooling(self, model_output: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        """Apply mean pooling to get sentence embeddings"""
        # Expand attention mask to match model output dimensions
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(model_output.size()).float()

        # Apply mask and compute mean
        sum_embeddings = torch.sum(model_output * input_mask_expanded, 1)
        sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)

        return sum_embeddings / sum_mask

    def _cls_pooling(self, model_output: torch.Tensor) -> torch.Tensor:
        """Use [CLS] token embedding"""
        return model_output[:, 0, :]

    def _max_pooling(self, model_output: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        """Apply max pooling to get sentence embeddings"""
        # Set masked tokens to large negative value
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(model_output.size()).float()
        model_output[input_mask_expanded == 0] = -1e9

        # Max pooling
        return torch.max(model_output, 1)[0]

    def _encode_embeddings_base64(self, embeddings: list) -> list:
        """Encode embeddings to base64 format"""
        import base64
        import struct
        import numpy as np

        encoded_embeddings = []
        for embedding in embeddings:
            # Convert to numpy array and then to bytes
            np_array = np.array(embedding, dtype=np.float32)
            bytes_data = np_array.tobytes()

            # Encode to base64
            encoded = base64.b64encode(bytes_data).decode('utf-8')
            encoded_embeddings.append(encoded)

        return encoded_embeddings

    def _get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by the model"""
        try:
            # Test with a simple input
            test_input = self.tokenizer("test", return_tensors="pt").to(self.device)

            with torch.no_grad():
                test_output = self.model_instance(**test_input)

                # Apply same pooling as in transform
                pooling_strategy = self._get_pooling_strategy()
                if pooling_strategy == 'mean':
                    test_embedding = self._mean_pooling(test_output.last_hidden_state, test_input['attention_mask'])
                elif pooling_strategy == 'cls':
                    test_embedding = self._cls_pooling(test_output.last_hidden_state)
                elif pooling_strategy == 'max':
                    test_embedding = self._max_pooling(test_output.last_hidden_state, test_input['attention_mask'])
                else:
                    test_embedding = self._mean_pooling(test_output.last_hidden_state, test_input['attention_mask'])

                return test_embedding.size(-1)

        except Exception as e:
            logger.warning(f"Failed to determine embedding dimension: {e}")
            return 1024  # Default BERT-like dimension


class ReRankTransformersLoader(TransformersLoader):
    """Concrete implementation of TransformersLoader for ReRank models"""

    def init_model(self):
        """Initialize the ReRank model"""
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model or self.model_path,
            padding_side='left',
            trust_remote_code=True
        )
        self.model_instance = AutoModelForCausalLM.from_pretrained(
            self.model or self.model_path,
            trust_remote_code=True
        ).to(self.device).eval()

        # Set default instruction if not provided
        if not self.instruction:
            self.instruction = self._get_default_instruction()

        logger.info(f"Initializing ReRank model: {self.model} from {self.model_path} on {self.device}")

    def _get_default_instruction(self) -> str:
        """Get default rerank instruction"""
        return (
            "Analyze the relevance between the given query and document. "
            "Determine if the document contains information that directly answers, "
            "relates to, or provides useful context for the query. Consider semantic "
            "similarity, topical relevance, and factual accuracy. The document should "
            "be considered relevant if it helps address the user's information need "
            "expressed in the query, even if it doesn't provide a complete answer."
        )

    def transform(self, data: TaskReq) -> TaskResp:
        """Transform the input data using the ReRank model"""
        try:
            logger.info(f"Transforming data with ReRank model: {self.model}")

            # Get task instruction
            task = self.instruction if self.instruction else self._get_default_instruction()

            # Extract data
            request_data = data.data
            queries = request_data.get('query', [])
            documents = request_data.get('documents', [])
            top_n = request_data.get('top_n', len(documents))

            # Validate input
            if not queries or not documents:
                raise ValueError("Both 'query' and 'documents' must be provided")

            # Process reranking
            scores = self._compute_rerank_scores(task, queries, documents)

            # Get top results
            sorted_results = self._get_top_results(scores, documents, top_n)

            return TaskResp(
                worker_id=str(self.worker_id),
                data={
                    'reranked_documents': sorted_results,
                    'scores': scores[:top_n]
                },
                success=True
            )

        except Exception as e:
            logger.error(f"Error in ReRank transform: {e}")
            return TaskResp(
                worker_id=str(self.worker_id),
                data={"error": str(e)},
                success=False
            )

    def _compute_rerank_scores(self, task: str, queries: list, documents: list) -> list:
        """Compute rerank scores for query-document pairs"""
        # Token setup
        token_false_id = self.tokenizer.convert_tokens_to_ids("no")
        token_true_id = self.tokenizer.convert_tokens_to_ids("yes")

        prefix = (
            "<|im_start|>system\n"
            "Judge whether the Document meets the requirements based on the Query "
            "and the Instruct provided. Note that the answer can only be \"yes\" or \"no\"."
            "<|im_end|>\n<|im_start|>user\n"
        )
        suffix = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"

        prefix_tokens = self.tokenizer.encode(prefix, add_special_tokens=False)
        suffix_tokens = self.tokenizer.encode(suffix, add_special_tokens=False)

        # Format pairs
        pairs = [
            self._format_instruction(task, query, doc)
            for query, doc in zip(queries, documents)
        ]

        # Process inputs
        inputs = self._process_inputs(pairs, prefix_tokens, suffix_tokens)

        # Compute scores
        return self._compute_logits(inputs, token_true_id, token_false_id)

    def _format_instruction(self, instruction: str, query: str, doc: str) -> str:
        """Format instruction template"""
        return (
            f"<Instruct>: {instruction}\n"
            f"<Query>: {query}\n"
            f"<Document>: {doc}"
        )

    def _process_inputs(self, pairs: list, prefix_tokens: list, suffix_tokens: list):
        """Process input pairs for tokenization"""
        inputs = self.tokenizer(
            pairs,
            padding=False,
            truncation='longest_first',
            return_attention_mask=False,
            max_length=self.max_context_length - len(prefix_tokens) - len(suffix_tokens)
        )

        for i, ele in enumerate(inputs['input_ids']):
            inputs['input_ids'][i] = prefix_tokens + ele + suffix_tokens

        inputs = self.tokenizer.pad(
            inputs,
            padding=True,
            return_tensors="pt",
            max_length=self.max_context_length
        )

        for key in inputs:
            inputs[key] = inputs[key].to(self.model_instance.device)

        return inputs

    @torch.no_grad()
    def _compute_logits(self, inputs, token_true_id: int, token_false_id: int) -> list:
        """Compute relevance scores from model logits"""
        batch_scores = self.model_instance(**inputs).logits[:, -1, :]
        true_vector = batch_scores[:, token_true_id]
        false_vector = batch_scores[:, token_false_id]
        batch_scores = torch.stack([false_vector, true_vector], dim=1)
        batch_scores = torch.nn.functional.log_softmax(batch_scores, dim=1)
        scores = batch_scores[:, 1].exp().tolist()
        return scores

    def _get_top_results(self, scores: list, documents: list, top_n: int) -> list:
        """Get top N documents based on scores"""
        scored_docs = list(zip(scores, documents))
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        return [doc for score, doc in scored_docs[:top_n]]



class ZMQBroker:
    """ZMQ Broker for handling message routing"""

    def __init__(self):
        self.poller = None
        self.ctx = None
        self.frontend = None
        self.backend = None
        self._running = False
        self._worker_addresses = {}  # store worker_id to address mapping
        self._client_worker_mapping = {}  # store client to worker mapping

    def start(self):
        """Start the broker"""
        try:
            self.ctx = zmq.Context()
            self.frontend = self.ctx.socket(zmq.ROUTER)
            self.backend = self.ctx.socket(zmq.ROUTER)

            self.frontend.bind("tcp://*:5555")

            if sys.platform == "win32":
                self.backend.bind("tcp://*:5556")
            else:
                os.makedirs(os.path.dirname(TransformersConfig.BACKEND_IPC_PATH), exist_ok=True)
                self.backend.bind(TransformersConfig.BACKEND_IPC_PATH)

            self._setup_signal_handlers()
            self._running = True
            logger.info("Broker started successfully")
            # zmq.proxy(self.frontend, self.backend)
            self.poller = zmq.Poller()
            self.poller.register(self.frontend, zmq.POLLIN)
            self.poller.register(self.backend, zmq.POLLIN)
            self._broker_loop()

        except Exception as e:
            logger.error(f"Failed to start broker: {e}")
            self.cleanup()
            raise

    def _broker_loop(self):
        """Main broker loop"""
        while self._running:
            try:
                socks = dict(self.poller.poll(10000))  # 10 second timeout

                # client message
                if self.frontend in socks and socks[self.frontend] == zmq.POLLIN:
                    self._handle_client_message()
                # worker message
                if self.backend in socks and socks[self.backend] == zmq.POLLIN:
                    self._handle_worker_message()

            except Exception as e:
                logger.error(f"Error in broker loop: {e}")
                break

    def _handle_client_message(self):
        """Handle message from client"""
        try:
            # 接收客户端消息
            client_id, empty, message_data = self.frontend.recv_multipart()

            # 解析任务请求
            try:
                message_json = json.loads(json.loads(message_data.decode('utf-8')))
                task_req = TaskReq.model_validate(message_json)
            except Exception as e:
                logger.error(f"Failed to parse client message: {e}")
                # 发送错误响应给客户端
                error_resp = TaskResp(
                    worker_id="",
                    data={"error": f"Invalid message format: {str(e)}"},
                    success=False
                )
                self.frontend.send_multipart([
                    client_id, b'',
                    error_resp.model_dump_json().encode('utf-8')
                ])
                return

            # 根据worker_id进行路由
            target_worker = task_req.worker_id
            if not target_worker:
                error_resp = TaskResp(
                    worker_id="",
                    data={"error": "No worker_id specified in request"},
                    success=False
                )
                self.frontend.send_multipart([
                    client_id, b'',
                    error_resp.model_dump_json().encode('utf-8')
                ])
                return

            # 存储客户端到worker的映射关系
            self._client_worker_mapping[client_id.decode()] = target_worker

            # 转发消息给指定的worker
            self.backend.send_multipart([
                target_worker.encode('utf-8'), b'',
                client_id, b'', message_data
            ])

            logger.debug(f"Routed message from client {client_id.decode()} to worker {target_worker}")

        except Exception as e:
            logger.error(f"Error handling client message: {e}")

    def _handle_worker_message(self):
        """Handle message from worker"""
        try:
            # 接收worker响应
            worker_id, empty1, client_id, empty2, response_data = self.backend.recv_multipart()

            # 将响应转发回对应的客户端
            self.frontend.send_multipart([client_id, b'', response_data])

            # 清理映射关系
            client_key = client_id.decode()
            if client_key in self._client_worker_mapping:
                del self._client_worker_mapping[client_key]

            logger.debug(f"Forwarded response from worker {worker_id.decode()} to client {client_key}")

        except Exception as e:
            logger.error(f"Error handling worker message: {e}")

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""

        def stop_handler(signum, frame):
            logger.info(f"Broker stopping...")
            self.stop()
            sys.exit(0)

        for sig in [signal.SIGINT, signal.SIGTERM]:
            signal.signal(sig, stop_handler)

    def stop(self):
        """Stop the broker"""
        self._running = False
        self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        if self.frontend:
            self.frontend.close()
        if self.backend:
            self.backend.close()
        if self.ctx:
            self.ctx.term()


class ZMQWorker:
    """ZMQ Worker for processing tasks"""

    def __init__(self, transformer_loader: TransformersLoader):
        self.transformer_loader = transformer_loader
        self.ctx = None
        self.socket = None
        self._running = False
        self._ready = False

    def start(self):
        """Start the worker"""
        try:
            self.transformer_loader.init_model()
            self.ctx = zmq.Context()
            self.socket = self.ctx.socket(zmq.DEALER)  # 改为DEALER配合ROUTER broker

            # 设置worker身份标识
            self.socket.setsockopt(zmq.IDENTITY, self.transformer_loader.worker_id.encode('utf-8'))

            backend_address = self._get_backend_address()
            self.socket.connect(backend_address)

            self._setup_signal_handlers()
            self._running = True
            self._ready = True

            logger.info(f"Worker {self.transformer_loader.worker_id} started and ready")
            self._run_loop()

        except Exception as e:
            logger.error(f"Failed to start worker: {e}")
            self._ready = False
            self.cleanup()
            raise

    def _run_loop(self):
        """Main worker loop"""
        while self._running:
            try:
                poller = zmq.Poller()
                poller.register(self.socket, zmq.POLLIN)

                if poller.poll(1000):  # 1 second timeout
                    # 接收消息
                    client_id, empty, message_data = self.socket.recv_multipart()

                    try:
                        message_json = json.loads(json.loads(message_data.decode('utf-8')))
                        task_req = TaskReq.model_validate(message_json)

                        # 处理任务
                        response = self._process_task(task_req)

                        # 发送响应
                        self.socket.send_multipart([
                            client_id, b'',
                            response.model_dump_json().encode('utf-8')
                        ])

                    except Exception as e:
                        logger.error(f"Error processing task: {e}")
                        error_resp = TaskResp(
                            worker_id=self.transformer_loader.worker_id,
                            data={"error": str(e)},
                            success=False
                        )
                        self.socket.send_multipart([
                            client_id, b'',
                            error_resp.model_dump_json().encode('utf-8')
                        ])

            except zmq.Again:
                continue
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
                break

    def _process_task(self, task_req: TaskReq) -> TaskResp:
        """Process incoming task"""
        try:
            # 检查是否为健康检查请求
            if task_req.data and task_req.data.get("type") == "HEALTH_CHECK":
                return TaskResp(
                    worker_id=self.transformer_loader.worker_id,
                    data={"status": "ready" if self._ready else "not ready"},
                    success=self._ready
                )

            # 检查worker ID匹配
            if task_req.worker_id != self.transformer_loader.worker_id:
                logger.warning(
                    f"Worker ID mismatch: expected {self.transformer_loader.worker_id}, got {task_req.worker_id}")
                return TaskResp(
                    worker_id=self.transformer_loader.worker_id,
                    data={"error": f"Worker ID mismatch"},
                    success=False
                )

            # 检查worker是否就绪
            if not self._ready:
                return TaskResp(
                    worker_id=self.transformer_loader.worker_id,
                    data={"error": "Worker is not ready yet"},
                    success=False
                )

            # 处理实际任务
            return self.transformer_loader.transform(task_req)

        except Exception as e:
            logger.error(f"Error processing task: {e}")
            return TaskResp(
                worker_id=self.transformer_loader.worker_id,
                data={"error": str(e)},
                success=False
            )

    def _get_backend_address(self):
        """Get backend address based on platform"""
        if sys.platform == "win32":
            return TransformersConfig.BACKEND_TCP_ADDRESS
        else:
            return TransformersConfig.BACKEND_IPC_PATH

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""

        def stop_handler(signum, frame):
            logger.info(f"Worker {self.transformer_loader.worker_id} stopping...")
            self.stop()
            sys.exit(0)

        for sig in [signal.SIGINT, signal.SIGTERM]:
            signal.signal(sig, stop_handler)

    def stop(self):
        """Stop the worker"""
        self._running = False
        self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        if self.socket:
            self.socket.close()
        if self.ctx:
            self.ctx.term()


class ZMQClient:
    """ZMQ Client for sending requests"""

    def __init__(self):
        self.ctx = None
        self.socket = None

    @contextmanager
    def connect(self):
        """Context manager for client connection"""
        try:
            self.ctx = zmq.Context()
            self.socket = self.ctx.socket(zmq.REQ)
            self.socket.setsockopt(zmq.IDENTITY, "client".encode('utf-8'))
            self.socket.setsockopt(zmq.RCVTIMEO, TransformersConfig.CONNECTION_TIMEOUT)
            self.socket.setsockopt(zmq.SNDTIMEO, TransformersConfig.CONNECTION_TIMEOUT)
            self.socket.connect(TransformersConfig.FRONTEND_TCP_ADDRESS)
            yield self
        finally:
            self.cleanup()

    def send_and_receive(self, message: TaskReq) -> TaskResp:
        """Send request and receive response"""
        try:
            self.socket.send_json(message.model_dump_json())
            reply_json = self.socket.recv_json()
            resp = TaskResp.model_validate(json.loads(reply_json))
            if resp.worker_id==message.worker_id:
                return resp
            else:
                logger.debug("filtered invalid response due to worker_id mismatch, req_worker_id="
                               f"{message.worker_id}, resp_worker_id={resp.worker_id}")
        except zmq.Again:
            raise TimeoutError("Request timeout")
        except Exception as e:
            logger.error(f"Error in send_and_receive: {e}")
            raise

    def cleanup(self):
        """Clean up resources"""
        if self.socket:
            self.socket.close()
        if self.ctx:
            self.ctx.term()


class TransformersManager:
    """Manager for transformers workers and broker"""

    def __init__(self):
        self._broker_process = None
        self._worker_processes = {}
        self._worker_ready_status = {}  # 跟踪worker就绪状态
        self._lock = threading.Lock()

    def start_broker(self):
        """Start broker process"""
        with self._lock:
            if self._broker_process and self._broker_process.is_alive():
                logger.warning("Broker process already running")
                return

            try:
                context = multiprocessing.get_context("spawn")
                broker = ZMQBroker()
                self._broker_process = context.Process(
                    target=broker.start,
                    daemon=True,
                    name="transformers-broker"
                )
                self._broker_process.start()
                self._setup_signal_handlers()

                # Wait a bit for broker to start
                time.sleep(1)
                logger.info("Broker process started")

            except Exception as e:
                logger.error(f"Failed to start broker process: {e}")

    def start_worker(self, loader: TransformersLoader, timeout: int = 30):
        """Start worker process and wait for it to be ready"""
        with self._lock:
            if loader.model in self._worker_processes:
                process = self._worker_processes[loader.model]
                if process.is_alive():
                    logger.warning(f"Worker process for model {loader.model} already running")
                    return
                else:
                    # Clean up dead process
                    del self._worker_processes[loader.model]

            try:
                context = multiprocessing.get_context("spawn")
                worker = ZMQWorker(loader)
                process = context.Process(
                    target=worker.start,
                    daemon=True,
                    name=f"worker-{loader.model}"
                )
                process.start()
                self._worker_processes[loader.model] = process
                self._worker_ready_status[loader.model] = False

                logger.info(f"Worker process started for model {loader.model}, waiting for ready...")

                # 等待worker就绪
                if self._wait_for_worker_ready(loader.model, timeout):
                    self._worker_ready_status[loader.model] = True
                    time.sleep(1)  # 确保worker稳定
                    logger.info(f"Worker for model {loader.model} is ready")
                else:
                    # 如果worker没有在超时时间内就绪，清理进程
                    logger.error(f"Worker for model {loader.model} failed to become ready within {timeout} seconds")
                    self._cleanup_worker(loader.model)
                    raise RuntimeError(f"Worker for model {loader.model} failed to start process")

            except Exception as e:
                logger.error(f"Failed to start worker process for {loader.model}: {e}")
                if loader.model in self._worker_processes:
                    self._cleanup_worker(loader.model)
                raise

    def _wait_for_worker_ready(self, model: str, timeout: int) -> bool:
        """Wait for worker to become ready"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # 发送健康检查请求
                with ZMQClient().connect() as client:
                    health_req = TaskReq(worker_id=model, data={"type": "HEALTH_CHECK"})
                    response = client.send_and_receive(health_req)

                    if response.success and response.data.get("status") == "ready":
                        self._worker_ready_status[model] = True
                        logger.debug(f"Health check passed for worker {model}")
                        return True

            except Exception as e:
                logger.debug(f"Health check failed for {model}: {e}")

            time.sleep(1)  # 每秒检查一次

        return False

    def _cleanup_worker(self, model: str):
        """Clean up worker process"""
        if model in self._worker_processes:
            process = self._worker_processes[model]
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)

            if process.is_alive():
                process.kill()
                process.join(timeout=5)  # 确保清理，避免僵尸进程
            del self._worker_processes[model]

        if model in self._worker_ready_status:
            del self._worker_ready_status[model]

    def send_task(self, model: str, task_data: Dict[str, Any]) -> TaskResp:
        """Send task to specific model worker"""
        if model not in self._worker_processes:
            raise ValueError(f"Worker for model {model} not started")

        process = self._worker_processes[model]
        if not process.is_alive():
            raise RuntimeError(f"Worker process for model {model} is not running")

        # 检查worker是否就绪
        if not self._worker_ready_status.get(model, False):
            raise RuntimeError(f"Worker for model {model} is not ready yet")

        task_req = TaskReq(worker_id=model, data=task_data)

        with ZMQClient().connect() as client:
            return client.send_and_receive(task_req)

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""

        def stop_handler(signum, frame):
            logger.info("Manager stopping...")
            self.stop_all()
            sys.exit(0)

        for sig in [signal.SIGINT, signal.SIGTERM]:
            signal.signal(sig, stop_handler)

    def stop_all(self):
        """Stop all processes"""
        with self._lock:
            # Stop broker
            if self._broker_process and self._broker_process.is_alive():
                self._broker_process.terminate()
                self._broker_process.join(timeout=5)
                if self._broker_process.is_alive():
                    self._broker_process.kill()

            # Stop workers
            for model, process in self._worker_processes.items():
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)
                    if process.is_alive():
                        process.kill()

            self._worker_processes.clear()
            logger.info("All processes stopped")

    def is_worker_ready(self, model: str) -> bool:
        """Check if worker is ready"""
        return self._worker_ready_status.get(model, False)

    def get_worker_status(self) -> Dict[str, Dict[str, bool]]:
        """Get status of all workers"""
        with self._lock:
            return {
                model: {
                    "alive": process.is_alive(),
                    "ready": self._worker_ready_status.get(model, False)
                }
                for model, process in self._worker_processes.items()
            }
