"""Provides a highly configurable recursive text splitting strategy.

Purpose & Context
-----------------
This module implements the "recursive" chunking strategy, a versatile workhorse for
the Insight Ingenious framework. It is designed to split text by a hierarchical list
of separators (e.g., paragraphs, then sentences) while enforcing a strict size
budget for each chunk.

Its key innovation is the ability to enforce this budget in one of two units,
selected via ``ChunkConfig.overlap_unit``:
1.  **"tokens"**: Chunks are sized based on LLM tokens, which is ideal for precise
    context management and cost control.
2.  **"characters"**: Chunks are sized by character count, falling back to a more
    traditional and faster method.

This component is a core strategy located in ``ingenious/chunk/strategy/`` and is
instantiated via the central ``ingenious.chunk.factory.build_splitter``.

Key Algorithms & Design Choices
-------------------------------
-   **Dual-Path Implementation**: The ``create`` factory uses a conditional design.
    -   For **character-based** splitting, it leverages LangChain's robust
        ``RecursiveCharacterTextSplitter`` and wraps it with our internal
        ``_OverlapWrapper``. This reuses battle-tested code for a common use case.
    -   For **token-based** splitting, it uses the custom ``RecursiveTokenSplitter``.
        A custom class was necessary as no standard splitter enforces a strict
        token budget. Its algorithm accumulates text by paragraphs and performs a
        greedy slice on any single paragraph that exceeds the token budget.
-   **Consistent Overlap**: Both implementation paths use the shared utility
    ``ingenious.chunk.utils.overlap.inject_overlap`` to apply a bidirectional
    overlap. This ensures that overlap behavior is identical across all chunking
    strategies in the framework, regardless of the underlying splitting logic.

Usage Example
-------------
.. code-block:: python

    from ingenious.chunk.config import ChunkConfig
    from ingenious.chunk.factory import build_splitter

    # --- Token-based splitting (for LLM precision) ---
    token_config = ChunkConfig(
        strategy="recursive",
        chunk_size=100,
        chunk_overlap=20,
        overlap_unit="tokens",
    )
    token_splitter = build_splitter(token_config)
    chunks = token_splitter.split_text("Your long document text...")

    # --- Character-based splitting (for speed) ---
    char_config = ChunkConfig(
        strategy="recursive",
        chunk_size=500,
        chunk_overlap=50,
        overlap_unit="characters",
    )
    char_splitter = build_splitter(char_config)
    chunks = char_splitter.split_text("Your long document text...")

"""

from __future__ import annotations

import copy
from types import MappingProxyType
from typing import Any, Callable, Iterable, List, Optional

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter, TextSplitter

from ingenious.chunk.utils.overlap import inject_overlap
from ingenious.chunk.utils.token_len import token_len

from ..config import ChunkConfig
from . import register

__all__: list[str] = ["create"]


class _OverlapWrapper(TextSplitter):
    """A private helper that wraps a splitter to inject bidirectional overlap.

    Rationale:
        This wrapper allows the reuse of a standard LangChain splitter while applying
        the Insight Ingenious framework's custom, consistent overlap logic. This
        promotes code reuse and separates the concern of splitting from the concern
        of adding contextual overlap. It is used by the 'recursive' factory for the
        character-based splitting path.
    """

    def __init__(
        self,
        base: RecursiveCharacterTextSplitter,
        overlap_size: int,
        enc: str,
        unit: str = "tokens",
    ):
        """Initializes the wrapper.

        Args:
            base: The underlying LangChain splitter instance.
            k: The size of the overlap window.
            enc: The ``tiktoken`` encoding name, required by ``inject_overlap``.
            unit: The unit of overlap ("tokens" or "characters").
        """
        self._base = base
        self._overlap_size = overlap_size
        self._enc = enc
        self._unit = unit

    def split_text(self, text: str) -> list[str]:
        """Splits text using the base splitter, then injects overlap."""
        raw_chunks = self._base.split_text(text)
        if self._overlap_size == 0:
            return raw_chunks
        return inject_overlap(
            raw_chunks, self._overlap_size, unit=self._unit, enc_name=self._enc
        )

    def split_documents(self, documents: Iterable[Document]) -> List[Document]:
        """Splits documents using the base splitter, then injects overlap."""
        # This logic cannot be a simple wrapper as in `split_text` because
        # `inject_overlap` operates on string content, not Document objects.
        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        doc_chunks = []
        for i, text in enumerate(texts):
            chunks = self.split_text(text)
            for chunk in chunks:
                metadata = copy.deepcopy(metadatas[i])
                doc_chunks.append(Document(page_content=chunk, metadata=metadata))
        return doc_chunks

    def __getattr__(self, name: str) -> Any:
        """Forwards attribute access to the wrapped LangChain splitter."""
        if name.startswith("_"):
            raise AttributeError(
                f"Private attribute '{name}' cannot be accessed via forwarding."
            )

        attr = getattr(self._base, name)
        if callable(attr):
            return attr
        if isinstance(attr, (str, int, float, bool, type(None))):
            return attr
        if isinstance(attr, dict):
            return MappingProxyType(attr)
        if isinstance(attr, (list, set, bytearray)):
            return copy.deepcopy(attr)
        return attr


