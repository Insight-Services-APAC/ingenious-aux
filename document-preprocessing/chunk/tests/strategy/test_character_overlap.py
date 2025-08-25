"""
Regression test ensuring character‑level overlap semantics are identical across
all Insight Ingenious chunk‑splitting strategies.

Purpose & context
-----------------
Insight Ingenious exposes several pluggable text‑splitting strategies
(`recursive`, `markdown`, `token`).  Regardless of the concrete strategy, when
`overlap_unit="characters"` the framework guarantees that the trailing
``chunk_overlap`` characters of chunk *i* reappear as the leading characters of
chunk *i+1*.  This invariant is critical for downstream retrieval‑augmented
generation (RAG) pipelines that rely on contiguous context windows.

This test validates that contract using an intentionally small
``chunk_size`` to force many overlap boundaries.  For the *semantic* strategy
(`langchain_semantic`) a stub embedder is injected so the suite runs offline.

Key algorithms / design choices
-------------------------------
* **Hermetic execution** A stub ``OpenAIEmbeddings`` implementation avoids
  network calls during the test run.
* **Parametrised assertion** The identical logic is executed against every
  supported strategy via ``pytest.mark.parametrize``.
* **Synthetic corpus** Repeating the ASCII alphabet four times yields a short
  yet sufficiently long string to generate > 1 chunk with all strategies.
"""

from __future__ import annotations

from typing import List
from unittest.mock import MagicMock, patch

import pytest

from ingenious.chunk.config import ChunkConfig
from ingenious.chunk.factory import build_splitter

# ---------------------------------------------------------------------------
# Constants & helpers
# ---------------------------------------------------------------------------

_TEXT: str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ" * 4  # long enough to create chunks
_OVERLAP_K: int = 3  # overlap window size in characters


def _fake_embedder() -> MagicMock:
    """Return a minimal stub mimicking ``OpenAIEmbeddings``.

    The stub exposes an ``embed_documents`` method that returns a fixed‑length
    zero vector for each supplied text.  This is sufficient for the splitter
    factory to initialise the *semantic* strategy without performing network
    requests.

    Returns
    -------
    MagicMock
        A fully initialised mock object standing in for the real embeddings
        backend.
    """
    stub = MagicMock()
    stub.embed_documents.side_effect = lambda texts: [[0.0] * 5 for _ in texts]
    return stub


# ---------------------------------------------------------------------------
# Parametrised integration test
# ---------------------------------------------------------------------------


@patch(
    "ingenious.chunk.strategy.langchain_semantic.OpenAIEmbeddings",
    return_value=_fake_embedder(),
)
@pytest.mark.parametrize("strategy", ["recursive", "markdown", "token"])
def test_character_overlap_consistency(_, strategy: str) -> None:
    """Ensure character‑based overlap behaves identically for all strategies.

    For ``overlap_unit="characters"`` the last *k* characters of chunk ``i``
    **must** equal the first *k* characters of chunk ``i+1``.  This test
    iterates over every built‑in splitter and asserts that the invariant holds.

    Parameters
    ----------
    _
        Unused fixture injected by :pyfunc:`unittest.mock.patch`.
    strategy : str
        Name of the splitting strategy under test.

    Raises
    ------
    AssertionError
        If fewer than two chunks are produced *or* if any adjacent chunk pair
        violates the overlap invariant.
    """
    cfg = ChunkConfig(
        strategy=strategy,
        chunk_size=15,  # tiny to force many chunks
        chunk_overlap=_OVERLAP_K,
        overlap_unit="characters",
    )
    splitter = build_splitter(cfg)
    chunks: List[str] = splitter.split_text(_TEXT)

    # At least two chunks must be produced
    assert len(chunks) >= 2

    for i in range(1, len(chunks)):
        assert chunks[i - 1][-_OVERLAP_K:] == chunks[i][:_OVERLAP_K]
