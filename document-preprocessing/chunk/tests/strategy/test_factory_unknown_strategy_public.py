"""
Tests for the text splitter factory in ingenious.chunk.factory.

Purpose & Context:
    This module contains unit tests for the `build_splitter` factory function,
    which is a critical component of the Insight Ingenious document processing
    pipeline. The factory is responsible for instantiating a specific text
    splitter implementation based on the provided `ChunkConfig`. These tests
    ensure the factory's robustness, particularly its ability to handle invalid
    or corrupt configurations gracefully.

Key Algorithms / Design Choices:
    The tests employ standard `pytest` patterns for assertion and context
    management. A notable technique used is `object.__setattr__` to bypass the
    immutability of Pydantic configuration models. This allows for targeted
    "white-box" testing of invalid states (e.g., a strategy string that cannot
    be created via the model's public API), simulating data corruption without
    altering the production code's design.
"""

import pytest

from ingenious.chunk.config import ChunkConfig
from ingenious.chunk.factory import build_splitter


def test_build_splitter_unknown_strategy() -> None:
    """Verifies that build_splitter raises ValueError for an unknown strategy.

    Rationale:
        This test ensures the factory fails fast with a clear error when the
        configuration is invalid. Robust validation is critical to prevent
        downstream components from operating on malformed data, which could
        result from manual misconfiguration or deserializing untrusted data.
        This aligns with the DI-101 principle of defensive programming.

    Raises:
        AssertionError: If `pytest.raises` fails to catch the expected
            `ValueError`.

    Implementation Notes:
        To test this specific failure mode, the test deliberately bypasses the
        immutability of the `ChunkConfig` Pydantic model using
        `object.__setattr__`. This simulates a runtime state where the
        `strategy` field holds an invalid string, allowing for a focused test
        of the factory's error-handling logic without modifying the config
        model's validation rules.
    """
    # 1. ARRANGE: Create a valid default config instance.
    cfg = ChunkConfig()

    # 2. ACT: Bypass immutability to inject an invalid strategy name.
    #    This simulates a corrupted configuration object.
    object.__setattr__(cfg, "strategy", "does-not-exist")

    # 3. ASSERT: The factory must raise a ValueError with a specific message.
    with pytest.raises(ValueError, match="Unknown chunking strategy"):
        build_splitter(cfg)