class RecursiveTokenSplitter(RecursiveCharacterTextSplitter):
    """Recursively splits text while enforcing a strict token-based size budget.

    Rationale:
        Standard recursive splitters are character-based. For LLM applications,
        managing context windows based on tokens is more precise and cost-effective.
        This class provides that capability by reimplementing the splitting logic
        to use a token-counting function for all size measurements.
    """

    def __init__(
        self,
        encoding_name: str,
        chunk_size: int,
        chunk_overlap: int,
        overlap_unit: str = "tokens",
        separators: Optional[list[str]] = None,
    ):
        """Initializes the token-aware recursive splitter.

        Args:
            encoding_name: The name of the ``tiktoken`` encoding to use.
            chunk_size: The maximum size of a chunk in the specified ``unit``.
            chunk_overlap: The size of the overlap between chunks.
            overlap_unit: The unit for all measurements ("tokens" or "characters").
            separators: An ordered list of strings to split on. Defaults to
                common text separators.
        """
        super().__init__(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self._encoding_name = encoding_name
        self._separators = separators or ["\n\n", "\n", " ", ""]
        self._overlap_unit = overlap_unit

        # Select the measurement function based on the chosen unit.
        if self._overlap_unit == "characters":
            self._measure: Callable[[str], int] = len
        else:  # "tokens" (default)
            self._measure = lambda s: token_len(s, self._encoding_name)

    def split_text(self, text: str) -> List[str]:
        """Splits text into chunks respecting a token or character budget.

        Implementation Notes:
            The algorithm iterates through paragraphs (or other top-level
            separators) and accumulates them into a buffer. If adding a new
            paragraph would exceed the chunk size, the buffer is flushed as a
            new chunk. If a single paragraph is itself over budget, it is
            greedily sliced into fitting sub-chunks. This ensures no single
            chunk exceeds the configured ``chunk_size``. The bidirectional overlap
            is injected in a final pass.
        """
        chunks: list[str] = []
        buffer = ""
        # We only use the highest-priority separator for the initial split.
        # Finer-grained splitting is not yet implemented in this custom path.
        primary_separator = self._separators[0]

        for paragraph in text.split(primary_separator):
            prospective_buffer = f"{buffer}{paragraph}{primary_separator}"
            if self._measure(prospective_buffer) > self._chunk_size:
                if buffer:  # Flush the buffer if it contains content
                    chunks.append(buffer)

                # If the new paragraph alone is too large, slice it greedily.
                if self._measure(paragraph) > self._chunk_size:
                    start_idx = 0
                    while start_idx < len(paragraph):
                        window = paragraph[start_idx:]
                        # Shrink window from the end until it fits the budget.
                        while self._measure(window) > self._chunk_size:
                            window = window[:-1]
                        chunks.append(f"{window}{primary_separator}")
                        start_idx += len(window)
                    buffer = ""  # The oversized paragraph has been fully processed.
                else:
                    # Start a new buffer with the current paragraph.
                    buffer = f"{paragraph}{primary_separator}"
            else:
                # Add the paragraph to the current buffer.
                buffer = prospective_buffer

        if buffer:
            chunks.append(buffer)

        if self._chunk_overlap == 0:
            return chunks

        # Inject bidirectional overlap using the user-selected unit.
        return inject_overlap(
            chunks,
            self._chunk_overlap,
            unit=self._overlap_unit,
            enc_name=self._encoding_name,
        )


@register("recursive")
def create(cfg: ChunkConfig) -> TextSplitter:
    """Factory for the 'recursive' splitter, choosing an implementation by unit.

    Rationale:
        This factory abstracts the underlying implementation from the caller. Based
        on ``overlap_unit``, it intelligently selects the optimal splitter:
        LangChain's robust implementation for character-based units or our custom,
        token-aware implementation for token-based units.

    Args:
        cfg: The centralized configuration object.

    Returns:
        A configured splitter instance ready for use.
    """
    # For character budgets, use LangChain's robust word-aware splitter and
    # wrap it to add our standard bidirectional overlap.
    if cfg.overlap_unit == "characters":
        base = RecursiveCharacterTextSplitter(
            chunk_size=cfg.chunk_size,
            chunk_overlap=0,  # Overlap is handled by our wrapper.
            separators=cfg.separators or ["\n\n", "\n", " ", ""],
        )
        return _OverlapWrapper(
            base,
            cfg.chunk_overlap,
            cfg.encoding_name,
            unit="characters",
        )

    # For token budgets, fall back to our custom strict token splitter.
    return RecursiveTokenSplitter(
        encoding_name=cfg.encoding_name,
        chunk_size=cfg.chunk_size,
        chunk_overlap=cfg.chunk_overlap,
        overlap_unit="tokens",
        separators=cfg.separators,
    )
