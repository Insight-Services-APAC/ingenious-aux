"""
Regression test for metadata preservation in the semantic chunker.

Purpose & Context:
------------------
This module provides a regression test for a critical bug (tracked as M5)
where the `SemanticOverlapChunker` would discard document metadata during the
splitting process. It ensures that when text is split with the `return_docs=True`
flag, the metadata from the original document is correctly propagated to all
resulting chunks.

This test is a vital part of the quality assurance for the `ingenious.chunk`
subsystem, which is a foundational component for document processing pipelines
used by various agents and data ingestion flows in the Insight Ingenious
architecture.

Key Algorithms & Design Choices:
--------------------------------
The primary challenge in testing the semantic chunker is its dependency on an
external embedding model (e.g., `OpenAIEmbeddings`), which requires network
access and API credentials. To create a hermetic and deterministic unit test,
this module employs a mocking strategy:
- The `unittest.mock.patch` decorator intercepts the instantiation of
  `OpenAIEmbeddings`.
- It replaces the real class with a `_fake_embedder` that returns constant,
  pre-defined vectors.
This approach isolates the chunking logic from the embedding model, allowing for
fast, reliable, and offline testing.
"""

from __future__ import annotations

from typing import List
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

from ingenious.chunk.config import ChunkConfig
from ingenious.chunk.factory import build_splitter


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _fake_embedder() -> MagicMock:
    """Creates a mock `OpenAIEmbeddings` object for isolated testing.

    Rationale:
        Using a real `OpenAIEmbeddings` instance requires network I/O and a
        valid `OPENAI_API_KEY`. This mock makes the test suite hermetic,
        faster, and independent of external services, which is a best
        practice for robust unit testing. It ensures that tests for the
        chunker logic are not affected by embedding model availability or
        performance.

    Returns:
        A `unittest.mock.MagicMock` instance configured to mimic the public
        surface of `langchain_community.embeddings.OpenAIEmbeddings` for the
        methods used by the semantic splitter.

    Implementation Notes:
        The mock implements `embed_documents` and `embed_query` to return
        deterministic, fixed-size zero vectors. This ensures the test's
        behavior is predictable and repeatable, focusing solely on the
        chunking logic rather than the semantic meaning of the text.
    """
    stub = MagicMock()
    stub.embed_documents.side_effect = lambda texts: [[0.0] * 8 for _ in texts]
    stub.embed_query.return_value = [0.0] * 8
    return stub


# --------------------------------------------------------------------------- #
# Test case                                                                   #
# --------------------------------------------------------------------------- #
@patch(
    "ingenious.chunk.strategy.langchain_semantic.OpenAIEmbeddings",
    return_value=_fake_embedder(),
)
def test_split_text_preserves_metadata(_patched_embed: MagicMock) -> None:
    """Verifies that the semantic chunker preserves document metadata.

    This test confirms that when `split_text` is called with the `metadata`
    and `return_docs=True` arguments, the provided metadata is attached
    unchanged to every `Document` object returned.

    Rationale:
        This is a regression test for issue M5, where the previous
        implementation failed to propagate metadata. This test acts as a
        contract, guaranteeing data integrity through the chunking pipeline
        and preventing future regressions. Losing metadata can break downstream
        processes that rely on source tracking or other contextual information.

    Args:
        _patched_embed: A `MagicMock` object injected by the `@patch` decorator.
            It replaces the real `OpenAIEmbeddings` class, ensuring the test
            runs without external dependencies. It is not used directly in the
            test body but is required for the patching mechanism to work.

    Raises:
        AssertionError: If any of the following conditions are not met:
            - The splitter produces at least one chunk.
            - All returned chunks are instances of `Document`.
            - The `metadata` attribute of every chunk is identical to the
              metadata object originally supplied.

    Implementation Notes:
        - The `type: ignore[assignment]` comment is necessary because the base
          `TextSplitter.split_text` method is typed to return `List[str]`.
          The `return_docs=True` argument changes the return type to
          `List[Document]`, a behavior that `mypy` cannot infer from the
          signature alone. This is a known pattern when working with certain
          LangChain components that use dynamic return types based on args.
    """
    cfg = ChunkConfig(strategy="semantic", chunk_size=32, chunk_overlap=8)
    splitter = build_splitter(cfg)

    meta = {"source": "unit-test", "page": 0}
    docs: List[Document] = splitter.split_text(  # type: ignore[assignment]
        "foo bar baz qux",
        metadata=meta,
        return_docs=True,
    )

    # -------- assertions ------------------------------------------------- #
    assert docs, "Expected at least one chunk to be produced"
    assert all(isinstance(d, Document) for d in docs), "Output must be Documents"
    assert all(d.metadata == meta for d in docs), "Metadata was not preserved"
