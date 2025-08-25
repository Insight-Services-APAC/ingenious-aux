"""
Unit tests that verify token‑level overlap consistency of the chunking
splitters shipped with the Insight Ingenious framework.

Purpose & Context
-----------------
The Insight Ingenious retrieval pipeline relies on reproducible chunk
boundaries so embeddings can be compared across indexing runs. This test suite
asserts that every supported splitting strategy preserves a configurable token
overlap when ``overlap_unit="tokens"``.

Key algorithms / design choices
-------------------------------
* **Strategy parametrisation** – A single parametric test covers all splitter
  implementations, ensuring new strategies are automatically tested by adding
  them to the parameter list or enum.
* **Unicode‑safe measurement** – Token accounting is done with
  ``tiktoken.get_encoding``, guarding against off‑by‑one errors introduced by
  multibyte characters.
"""

from __future__ import annotations

from typing import List
from unittest.mock import MagicMock, patch

import pytest
from tiktoken import get_encoding

from ingenious.chunk.config import ChunkConfig
from ingenious.chunk.factory import build_splitter

# --------------------------------------------------------------------------- #
# Test fixtures & stubs
# --------------------------------------------------------------------------- #
_fake_embed = MagicMock()
_fake_embed.embed_documents.side_effect = lambda texts: [[0.0] * 5 for _ in texts]


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
@patch(
    "ingenious.chunk.strategy.langchain_semantic.OpenAIEmbeddings",
    return_value=_fake_embed,
)
@pytest.mark.parametrize(
    "strategy",
    ["recursive", "markdown", "token", "semantic"],
)
def test_token_overlap_consistency(
    _patched_embeddings: MagicMock,
    strategy: str,
) -> None:
    """Ensure ``chunk_overlap`` tokens are preserved between adjacent chunks.

    For a given ``strategy`` the test checks that the last five tokens of chunk
    *i – 1* are identical to the first five tokens of chunk *i* across the
    entire split sequence.

    Args:
        _patched_embeddings: Fixture injected by :pyfunc:`unittest.mock.patch`
            to neutralise remote embedding calls.
        strategy: Name of the splitter strategy under test.

    Raises:
        AssertionError: If any adjacent chunk pair violates the overlap
            contract.
    """
    cfg = ChunkConfig(
        strategy=strategy,
        chunk_size=20,
        chunk_overlap=5,
        overlap_unit="tokens",
    )
    splitter = build_splitter(cfg)

    text: str = "foo bar baz qux " * 20
    chunks: List[str] = splitter.split_text(text)

    enc = get_encoding(cfg.encoding_name)
    for i in range(1, len(chunks)):
        prev_tail = enc.encode(chunks[i - 1])[-5:]
        curr_head = enc.encode(chunks[i])[:5]
        assert prev_tail == curr_head
