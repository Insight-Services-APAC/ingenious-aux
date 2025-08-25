"""
Tests configuration validation for the semantic chunking strategy.

Purpose & context:
    This module tests the warning mechanisms within the `ChunkConfig` data class,
    specifically for the "semantic" chunking strategy. It ensures that the system
    provides clear, actionable warnings to the user when a configuration might
    lead to unintended behavior (e.g., using a public API endpoint by default).
    This test is part of the `ingenious/chunk` subsystem's test suite and is
    crucial for maintaining robust and transparent configuration handling.

Key algorithms / design choices:
    The test uses the `pytest.warns` context manager, which is the idiomatic
    approach for asserting that a specific warning is emitted. By using the
    `match` parameter with a regular expression, the test verifies the essence
    of the warning message without being brittle to minor wording changes.
"""

import pytest

from ingenious.chunk.config import ChunkConfig


def test_semantic_emits_fallback_warning() -> None:
    """Verifies `ChunkConfig` warns when falling back to a public endpoint.

    Rationale:
        This test is critical for user safety and operational transparency. The
        semantic chunking strategy requires an embedding model. If one is not
        explicitly provided via `embed_model_name` or an Azure configuration,
        the system falls back to a public OpenAI endpoint. This could lead to
        unexpected costs or data handling. This test ensures the user is
        explicitly warned about this fallback, preventing silent, unintended
        API usage, which is a core design principle of the Insight Ingenious
        framework.

    Args:
        None

    Returns:
        None

    Raises:
        pytest.fail: If the `ChunkConfig` constructor does not raise the
            expected `UserWarning` under the specified test conditions.

    Implementation notes:
        - The `pytest.warns` context manager captures and verifies the warning.
        - The `match` parameter uses a regular expression to make the test
          robust against minor changes to the warning message's text.
    """
    with pytest.warns(UserWarning, match="Semantic splitter: no .* supplied"):
        ChunkConfig(strategy="semantic", chunk_size=64, chunk_overlap=8)
