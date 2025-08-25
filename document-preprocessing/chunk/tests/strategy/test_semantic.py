"""
Purpose & Context
-----------------
This module contains unit tests for the "semantic" text splitting strategy,
which is a core component of the document processing pipeline within the Insight
Ingenious framework (`ingenious/chunk`). The semantic strategy aims to split
documents along sentence boundaries, grouping related sentences based on their
embedding similarity. These tests verify that the strategy's factory function
(`build_splitter`) correctly configures the underlying LangChain `SemanticChunker`
for different embedding providers (Public OpenAI vs. Azure) and that the custom
character-overlap logic is applied correctly after the initial semantic split.

Key Algorithms / Design Choices
-------------------------------
The tests rely heavily on `unittest.mock.patch` to isolate the code under test
from external dependencies and non-deterministic machine learning models:
1.  **Dependency Isolation**: We mock `OpenAIEmbeddings` and `AzureOpenAIEmbeddings`
    to prevent actual network calls. This makes the tests fast, repeatable, and
    executable without API keys. A `_fake_embedder` helper provides a
    deterministic stand-in.
2.  **Logic-Specific Testing**: To test the character overlap feature in isolation,
    the `test_semantic_overlap_applied` test patches the entire `SemanticChunker`
    class with a simple, deterministic `_DummySemanticChunker`. This allows us
    to verify the post-processing overlap logic without invoking the complex and
    "black-box" behaviour of the real semantic chunker.
"""

from typing import List
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

from ingenious.chunk.config import ChunkConfig
from ingenious.chunk.factory import build_splitter
from ingenious.chunk.utils.overlap import inject_overlap


# ---------------------------------------------------------------------------
# Common helpers
# ---------------------------------------------------------------------------
def _fake_embedder() -> MagicMock:
    """Creates a mock embedding object that simulates the `embed_documents` method.

    Rationale:
        This helper provides a fast, deterministic, and dependency-free substitute
        for a real `LangChain` embedding model during tests. It avoids the need for
        network calls, API keys, and the computational overhead of real embeddings,
        ensuring tests are stable and quick.

    Returns:
        MagicMock: A mock object configured to act like an embedder, returning
                   fixed-size zero vectors for any input text.
    """
    stub = MagicMock()
    stub.embed_documents.side_effect = lambda texts: [[0.0] * 1536 for _ in texts]
    return stub


# ---------------------------------------------------------------------------
# 1. Public OpenAI fallback
# ---------------------------------------------------------------------------
@patch("ingenious.chunk.strategy.langchain_semantic.OpenAIEmbeddings")
def test_semantic_openai_fallback(mock_openai: MagicMock):
    """Verifies that the splitter correctly uses the public OpenAI embedding model.

    Rationale:
        Ensures the default code path for semantic chunking, which relies on public
        OpenAI APIs, is correctly wired. This test confirms that when no Azure
        configuration is provided in `ChunkConfig`, the `OpenAIEmbeddings`
        class is instantiated and used by the splitter.

    Args:
        mock_openai (MagicMock): A patch of the `OpenAIEmbeddings` class,
                                 injected by the `@patch` decorator.
    """
    mock_openai.return_value = _fake_embedder()

    cfg = ChunkConfig(
        strategy="semantic",
        chunk_size=100,
        chunk_overlap=10,
        embed_model="fake-model",
    )
    splitter = build_splitter(cfg)

    chunks = splitter.split_text("Sentence 1. Sentence 2. Sentence 3.")
    assert mock_openai.return_value.embed_documents.called
    assert chunks  # Ensure some chunks were produced.


# ---------------------------------------------------------------------------
# 2. Azure path
# ---------------------------------------------------------------------------
@patch("ingenious.chunk.strategy.langchain_semantic.AzureOpenAIEmbeddings")
def test_semantic_azure_path(mock_azure: MagicMock):
    """Verifies that the splitter correctly uses the Azure OpenAI embedding model.

    Rationale:
        This test case validates the alternative, Azure-specific code path. When an
        `azure_openai_deployment` is specified in the `ChunkConfig`, the system
        must instantiate `AzureOpenAIEmbeddings` instead of the default public
        OpenAI version. This confirms the factory's conditional logic.

    Args:
        mock_azure (MagicMock): A patch of the `AzureOpenAIEmbeddings` class,
                                injected by the `@patch` decorator.
    """
    mock_azure.return_value = _fake_embedder()

    cfg = ChunkConfig(
        strategy="semantic",
        chunk_size=100,
        chunk_overlap=10,
        embed_model="fake-model",
        azure_openai_deployment="my-deployment",
    )
    splitter = build_splitter(cfg)

    chunks = splitter.split_text("Sentence 1. Sentence 2. Sentence 3.")
    assert mock_azure.return_value.embed_documents.called
    assert chunks  # Ensure some chunks were produced.


# ---------------------------------------------------------------------------
# 3. Overlap logic
# ---------------------------------------------------------------------------
# We patch `SemanticChunker` with a tiny, deterministic stub so we can
# predict the expected overlap result without invoking heavy ML code.
class _DummySemanticChunker:
    """A deterministic chunker that splits input into 4-character slices."""

    def __init__(self, *_, **__):
        pass

    def split_documents(self, docs: List[Document]) -> List[Document]:
        """Splits each document's content into fixed-size chunks of 4 chars.

        Args:
            docs (List[Document]): A list of documents to split.

        Returns:
            List[Document]: A list of new documents, each containing a 4-char chunk.
        """
        out = []
        for doc in docs:
            txt = doc.page_content
            for i in range(0, len(txt), 4):
                out.append(Document(page_content=txt[i : i + 4], metadata=doc.metadata))
        return out


@patch(
    "ingenious.chunk.strategy.langchain_semantic.SemanticChunker",
    new=_DummySemanticChunker,
)
@patch("ingenious.chunk.strategy.langchain_semantic.OpenAIEmbeddings")
def test_semantic_overlap_applied(mock_openai: MagicMock):
    """Validates that character-level overlap is correctly applied post-chunking.

    Rationale:
        The semantic chunking process involves two steps: first, the base
        `SemanticChunker` splits text, and second, our custom `inject_overlap`
        utility adds character overlap. This test isolates and verifies the second
        step. By replacing the real chunker with a simple, predictable dummy, we
        can guarantee the input to the overlap function and assert its output with
        perfect accuracy.

    Args:
        mock_openai (MagicMock): A patch for the embedder, required for the
                                 splitter build but not central to the test's logic.
    """
    mock_openai.return_value = _fake_embedder()

    cfg = ChunkConfig(strategy="semantic", chunk_size=4, chunk_overlap=2)
    splitter = build_splitter(cfg)

    text = "ABCDEFGHIJKLMNOP"
    actual = splitter.split_text(text)

    # Build the expected output by simulating the same two-step process:
    # 1. Create base chunks with the dummy chunker.
    # 2. Apply the shared overlap helper to those base chunks.
    base_chunks = _DummySemanticChunker().split_documents([Document(page_content=text)])
    expected_docs = inject_overlap(
        base_chunks, cfg.chunk_overlap, unit="tokens", enc_name=cfg.encoding_name
    )
    expected = [c.page_content for c in expected_docs]

    assert actual == expected
