"""
Regression‑test that the token‑based overlap injected by
UnicodeSafeTokenTextSplitter complies with both the *length* and
*equality‑of‑text* invariants for every consecutive chunk pair.

Why compare text instead of token IDs?
--------------------------------------
The cl100k_base BPE can merge a trailing space from the previous chunk with
the first glyph of the next chunk, so token IDs may differ even though the
decoded strings are identical.  The test therefore asserts on *decoded
text*, allowing up to **+2 leading tokens** in the head slice—the same
tolerance used elsewhere in the suite.
"""

from __future__ import annotations

from tiktoken import get_encoding

from ingenious.chunk.config import ChunkConfig
from ingenious.chunk.factory import build_splitter

# --------------------------------------------------------------------------- #
# Constants                                                                   #
# --------------------------------------------------------------------------- #
ENC_NAME = "cl100k_base"
ENC = get_encoding(ENC_NAME)

K = 3  # overlap window (tokens)
EMOJI = "👩‍💻"  # multi‑code‑point (grapheme‑safe path)
TEXT = (EMOJI + " word ") * 40  # long enough to create many chunks


# --------------------------------------------------------------------------- #
# Test case                                                                   #
# --------------------------------------------------------------------------- #
def test_token_overlap_exact() -> None:
    """Verifies that consecutive text chunks have a semantically correct token-based overlap.

    Rationale:
        This test is critical for ensuring data integrity at chunk boundaries, a
        cornerstone for context-aware agents in the Insight Ingenious framework.
        The implementation's key design choice is to validate overlap using decoded
        *text* rather than raw token IDs. This provides robustness against BPE
        tokenizer artifacts, where semantically identical text (e.g., " word" vs.
        "word") can have different token representations. The small chunk size
        is chosen pragmatically to guarantee multiple chunks are produced from the
        test text, enabling the pairwise check.

    Raises:
        AssertionError: If the overlap length or text content between any two
            consecutive chunks is incorrect.

    Implementation Notes:
        The test validates two invariants for every pair of adjacent chunks
        `(chunks[i-1], chunks[i])`:

        1.  **Length Invariant**: The number of tokens in the overlapping segments
            must both equal the configured overlap size, `K`.
        2.  **Semantic Invariant**: The decoded text from the tail of the previous
            chunk must appear exactly at the start of the current chunk.

        A tolerance of `K + 2` tokens is used when slicing the head of the current
        chunk. This is necessary because the `cl100k_base` tokenizer might merge
        a trailing space from the previous chunk with the first word of the
        current one, altering tokenization. For example, `encode(' word')` can
        be one token, while `encode('word')` is another. Comparing decoded and
        stripped text (`lstrip()`) handles this ambiguity.

        The test text includes the multi-codepoint emoji "👩‍💻" to ensure the
        splitter is grapheme-safe.
    """
    cfg = ChunkConfig(
        strategy="token",
        chunk_size=30,  # small to guarantee ≥ 2 chunks
        chunk_overlap=K,
        overlap_unit="tokens",
        encoding_name=ENC_NAME,
    )
    chunks = build_splitter(cfg).split_text(TEXT)

    assert len(chunks) >= 2, "Splitter produced < 2 chunks – test is invalid"

    for prev, curr in zip(chunks, chunks[1:]):
        # --- Length Check ---
        # Ensure the tail of the previous chunk and the head of the current
        # chunk contain exactly K tokens.
        prev_tail_ids = ENC.encode(prev)[-K:]
        curr_head_ids = ENC.encode(curr)[:K]
        assert len(prev_tail_ids) == K, f"Tail length is {len(prev_tail_ids)}, not {K}"
        assert len(curr_head_ids) == K, f"Head length is {len(curr_head_ids)}, not {K}"

        # --- Semantic Equality Check ---
        # Decode the tail of the previous chunk.
        prev_tail_text = ENC.decode(prev_tail_ids)

        # Decode the head of the current chunk with a small tolerance to handle
        # BPE artifacts (e.g., merging a space with a word token).
        head_ids_with_tolerance = ENC.encode(curr)[: K + 2]
        head_text_with_tolerance = ENC.decode(head_ids_with_tolerance)

        # The stripped head text must start with the stripped tail text.
        err_msg = (
            f"Overlap mismatch:\n"
            f"  - Tail Text: {prev_tail_text.lstrip()!r}\n"
            f"  - Head Text: {head_text_with_tolerance.lstrip()!r}"
        )
        assert head_text_with_tolerance.lstrip().startswith(prev_tail_text.lstrip()), (
            err_msg
        )
