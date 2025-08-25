"""
Tests for the text chunking utilities in the Insight Ingenious framework.

Purpose & Context:
    This test module validates the core text splitting functionality found in
    `ingenious.chunk`. Reliable text chunking is a foundational requirement for
    many downstream AI processes, including Retrieval-Augmented Generation (RAG),
    where documents are split into manageable pieces for embedding and vector
    searches. This module ensures that the chunking logic is robust, accurate,
    and preserves data integrity, especially across complex text structures.

Key Algorithms / Design Choices:
    The tests are designed to probe boundary conditions of the splitting
    algorithms (e.g., recursive character, token-based). A key focus is on the
    correct handling of Unicode, particularly multi-byte characters and grapheme
    clusters. This specific test (`test_grapheme_boundaries_preserved`) uses UTF-16
    encoding validation as a robust method to detect when a multi-byte character
    has been improperly split, which would result in invalid "lone surrogate"
    code points.
"""

from ingenious.chunk.config import ChunkConfig
from ingenious.chunk.factory import build_splitter


def test_grapheme_boundaries_preserved() -> None:
    """Verifies that the token-based splitter respects grapheme cluster boundaries.

    Rationale:
        This test is critical because naive byte- or character-based splitting can
        corrupt multi-byte Unicode characters (e.g., emojis, flags). Such
        corruption would produce invalid text chunks, leading to downstream
        errors in embedding models or rendering. We validate this by attempting
        to encode each chunk to UTF-16; an invalid split of a multi-byte
        character would create a "lone surrogate" pair, causing a
        `UnicodeEncodeError`. This provides a reliable and computationally
        cheap way to confirm grapheme integrity.

    Args:
        None

    Returns:
        None

    Raises:
        AssertionError: If a generated chunk contains a partial, invalid
                        Unicode character sequence that cannot be encoded.

    Implementation Notes:
        The input string `text` is specifically constructed to contain several
        challenging Unicode cases:
        - `😀`: A 4-byte emoji (U+1F600).
        - `🇦🇺`: A flag grapheme composed of two regional indicator symbols
               (U+1F1E6 and U+1F1E8).
        - `café`: A character with a diacritical mark (U+00E9).
        The string is repeated to ensure its token length exceeds `chunk_size`,
        forcing the splitter to perform segmentation.
    """
    text = "😀🇦🇺 café\n" * 5  # Emojis, flags, and accented chars
    cfg = ChunkConfig(strategy="token", chunk_size=4, chunk_overlap=0)
    splitter = build_splitter(cfg)

    chunks = splitter.split_text(text)

    # Every chunk must be composed of valid Unicode grapheme clusters. A cheap
    # way to verify this is to ensure it can be encoded to UTF-16, which
    # would fail if a split created a lone surrogate.
    for c in chunks:
        try:
            c.encode("utf-16", "strict")
        except UnicodeEncodeError:
            assert False, f"Invalid UTF-16 sequence in chunk: {repr(c)}"
