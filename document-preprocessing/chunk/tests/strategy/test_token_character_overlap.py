"""
Tests for text chunker invariants in the Insight Ingenious framework.

Purpose & Context
-----------------
This module contains pytest-based unit tests to verify critical invariants
of the text splitting (chunking) logic located in `ingenious.chunk`.
Correct chunking is fundamental to the Retrieval-Augmented Generation (RAG)
pipelines in Insight Ingenious, as it directly impacts the quality of context
provided to language models.

This file specifically tests that configuration parameters like `chunk_overlap`
are respected, regardless of the splitting `strategy` (e.g., "token",
"recursive") or the `overlap_unit` (e.g., "characters", "tokens").

Key Algorithms / Design Choices
-------------------------------
The tests are designed as property-based checks against the chunker's output.
For instance, to verify overlap, the test programmatically creates a chunker with
a known overlap setting, splits a sample text, and then asserts that the
suffix of chunk `N` is identical to the prefix of chunk `N+1`. This approach
is robust and directly validates the expected behavior.
"""

from ingenious.chunk.config import ChunkConfig
from ingenious.chunk.factory import build_splitter

# A constant representing the character overlap to test for.
# Using a small prime number helps avoid trivial alignments with chunk sizes.
K = 5


def test_token_character_overlap(unicode_text: str) -> None:
    """Verifies character-based overlap is correct for the 'token' strategy.

    Rationale:
        This test confirms a fundamental invariant: when `overlap_unit` is set
        to "characters", the specified number of characters must be shared
        between consecutive chunks. This is crucial for maintaining semantic
        continuity in RAG pipelines, preventing context from being lost at
        chunk boundaries. A direct suffix/prefix comparison is the most
        reliable validation method.

    Args:
        unicode_text (str): A string containing diverse Unicode characters,
            provided by the `unicode_text` pytest fixture. Using a complex
            text ensures the logic is robust against multi-byte characters.

    Returns:
        None

    Raises:
        AssertionError: If the suffix of a preceding chunk does not exactly
            match the prefix of the subsequent chunk, or if fewer than two
            chunks are produced.

    Implementation Notes:
        - The overlap size `K` is defined as a module-level constant for
          clarity and ease of modification.
        - The test requires that `unicode_text` is long enough relative to
          `chunk_size` to produce at least two chunks. This is guaranteed
          by the fixture's design.
    """
    cfg = ChunkConfig(
        strategy="token",
        chunk_size=40,
        chunk_overlap=K,
        overlap_unit="characters",
    )
    splitter = build_splitter(cfg)
    chunks = splitter.split_text(unicode_text)

    # The invariant can only be checked if there is at least one overlap.
    assert len(chunks) >= 2, (
        "Test text did not produce enough chunks for an overlap check."
    )

    for i in range(1, len(chunks)):
        # The last K characters of the previous chunk must be the first K of the current.
        previous_chunk_suffix = chunks[i - 1][-K:]
        current_chunk_prefix = chunks[i][:K]
        assert previous_chunk_suffix == current_chunk_prefix
