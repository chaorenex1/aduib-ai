import re
from typing import cast, Optional

from jieba3 import jieba3

from runtime.rag.keyword.stopwords import STOPWORDS


class JiebaKeyword:
    def __init__(self):
        # import jieba.analyse  # type: ignore
        #
        # jieba3.analyse.default_tfidf.stop_words = STOPWORDS  # type: ignore
        self.jieba3=jieba3()

    def extract_keywords(self, text: str, max_keywords_per_chunk: Optional[int] = 10) -> set[str]:
        """Extract keywords with JIEBA tfidf."""
        # import jieba.analyse  # type: ignore

        keywords = self.jieba3.cut_text(text)  # type: ignore
        # jieba.analyse.extract_tags returns list[Any] when withFlag is False by default.
        keywords = cast(list[str], keywords)

        return set(self._expand_tokens_with_subtokens(set(keywords)))

    def _expand_tokens_with_subtokens(self, tokens: set[str]) -> set[str]:
        """Get subtokens from a list of tokens., filtering for stopwords."""

        results = set()
        for token in tokens:
            results.add(token)
            sub_tokens = re.findall(r"\w+", token)
            if len(sub_tokens) > 1:
                results.update({w for w in sub_tokens if w not in list(STOPWORDS)})

        return results
