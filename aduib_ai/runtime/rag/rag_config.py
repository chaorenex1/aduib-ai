from abc import ABC, abstractmethod


class SplitConfig(ABC):
    """Abstract base class for split configurations."""
    @abstractmethod
    def get_chunk_size(self):
        raise NotImplementedError

    @abstractmethod
    def get_chunk_overlap(self):
        raise NotImplementedError

class ParagraphSplitConfig(SplitConfig):
    """Configuration for splitting documents into paragraphs."""

    def __init__(self, chunk_size=500, chunk_overlap=100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def get_chunk_size(self):
        return self.chunk_size
    def get_chunk_overlap(self):
        return self.chunk_overlap

class QASplitConfig(SplitConfig):
    """Configuration for splitting documents for QA tasks."""
    def __init__(self, chunk_size=300, chunk_overlap=50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def get_chunk_size(self):
        return self.chunk_size
    def get_chunk_overlap(self):
        return self.chunk_overlap


class ParentChildSplitConfig(SplitConfig):
    """Configuration for hierarchical splitting of documents into parent and child chunks."""

    def __init__(self, parent_chunk_size=1000, parent_chunk_overlap=200, child_chunk_size=300, child_chunk_overlap=50):
        self.parent_chunk_size = parent_chunk_size
        self.parent_chunk_overlap = parent_chunk_overlap
        self.child_chunk_size = child_chunk_size
        self.child_chunk_overlap = child_chunk_overlap

    def get_chunk_size(self):
        return self.parent_chunk_size

    def get_chunk_overlap(self):
        return self.parent_chunk_overlap

    def get_child_chunk_size(self):
        return self.child_chunk_size

    def get_child_chunk_overlap(self):
        return self.child_chunk_overlap

