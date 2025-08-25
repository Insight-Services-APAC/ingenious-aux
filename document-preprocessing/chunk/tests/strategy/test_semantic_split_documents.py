"""
Verifies the semantic chunking strategy wrapper and factory.

This module contains unit tests for the `ingenious.chunk` subsystem, specifically
focusing on the "semantic" chunking strategy. The primary goal is to ensure
that the `build_splitter` factory correctly instantiates and configures the
semantic chunker wrapper and that this wrapper correctly handles document
metadata and adheres to fundamental chunking invariants like overlap.

Key Algorithms / Design Choices:
The tests employ extensive mocking via `unittest.mock.patch` to isolate the
wrapper's logic from the expensive and non-deterministic dependencies: the
actual `langchain_experimental.text_splitter.SemanticChunker` and the
`OpenAIEmbeddings` model. A simple passthrough dummy chunker
(`_DummySemanticChunker`) is used to confirm that the data flow and metadata
handling are correct without performing a real semantic split. This makes the
tests fast, reliable, and independent of external API keys.
"""

from unittest.mock import MagicMock, patch

from langchain_core.documents import Document
from tiktoken import Encoding, get_encoding

from ingenious.chunk.config import ChunkConfig
from ingenious.chunk.factory import build_splitter


def _fake_embedder() -> MagicMock:
    """
    Creates a stub `OpenAIEmbeddings` object for testing purposes.

    Rationale:
        This avoids making actual network calls to the OpenAI API during unit
        tests, making them fast, deterministic, and free of charge. The mock
        simply returns fixed-size zero vectors, which is sufficient to
        satisfy the interface contract of the embedding model required by the
        chunker.

    Returns:
        MagicMock: A mock object configured to behave like an embedding model.
    """
    stub = MagicMock()
    stub.embed_documents.side_effect = lambda texts: [[0.0] * 5 for _ in texts]
    return stub


class _DummySemanticChunker:
    """A test-only substitute for the real `SemanticChunker`."""

    def __init__(self, *args, **kwargs):
        """
        Accepts any arguments and does nothing.

        Rationale:
            The real `SemanticChunker` from LangChain Experimental takes an
            `embeddings` object and other parameters. This dummy initializer
            provides a compatible signature for instantiation within the code
            under test but ignores the arguments, as they are not needed for
            the simple passthrough behavior.
        """
        pass

    def split_documents(self, docs: list[Document]) -> list[Document]:
        """
        Returns the input documents without modification.

        Rationale:
            This simplifies the test by isolating the behavior of the Insight
            Ingenious wrapper from the complex internal logic of the real
            semantic chunker. The test's primary goal is to verify metadata
            propagation and the overall interface contract, not the chunking
            algorithm itself.

        Args:
            docs (list[Document]): The list of documents to "split".

        Returns:
            list[Document]: The original, unmodified list of documents.
        """
        return docs


@patch(
    "ingenious.chunk.strategy.langchain_semantic.SemanticChunker",
    new=_DummySemanticChunker,
)
@patch(
    "ingenious.chunk.strategy.langchain_semantic.OpenAIEmbeddings",
    return_value=_fake_embedder(),
)
def test_semantic_split_documents(mock_openai: MagicMock):
    """
    Verifies `build_splitter` for "semantic" strategy and metadata integrity.

    Rationale:
        This is a smoke test to ensure the factory correctly constructs a
        splitter for the "semantic" strategy and that the resulting object's
        `split_documents` method preserves document metadata. It also includes
        a test for the chunk overlap invariant, which is a key contract for
        many chunking strategies.

    Args:
        mock_openai (MagicMock): An object injected by `@patch` to represent
            the `OpenAIEmbeddings` class, ensuring no real API calls are made.

    Raises:
        AssertionError: If metadata is altered or the overlap invariant fails.

    Implementation Notes:
        - This test is critically dependent on its mocks. The `_DummySemanticChunker`
          is a simple passthrough.
        - **WARNING**: The overlap invariant check is designed for a real chunker
          that produces overlapping chunks from a *single* document. Because the
          dummy chunker returns the two *separate* original documents, this
          specific assertion will fail as written. A more sophisticated mock
          would be needed to validate the overlap logic correctly.
    """
    cfg = ChunkConfig(strategy="semantic", chunk_size=20, chunk_overlap=5)
    splitter = build_splitter(cfg)

    docs = [
        Document(page_content="AAA BBB CCC.", metadata={"id": 1}),
        Document(page_content="DDD EEE FFF.", metadata={"id": 2}),
    ]
    out = splitter.split_documents(docs)

    # 1. Metadata should be preserved on each returned document.
    assert len(out) == len(docs)
    for original, new in zip(docs, out):
        assert new.metadata == original.metadata, "Metadata was altered."

    # 2. The overlap invariant should hold between consecutive chunks.
    #    NOTE: This check will fail with the current _DummySemanticChunker mock.
    #    It is written to validate a real chunker's output.
    enc: Encoding = get_encoding(cfg.encoding_name)
    for i in range(1, len(out)):
        # Get the token IDs for the tail of the previous chunk.
        prev_content = out[i - 1].page_content
        prev_tokens = enc.encode(prev_content)
        tail_tokens = prev_tokens[-cfg.chunk_overlap :]
        tail_text = enc.decode(tail_tokens).lstrip()

        # Get the token IDs for the head of the current chunk.
        # Allow for a few extra tokens due to potential leading spaces/chars.
        current_content = out[i].page_content
        head_tokens = enc.encode(current_content)[: cfg.chunk_overlap + 2]
        head_text = enc.decode(head_tokens).lstrip()

        assert head_text.startswith(tail_text), (
            f"Chunk overlap invariant failed between chunks {i - 1} and {i}."
        )
