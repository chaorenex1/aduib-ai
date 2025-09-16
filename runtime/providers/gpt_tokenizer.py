import logging
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

_tokenizer: Any = None
_lock = Lock()

class GPTTokenizer:
    """
    Singleton class to manage the GPT tokenizer.
    """

    @staticmethod
    def get_tokenizer(model_name: str = "gpt-4", encoding_name: str = "cl100k_base") -> Any:
        global _tokenizer, _lock
        if _tokenizer is None:
            with _lock:
                if _tokenizer is None:  # Double-checked locking
                    try:
                        import tiktoken
                    except ImportError:
                        logger.error(
                            "tiktoken package is not installed. "
                            "Please install it with `pip install tiktoken`."
                        )
                        raise ImportError(
                            "Could not import tiktoken python package. "
                            "This is needed in order to calculate max_tokens_for_prompt. "
                            "Please install it with `pip install tiktoken`."
                        )

                    if model_name is not None:
                        _tokenizer = tiktoken.encoding_for_model(model_name)
                    else:
                        _tokenizer = tiktoken.get_encoding(encoding_name)
        return _tokenizer

    @staticmethod
    def get_token_nums(text: str) -> int:
        """
        Get the number of tokens in the given text.

        :param text: The text to tokenize.
        :return: The number of tokens in the text.
        """
        tokenizer = GPTTokenizer.get_tokenizer()
        return len(tokenizer.encode(text, allowed_special="all"))


    @staticmethod
    def get_encoder() -> Any:
        """
        Get the tokenizer encoder.

        :return: The tokenizer encoder.
        """
        return _tokenizer