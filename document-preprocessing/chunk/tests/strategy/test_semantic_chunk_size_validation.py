"""
Unit tests for semantic document chunking configuration and logic.

Purpose & Context:
    This module provides unit tests for the semantic chunking strategy within the
    Insight Ingenious framework, located under `ingenious.chunk`. Its primary
    purpose is to verify that the configuration model (`ChunkConfig`) correctly
    validates its parameters and that the `build_splitter` factory can
    successfully instantiate and use the semantic chunker with valid settings.

    These tests are critical for the data ingestion pipeline, ensuring that documents
    are processed reliably before being passed to retrieval-augmented generation (RAG)
    agents.

Key Algorithms / Design Choices:
    - **Mocking**: The tests use `unittest.mock.patch` to replace the actual
      embedding model dependency (`_select_embeddings`) with a mock (`_fake_embedder`).
      This isolates the chunking logic from external services, making tests fast,
      deterministic, and free of network I/O or API costs.
    - **Configuration Validation**: The tests explicitly target `pydantic.ValidationError`
      to confirm that the `ChunkConfig` data model enforces its constraints (e.g.,
      percentile range). This "fail-fast" approach prevents invalid states from
      propagating through the system.
    - **Focused Assertions**: Tests use `pytest.raises` with a `match` argument to
      ensure not only that the correct exception is raised but also that it
      provides a user-friendly error message.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from ingenious.chunk.config import ChunkConfig
from ingenious.chunk.factory import build_splitter


def _fake_embedder() -> MagicMock:
    """Creates a mock embedding model to prevent real network calls.

    Rationale:
        Using a real embedding model would make tests slow, non-deterministic,
        and dependent on external APIs. This mock provides a simple, fast, and
        predictable substitute for validating the chunking logic.

    Returns:
        MagicMock: A mock object configured to simulate the `embed_documents`
            method of a LangChain embedder.

    Implementation Notes:
        The mock's `side_effect` dynamically generates a list of embeddings
        (lists of floats) that matches the number of input documents. The
        embedding content `[0.0] * 8` is arbitrary and sufficient for testing
        the splitter's structural behavior.
    """
    stub = MagicMock()
    # Return a list of lists (embeddings) matching the number of input texts.
    stub.embed_documents.side_effect = lambda texts: [[0.0] * 8 for _ in texts]
    return stub


def test_semantic_chunker_fails_with_invalid_percentile() -> None:
    """Verifies `ChunkConfig` raises `ValidationError` for an invalid percentile."""
    # Rationale:
    #   This test ensures the configuration model's validation rules are active,
    #   preventing downstream errors by rejecting invalid setup values at the
    #   earliest possible moment ("fail-fast" principle).
    with pytest.raises(
        ValidationError, match="Input should be less than or equal to 100"
    ):
        ChunkConfig(
            strategy="semantic",
            semantic_threshold_percentile=101,  # Invalid percentile > 100
        )


@patch(
    "ingenious.chunk.strategy.langchain_semantic._select_embeddings",
    return_value=_fake_embedder(),
)
def test_semantic_chunker_succeeds_with_valid_percentile(
    mock_select_embeddings: MagicMock,
) -> None:
    """Verifies the semantic chunker runs correctly with a valid percentile.

    Rationale:
        This is a "happy path" test to confirm that, with a valid configuration
        and a mocked embedding model, the semantic splitter can be successfully
        instantiated and used to split text without raising exceptions.

    Args:
        mock_select_embeddings (MagicMock): An object injected by `@patch` to
            replace the actual embedding model selection logic.

    Raises:
        pytest.fail: If `ChunkConfig` validation or splitter execution fails
            unexpectedly with a valid configuration.
    """
    try:
        cfg = ChunkConfig(
            strategy="semantic",
            semantic_threshold_percentile=95,  # Valid percentile
        )
        splitter = build_splitter(cfg)
        assert splitter is not None, "build_splitter should return a valid splitter"

        # Ensure the splitting process itself does not raise an error.
        splitter.split_text("This is the first sentence. This is the second sentence.")
    except ValidationError as e:
        pytest.fail(f"Initialization or splitting failed with a valid percentile: {e}")
