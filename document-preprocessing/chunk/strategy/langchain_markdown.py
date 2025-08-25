"""Provides a Markdown-aware text splitting strategy with bidirectional overlap.

Purpose & Context
-----------------
This module offers an advanced text splitting strategy named "markdown" for the Insight
Ingenious framework. It addresses a limitation in the standard LangChain
``MarkdownTextSplitter``, which only provides a simple, unidirectional,
character-based overlap. For sophisticated Retrieval-Augmented Generation (RAG)
pipelines, having context from both the preceding and succeeding chunks is vital for
semantic understanding and accurate retrieval.

This implementation enhances the base splitter by injecting a **bidirectional** overlap,
which can be measured in either **tokens** or **characters**, as configured in the
system's ``ChunkConfig``.

Key Algorithms & Design Choices
-------------------------------
1.  **Wrapper Pattern**: Instead of subclassing, this module uses the Wrapper
    Pattern via the ``MarkdownOverlapWrapper`` class. This design choice
    decouples our logic from LangChain's implementation, making the system more
    resilient to upstream changes in the ``langchain-text-splitters`` library.
2.  **Delegation & Single Responsibility**: The core Markdown parsing is delegated
    to the wrapped LangChain object. The bidirectional overlap logic is further
    delegated to the ``ingenious.chunk.utils.overlap.inject_overlap`` utility.
    This promotes code reuse and separates concerns.
3.  **Attribute Forwarding**: The ``__getattr__`` method provides transparent
    access to the underlying ``MarkdownTextSplitter``'s attributes and methods,
    making the wrapper a near-perfect proxy. It includes safety checks to return
    copies of mutable collections, preventing unintended side effects.
4.  **Explicit Overlap Control**: The factory function explicitly initializes the
    base splitter with ``chunk_overlap=0``. This is critical because the custom
    bidirectional overlap is handled entirely by this module, preventing
    conflicting or duplicated overlap logic.

Dev-Guide Compliance Notes
--------------------------
-   **Configuration**: The strategy is configured via the central ``ChunkConfig``
    object, aligning with DI-101's configuration management guidelines.
-   **Extensibility**: The factory function is registered with the ``@register``
    decorator, fitting the project's extensible, factory-based architecture for
    core components like chunkers.
-   **Type Safety**: All public APIs are fully type-hinted, adhering to the
    project's Python 3.10+ baseline.
-   **Formatting**: The code is formatted to be compliant with ``black`` (88-char
    lines) and ``Ruff``.

Usage Example
-------------
The splitter is typically constructed and used via the central factory.

.. code-block:: python

    from ingenious.chunk.config import ChunkConfig
    from ingenious.chunk.factory import build_splitter

    # 1. Define configuration for chunking.
    markdown_config = ChunkConfig(
        strategy="markdown",
        chunk_size=100,
        chunk_overlap=15,
        overlap_unit="tokens",
        encoding_name="cl100k_base",
    )

    # 2. Build the splitter using the project's factory.
    splitter = build_splitter(markdown_config)

    # 3. Use the splitter on a Markdown document.
    markdown_text = (
        "# Project Gemini\\n\\nGemini is a multimodal AI.\\n\\n"
        "## Key Features\\n\\n- Long context window\\n- Multimodality"
    )
    chunks = splitter.split_text(markdown_text)
    for i, chunk in enumerate(chunks):
        print(f"--- Chunk {i+1} ---\\n{chunk}\\n")

"""

from __future__ import annotations

import copy
from types import MappingProxyType
from typing import Any, Dict, Iterable, List

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownTextSplitter, TextSplitter

from ingenious.chunk.utils.overlap import inject_overlap

from ..config import ChunkConfig
from . import register


