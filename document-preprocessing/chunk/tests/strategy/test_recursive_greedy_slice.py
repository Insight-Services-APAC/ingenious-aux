"""
Purpose & Context
-----------------
Validates the *greedy slice* branch of
:pyclass:`ingenuous.chunk.strategy.RecursiveTokenSplitter` by asserting that
produced chunks respect the configured token budget **and** maintain the
required sliding‑window overlap invariant.  The test operates on a single
run‑on paragraph of 500 identical characters to force the splitter down its
worst‑case path.

Key Algorithms / Design Choices
-------------------------------
* **Hard budget** – ensures every chunk contains at most
  ``chunk_size + 2 * chunk_overlap`` tokens.
* **Overlap invariant** – verifies that the last ``chunk_overlap`` tokens of
  each chunk equal the first ``chunk_overlap`` tokens of the subsequent chunk.

Assertions are performed on the *tokenised* representation produced by
`tiktoken`, decoupling the test from implementation details such as character
lengths.
"""

from __future__ import annotations

from tiktoken import get_encoding

from ingenious.chunk.config import ChunkConfig
from ingenious.chunk.factory import build_splitter


def test_recursive_greedy_slice() -> None:
    """Ensure greedy slice respects token budget and overlap invariants.

    Rationale
    ---------
    Uses a pathological input string with no natural break‑points to coerce
    the recursive splitter into its greedy fallback path, guaranteeing the
    specific algorithmic branch is under test.

    Raises
    ------
    AssertionError
        If any chunk exceeds the allowed token budget or the overlap invariant
        is violated.

    Implementation Notes
    --------------------
    * ``max_allowed`` represents the strict upper bound for any chunk's token
      length derived from the configuration.
    * The overlap check is performed at the **token** level to mirror
      production semantics exactly.
    """
    text: str = "A" * 500  # one extremely long “paragraph” (no spaces)
    cfg: ChunkConfig = ChunkConfig(strategy="recursive", chunk_size=50, chunk_overlap=5)
    splitter = build_splitter(cfg)
    chunks = splitter.split_text(text)

    enc = get_encoding(cfg.encoding_name)
    max_allowed = cfg.chunk_size + 2 * cfg.chunk_overlap

    assert chunks and all(len(enc.encode(c)) <= max_allowed for c in chunks)

    # Overlap invariant – tail tokens of previous chunk equal head tokens of
    # current chunk.
    for i in range(1, len(chunks)):
        tail = enc.encode(chunks[i - 1])[-cfg.chunk_overlap :]
        head = enc.encode(chunks[i])[: cfg.chunk_overlap]
        assert tail == head
