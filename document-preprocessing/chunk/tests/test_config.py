"""
Tests for ``ingenious.chunk.config.ChunkConfig``.

Purpose & context
-----------------
``ChunkConfig`` centralises text‑chunking parameters (``chunk_size``,
``chunk_overlap``, and ``strategy``) used across Insight Ingenious
retrieval‑augmented generation (RAG) pipelines. This test module guards those
defaults and invariants so that downstream agents and extensions can rely on
predictable behaviour.

Key algorithms / design choices
-------------------------------
No complex algorithms are required; declarative assertions provided by
**pytest** express expectations clearly. Validation paths are exercised via
``pytest.raises`` to capture exceptions raised by *pydantic* model validation
and custom post‑initialisation hooks.
"""

from __future__ import annotations

import pydantic
import pytest

from ingenious.chunk.config import ChunkConfig


def test_defaults() -> None:
    """Validate the default values exposed by :class:`ChunkConfig`.

    Rationale:
        Guarantees the shipped defaults (recursive strategy, 1 024‑token
        chunks, 128‑token overlap) remain stable, preserving the token budget
        assumptions baked into downstream RAG components.

    Args:
        None

    Returns:
        None

    Raises:
        AssertionError: If any default attribute deviates from the expected
            value.

    Implementation notes:
        The defaults are hard‑coded in ``ChunkConfig``. Should they evolve,
        update the constants here in tandem to avoid false‑positive failures.
    """

    cfg = ChunkConfig()
    assert cfg.strategy == "recursive"
    assert cfg.chunk_size == 1024
    assert cfg.chunk_overlap == 128


def test_validation_error() -> None:
    """Verify input validation logic of :class:`ChunkConfig`.

    Rationale:
        Ensures model invariants are strictly enforced, preventing
        misconfiguration leaks into production agent flows.

    Args:
        None

    Returns:
        None

    Raises:
        AssertionError: If supplying invalid parameters does **not** raise the
            expected exceptions.

    Implementation notes:
        Two invalid scenarios are covered:
        1. ``chunk_size`` must be positive.
        2. ``chunk_overlap`` must be **strictly** smaller than ``chunk_size``.
    """

    # 1️⃣ negative size still invalid
    with pytest.raises(pydantic.ValidationError):
        ChunkConfig(chunk_size=-1)

    # 2️⃣ overlap must now be strictly smaller than size
    with pytest.raises(ValueError):
        ChunkConfig(chunk_size=10, chunk_overlap=10)