class MarkdownOverlapWrapper(TextSplitter):
    """Wraps a LangChain MarkdownTextSplitter to inject bidirectional overlap.

    Rationale:
        This wrapper approach avoids subclassing ``MarkdownTextSplitter``, making the
        integration more robust against upstream changes in LangChain. It delegates
        the core splitting to LangChain and the overlap logic to a dedicated utility,
        adhering to the Single Responsibility Principle. The ``__getattr__``
        implementation ensures the wrapper is transparent for most use cases,
        behaving like the object it wraps.
    """

    def __init__(
        self,
        base: MarkdownTextSplitter,
        overlap_size: int,
        enc: str,
        unit: str = "tokens",
    ):
        """Initializes the wrapper with a base splitter and overlap settings.

        Args:
            base: The underlying (character-bounded) splitter from LangChain. It
                should be initialized with ``chunk_overlap=0``.
            overlap_size: The size of the overlap window to inject between chunks.
            enc: The ``tiktoken`` encoding name (e.g., 'cl100k_base'). This is
                only used when ``unit`` is "tokens".
            unit: The unit for measuring overlap, either "tokens" or "characters".
        """
        self._base = base
        self._overlap_size = overlap_size
        self._enc = enc
        self._unit = unit

    def split_text(self, text: str) -> List[str]:
        """Splits text into Markdown-aware chunks and adds bidirectional overlap.

        Rationale:
            This method orchestrates the two-step splitting process. It first
            leverages LangChain's battle-tested Markdown parser for the initial
            structural split, then applies the custom Insight Ingenious overlap
            logic for consistent, context-aware chunking.

        Args:
            text: The text content to be split.

        Returns:
            A list of strings, where each string is a chunk with bidirectional
            overlap applied.

        Implementation Notes:
            The process is:
            1. Call the base splitter to get raw chunks based on Markdown structure
               and character length.
            2. Pass these raw chunks to ``inject_overlap`` to add the contextual
               windows.
            Complexity is approximately linear, O(N), where N is the length of the
            input text.
        """
        raw_chunks = self._base.split_text(text)
        if self._overlap_size == 0:
            return raw_chunks
        return inject_overlap(
            raw_chunks, self._overlap_size, unit=self._unit, enc_name=self._enc
        )

    def split_documents(self, documents: Iterable[Document]) -> List[Document]:
        """Splits multiple documents and injects overlap into each.

        Rationale:
            Provides a consistent API with the underlying LangChain splitter for
            processing multiple documents at once. The overlap logic is applied
            independently to the chunks derived from each document.

        Args:
            documents: An iterable of LangChain ``Document`` objects.

        Returns:
            A list of ``Document`` objects, representing the new, smaller chunks
            with overlap applied. Metadata is preserved from the original documents.

        Implementation Notes:
            LangChain's ``split_documents`` handles splitting and metadata
            propagation. Our ``inject_overlap`` utility is then applied to the
            ``page_content`` of the resulting chunks. The logic does not currently
            add overlap *between* documents.
        """
        # We cannot simply call the base method and then inject overlap on the
        # result, as `inject_overlap` works on strings, not Documents. We must
        # reimplement the loop to apply it correctly.
        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        return self._split_text_with_metadata(texts, metadatas)

    def _split_text_with_metadata(
        self, texts: List[str], metadatas: List[Dict[str, Any]]
    ) -> List[Document]:
        """Helper to split texts and re-associate metadata."""
        doc_chunks = []
        for i, text in enumerate(texts):
            # Split the text of a single document
            chunks = self.split_text(text)
            for chunk in chunks:
                # Create a new Document for each chunk with original metadata
                metadata = copy.deepcopy(metadatas[i])
                doc_chunks.append(Document(page_content=chunk, metadata=metadata))
        return doc_chunks

    def __getattr__(self, name: str) -> Any:
        """Forwards attribute access to the wrapped LangChain splitter.

        Rationale:
            This makes the wrapper a transparent proxy, allowing callers to access
            methods or properties of the base splitter (e.g., ``chunk_size``)
            without needing to know about the wrapper's existence. It includes
            safety measures to prevent mutable state from being modified by reference.

        Args:
            name: The name of the attribute to access.

        Returns:
            The attribute from the underlying ``_base`` splitter instance.

        Raises:
            AttributeError: If the attribute name starts with an underscore or
                does not exist on the base object.

        Implementation Notes:
            - Private attributes (starting with '_') are not forwarded.
            - Immutable types are returned directly for performance.
            - Mutable collections (``list``, ``dict``, ``set``) are returned as
              deep copies or immutable proxies to prevent side effects.
        """
        if name.startswith("_"):
            raise AttributeError(
                f"Private attribute '{name}' cannot be accessed via forwarding."
            )

        attr = getattr(self._base, name)

        # For callable methods, return them directly.
        if callable(attr):
            return attr

        # For simple, immutable types, return them directly.
        if isinstance(attr, (str, int, float, bool, type(None))):
            return attr

        # For dicts, return an immutable proxy.
        if isinstance(attr, dict):
            return MappingProxyType(attr)

        # For other common mutable collections, return a deep copy.
        if isinstance(attr, (list, set, bytearray)):
            return copy.deepcopy(attr)

        # For any other types, return the attribute as-is.
        return attr


@register("markdown")
def create(cfg: ChunkConfig) -> TextSplitter:
    """Builds a Markdown splitter that respects custom overlap settings.

    Rationale:
        This factory is registered with the name 'markdown', allowing the chunking
        system to dynamically construct this specific splitter based on
        configuration. This decouples client code from the concrete implementation,
        adhering to the factory pattern prescribed by the project architecture.

    Args:
        cfg: The centralized configuration object specifying ``chunk_size``,
            ``chunk_overlap``, ``overlap_unit``, and ``encoding_name``.

    Returns:
        A fully configured ``MarkdownOverlapWrapper`` instance ready for use.

    Implementation Notes:
        Crucially, this factory initializes the base ``MarkdownTextSplitter`` with
        ``chunk_overlap=0``. The overlap is handled entirely by the wrapper and the
        ``inject_overlap`` utility, preventing incorrect or duplicated overlap.
    """
    base_splitter = MarkdownTextSplitter(chunk_size=cfg.chunk_size, chunk_overlap=0)
    return MarkdownOverlapWrapper(
        base=base_splitter,
        overlap_size=cfg.chunk_overlap,
        enc=cfg.encoding_name,
        unit=cfg.overlap_unit,
    )
