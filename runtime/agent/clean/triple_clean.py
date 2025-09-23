import hashlib
from typing import List, Tuple, Set

import spacy


class TripleCleaner:
    """三元组清洗工具：大小写归一化、词形还原、实体对齐、去重"""

    def __init__(self, doc_lang: str = "en"):
        if doc_lang != "en":
            self.nlp = spacy.load(f"{doc_lang}_core_web_lg")
        else:
            self.nlp = spacy.load("en_core_web_sm")
        self.seen: Set[str] = set()  # 存储已见三元组哈希

    def _normalize_text(self, text: str) -> str:
        """小写 + 词形还原"""
        doc = self.nlp(text.lower().strip())
        return " ".join([token.lemma_ for token in doc])

    def _hash_triple(self, head: str, relation: str, tail: str) -> str:
        raw = f"{head}|{relation}|{tail}"
        return hashlib.md5(raw.encode()).hexdigest()

    def clean_triple(self, head: str, relation: str, tail: str) -> Tuple[str, str, str]:
        """清洗单个三元组"""
        head = self._normalize_text(head)
        relation = self._normalize_text(relation)
        tail = self._normalize_text(tail)
        return head, relation, tail

    def deduplicate(self, triples: List[Tuple[str, str, str]]) -> List[Tuple[str, str, str]]:
        """清洗 + 去重"""
        cleaned = []
        for h, r, t in triples:
            h, r, t = self.clean_triple(h, r, t)
            triple_id = self._hash_triple(h, r, t)
            if triple_id not in self.seen:
                self.seen.add(triple_id)
                cleaned.append((h, r, t))
        return cleaned
