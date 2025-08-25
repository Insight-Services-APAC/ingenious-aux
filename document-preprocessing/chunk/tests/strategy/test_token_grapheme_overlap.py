"""
Tests grapheme cluster integrity during text chunking.

Purpose & Context:
    This module contains unit tests for the `ingenious.chunk` subsystem,
    specifically verifying that text splitting algorithms do not break Unicode
    grapheme clusters. Complex characters, such as emojis with skin-tone
    modifiers or ZWJ (Zero-Width Joiner) sequences, can be composed of
    multiple code points. If a chunker splits a string in the middle of such a
    sequence, it corrupts the data, leading to rendering errors or faulty
    analysis by downstream agents (e.g., Large Language Models).

    These tests ensure that the chunking factory and its configured strategies
    are "grapheme-aware," preserving data fidelity, which is a critical
    requirement for the Insight Ingenious data processing pipeline.

Key Algorithms & Design Choices:
    The core testing strategy involves creating a string composed of a repeating
    complex emoji (`👩‍💻`, "woman technologist"). This emoji is constructed
    from multiple Unicode code points, including a Zero-Width Joiner (`\u200d`).

    The primary assertion, `_assert_no_split`, checks that no chunk produced by
    the splitter starts or ends with an orphaned ZWJ. This is a robust and
    efficient heuristic for detecting improper grapheme splits. The tests use
    deliberately small chunk and overlap sizes to stress-test the boundary-
    handling logic of the splitting algorithms under different configurations.
"""

from ingenious.chunk.config import ChunkConfig
from ingenious.chunk.factory import build_splitter

EMOJI = "👩‍💻"  # multi‑code‑point emoji with ZWJ
TEXT = (EMOJI + " ") * 40  # long enough to force many chunks
ZWLJ = "\u200d"  # zero‑width joiner


def _assert_no_split(chunks: list[str]) -> None:
    """Asserts that no chunk has been split mid-grapheme.

    Rationale:
        This helper provides a reusable and specific assertion for grapheme
        integrity. By checking for an orphaned Zero-Width Joiner (ZWJ) at the
        boundaries of each chunk, we can reliably detect when a complex emoji
        or other multi-code-point character has been incorrectly divided. This
        is more robust than simply checking for the presence of the full emoji.

    Args:
        chunks: A list of text chunks produced by a splitter.

    Raises:
        AssertionError: If a chunk starts or ends with a ZWJ character,
            indicating a split within a grapheme cluster.
    """
    for c in chunks:
        assert not c.startswith(ZWLJ), f"Chunk starts with ZWJ: '{c[:10]}...'"
        assert not c.endswith(ZWLJ), f"Chunk ends with ZWJ: '...{c[-10:]}'"


def test_token_unit_grapheme_overlap() -> None:
    """Verifies grapheme integrity when using token-based overlap.

    Rationale:
        This test case specifically validates the `token` splitting strategy
        when `chunk_overlap` is also measured in `tokens`. The small
        `chunk_size` and `chunk_overlap` values are deliberately chosen to create
        stress conditions at chunk boundaries, increasing the likelihood of
        exposing grapheme splitting bugs. This ensures robustness for a
        common chunking configuration.

    Implementation Notes:
        - See ticket `TKT-4815`: "Ensure chunker respects grapheme boundaries."
    """
    cfg = ChunkConfig(
        strategy="token",
        chunk_size=8,  # deliberately tiny
        chunk_overlap=4,
        overlap_unit="tokens",
    )
    chunks = build_splitter(cfg).split_text(TEXT)
    _assert_no_split(chunks)


def test_character_unit_grapheme_overlap() -> None:
    """Verifies grapheme integrity when using character-based overlap.

    Rationale:
        This test complements `test_token_unit_grapheme_overlap` by validating
        the `token` splitting strategy when `chunk_overlap` is measured in
        `characters`. This is a distinct and important scenario, as character
        offsets do not naturally align with token or grapheme boundaries. This
        test ensures the splitter's logic correctly adjusts boundaries to
        preserve whole graphemes, regardless of the overlap unit.

    Implementation Notes:
        - See ticket `TKT-4815`: "Ensure chunker respects grapheme boundaries."
    """
    cfg = ChunkConfig(
        strategy="token",
        chunk_size=12,
        chunk_overlap=5,
        overlap_unit="characters",
    )
    chunks = build_splitter(cfg).split_text(TEXT)
    _assert_no_split(chunks)
