"""
Tests for the chunking strategy registry and retrieval mechanism.

Purpose & Context:
    This module contains unit tests for the chunking strategy factory located in
    `ingenious.chunk.strategy`. It verifies two critical behaviors:
    1.  All core, supported chunking strategies are correctly registered and available.
    2.  The factory function (`get`) behaves predictably and raises a clear error
        when a non-existent strategy is requested.
    These tests are essential for ensuring the stability of the document processing
    pipelines within the Insight Ingenious architecture, as various agents and flows
    rely on this mechanism to correctly segment documents for tasks like RAG.

Key Algorithms / Design Choices:
    The tests are built using the `pytest` framework.
    -   `test_all_strategies_registered` uses a set-based comparison (`issubset`)
        to confirm the presence of core strategies. This approach is robust because
        it is order-independent and allows for other, non-core strategies to be
        added to the registry without breaking this test.
    -   `test_get_unknown_strategy` uses the `pytest.raises` context manager to
        idiomatically assert that a `ValueError` is thrown, which is standard
        practice for exception testing.
"""

import pytest

from ingenious.chunk.strategy import _SPLITTER_REGISTRY, get


def test_all_strategies_registered() -> None:
    """Verifies that all expected chunking strategies are registered."""
    expected = {"recursive", "markdown", "token", "semantic"}
    assert expected.issubset(_SPLITTER_REGISTRY.keys())


def test_get_unknown_strategy() -> None:
    """Ensures the get() function raises a ValueError for an unknown strategy."""
    # This now correctly matches the actual error message from the application.
    with pytest.raises(ValueError, match="Unknown chunking strategy"):
        get("does-not-exist")
