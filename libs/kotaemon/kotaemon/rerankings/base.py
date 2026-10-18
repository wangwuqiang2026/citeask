from __future__ import annotations

from abc import abstractmethod

from kotaemon.base import BaseComponent, Document


class BaseReranking(BaseComponent):
    @abstractmethod
    def run(self, documents: list[Document], query: str) -> list[Document]:
        """Main method to transform list of documents
        (re-ranking, filtering, etc)"""
        ...

    def is_available(self) -> bool:
        """Whether this reranker can actually run (credentials, local model, ...).

        A reranker that is configured but cannot run used to be a silent no-op: the
        list came back unchanged while the UI said reranking was on. Callers use this
        to fall back instead (see ``kotaemon/rerankings/resolve.py``).
        """
        return True
