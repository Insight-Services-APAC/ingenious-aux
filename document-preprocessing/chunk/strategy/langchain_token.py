"""
Provides a Unicode-safe, token-aware text splitting strategy.

Purpose & Context
-----------------
This module implements the "token" chunking strategy for the Insight Ingenious
framework. Its primary purpose is to provide a highly precise splitting mechanism
that operates on a strict token budget while guaranteeing Unicode correctness. This
prevents the silent corruption of complex characters (e.g., emojis with multiple
codepoints, accented letters), which is critical for processing multilingual or
unstructured modern text for RAG pipelines.

This component is a core strategy located in ``ingenious/chunk/strategy/`` and is
instantiated via the central ``ingenious.chunk.factory.build_splitter``.

Key Algorithms & Design Choices
-------------------------------
1.  **Grapheme-First Splitting**: The cornerstone of this module's Unicode safety
    is its initial step: the input text is immediately parsed into a list of
    extended grapheme clusters using the ``regex`` library's ``\\X`` atom. All
    subsequent splitting and buffering operations work on this list of graphemes,
    ensuring that no multi-byte or composite character is ever torn apart.
2.  **Dual-Path Implementation**: The ``create`` factory intelligently selects an
    implementation based on the user's configuration (`overlap_unit`):
    -   **Token Budgets**: Uses the custom ``UnicodeSafeTokenTextSplitter`` for its
        high-precision, token-aware logic.
    -   **Character Budgets**: Delegates to LangChain's standard, word-aware
        ``RecursiveCharacterTextSplitter`` and reuses the ``_OverlapWrapper``
        from the "recursive" strategy. This promotes code reuse and uses the best
        tool for each job.
3.  **Safe Overlap Boundaries**: The token-splitting algorithm contains a complex
    rollback loop. This is a deliberate trade-off, prioritizing the correctness
    of the overlap text over raw performance. It guarantees that the k-token
    overlap window does not start mid-character, which would corrupt the text
    and cause downstream errors.

Usage Example
-------------
.. code-block:: python

    from ingenious.chunk.config import ChunkConfig
    from ingenious.chunk.factory import build_splitter

    # Example: Split text with a strict token budget and 20-token overlap.
    # This path will use the UnicodeSafeTokenTextSplitter.
    token_config = ChunkConfig(
        strategy="token",
        chunk_size=256,
        chunk_overlap=20,
        overlap_unit="tokens",
        encoding_name="cl100k_base",
    )
    splitter = build_splitter(token_config)

    # This text contains a multi-codepoint emoji: 👩‍👩‍👧‍👦
    text_with_emoji = "This is the first sentence. 👩‍👩‍👧‍👦 This family emoji " \
                      "should never be split. This is the final sentence."
    chunks = splitter.split_text(text_with_emoji)

    for i, chunk in enumerate(chunks):
        print(f"--- Chunk {i+1} ---\\n{chunk}\\n")
"""

from __future__ import annotations

from typing import List

import regex as re
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_text_splitters.base import TextSplitter
from tiktoken import Encoding, get_encoding

from ..config import ChunkConfig
from . import register
from .langchain_recursive import _OverlapWrapper  # Reuse for char-budget path

__all__: list[str] = ["create"]

# Pre-compiled regex for Unicode extended grapheme clusters (TR-29).
# This ensures we never split inside a composite emoji or accented character.
_GRAPHEME_RE = re.compile(r"\X", re.UNICODE)

# Zero-width joiner, a common "glue" in emoji sequences, used as a boundary sentinel.
_ZWJ = "\u200d"


def _is_roundtrip_safe(encoder: Encoding, token_ids: list[int]) -> bool:
    """Checks if token IDs can be safely decoded and re-encoded."""
    return encoder.encode(encoder.decode(token_ids)) == token_ids


class UnicodeSafeTokenTextSplitter(TextSplitter):
    """A Unicode-safe text splitter that enforces a strict token or character budget.

    Rationale:
        This class was created because standard token splitters are not guaranteed
        to be Unicode-correct and can split inside complex graphemes (e.g., emojis,
        accented characters). By operating on a list of graphemes, this
        implementation guarantees correctness, which is critical for preserving the
        integrity of multilingual or emoji-rich text. The custom logic is necessary
        to enforce a strict token budget, a feature not available in standard
        grapheme-aware splitters.
    """

    def __init__(
        self,
        encoding_name: str,
        chunk_size: int,
        chunk_overlap: int,
        overlap_unit: str = "tokens",
    ):
        """Initializes the Unicode-safe splitter.

        Args:
            encoding_name: The name of the ``tiktoken`` encoding (e.g., "cl100k_base").
            chunk_size: The hard upper-bound for each chunk before overlap is added.
            chunk_overlap: The size of the bidirectional overlap window.
            overlap_unit: The unit for budgeting ("tokens" or "characters").
        """
        super().__init__(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self._enc = get_encoding(encoding_name)
        self._overlap_unit = overlap_unit

    def split_text(self, text: str) -> list[str]:
        """Splits text into chunks respecting a strict budget and Unicode rules.

        Rationale:
            The implementation iterates grapheme-by-grapheme to respect Unicode
            boundaries. The complex rollback loop is a deliberate trade-off,
            prioritizing the correctness of the overlap text over raw performance.
            It ensures that the overlap added to the next chunk is a valid,
            decodable string, preventing downstream errors in the RAG pipeline.

        Args:
            text: The input text to be split.

        Returns:
            A list of text chunks.

        Implementation Notes:
            The algorithm works by building a buffer of graphemes. When adding a
            new grapheme exceeds the token budget, a rollback loop searches
            backwards from the end of the buffer to find a "safe" boundary. A safe
            boundary is one where the last K tokens (the overlap) can be decoded
            without corruption. This has a known complexity of O(N*C) in the worst
            case, and its performance is tracked by tests in
            ``tests/perf/test_unicode_splitter_perf.py``.
        """
        clusters = _GRAPHEME_RE.findall(text)
        if self._overlap_unit == "characters":
            return self._split_char_budget(clusters)

        # Token-budget path
        output_chunks: list[str] = []
        grapheme_buffer: list[str] = []

        for grapheme in clusters:
            # Handle a single grapheme that is larger than the entire chunk budget.
            grapheme_len_in_tokens = len(self._enc.encode(grapheme))
            if grapheme_len_in_tokens > self._chunk_size:
                if grapheme_buffer:  # Flush anything before this oversized grapheme.
                    output_chunks.append("".join(grapheme_buffer))
                    grapheme_buffer = []
                output_chunks.append(grapheme)
                continue

            grapheme_buffer.append(grapheme)
            buffer_len_in_tokens = len(self._enc.encode("".join(grapheme_buffer)))

            if buffer_len_in_tokens <= self._chunk_size:
                continue

            # --- Budget Overflow: Find a safe split point ---
            grapheme_buffer.pop()  # Roll back the grapheme that caused the overflow.

            carry_graphemes: list[str] = []
            while grapheme_buffer:
                # A boundary is "safe" if the overlap it creates is not corrupt.
                is_safe = self._is_boundary_safe(
                    grapheme_buffer, carry_graphemes, grapheme
                )
                if is_safe:
                    break
                # If not safe, move the last grapheme from the buffer to the carry.
                carry_graphemes.insert(0, grapheme_buffer.pop())

            if grapheme_buffer:
                output_chunks.append("".join(grapheme_buffer))

            # Start the new buffer with the overlap, carried-over graphemes,
            # and the current grapheme that caused the overflow.
            overlap_graphemes = (
                self._build_overlap(grapheme_buffer) if grapheme_buffer else []
            )
            grapheme_buffer = overlap_graphemes + carry_graphemes + [grapheme]

        if grapheme_buffer:
            output_chunks.append("".join(grapheme_buffer))
        return output_chunks

    def _is_boundary_safe(
        self,
        current_buffer: list[str],
        carry: list[str],
        next_grapheme: str,
    ) -> bool:
        """Checks if a potential chunk boundary will create a valid overlap."""
        k = self._chunk_overlap
        if k == 0:
            return True

        chunk_tokens = self._enc.encode("".join(current_buffer))
        if len(chunk_tokens) < k:
            return True  # Not enough tokens to form an overlap, so boundary is fine.

        # 1. Check if the overlap tokens are decodable on their own.
        overlap_tokens = chunk_tokens[-k:]
        if not _is_roundtrip_safe(self._enc, overlap_tokens):
            return False

        # 2. Check for invalid Unicode sequences in the decoded overlap.
        overlap_text = self._enc.decode(overlap_tokens)
        if overlap_text.startswith(_ZWJ) or "\ufffd" in overlap_text:
            return False

        # 3. Check for re-encoding consistency.
        next_chunk_start_text = overlap_text + "".join(carry) + next_grapheme
        next_chunk_start_tokens = self._enc.encode(next_chunk_start_text)
        if next_chunk_start_tokens[:k] != overlap_tokens:
            return False

        return True

    def _split_char_budget(self, clusters: list[str]) -> list[str]:
        """A simpler splitting path that operates on a character budget."""
        output_chunks: list[str] = []
        grapheme_buffer: list[str] = []
        current_char_len: int = 0

        for grapheme in clusters:
            grapheme_len = len(grapheme)
            if current_char_len + grapheme_len > self._chunk_size and grapheme_buffer:
                output_chunks.append("".join(grapheme_buffer))
                # Build overlap from the list of graphemes, not a broken string
                overlap_graphemes = self._build_overlap(grapheme_buffer)
                grapheme_buffer = overlap_graphemes + [grapheme]
                current_char_len = len("".join(grapheme_buffer))
            else:
                grapheme_buffer.append(grapheme)
                current_char_len += grapheme_len

        if grapheme_buffer:
            output_chunks.append("".join(grapheme_buffer))

        return output_chunks

    def _build_overlap(self, old_buf_graphemes: List[str]) -> List[str]:
        """Extracts the overlap window (last K units) from the previous buffer.

        Rationale:
            This helper centralizes the logic for creating the overlap window.
            It's called *after* the main ``split_text`` loop has determined a safe
            split boundary, so its logic can be simpler: it just needs to extract
            the last K units and convert them back to a list of graphemes.
        """
        k = self._chunk_overlap
        if k == 0 or not old_buf_graphemes:
            return []

        if self._overlap_unit == "characters":
            # In character mode, graphemes are the unit.
            return old_buf_graphemes[-k:].copy()

        # In token mode, we extract the last K tokens and decode them.
        tokens = self._enc.encode("".join(old_buf_graphemes))
        tail_text = self._enc.decode(tokens[-k:])
        return _GRAPHEME_RE.findall(tail_text)


@register("token")
def create(cfg: ChunkConfig) -> TextSplitter:
    """Factory for the 'token' splitter, choosing an implementation by unit.

    Rationale:
        This factory abstracts the complexity of the dual-path implementation. It
        selects the highly precise but complex ``UnicodeSafeTokenTextSplitter``
        for token-based splitting, and reuses the more standard and word-aware
        ``RecursiveCharacterTextSplitter`` for character-based splitting. This
        ensures the best tool is used for each job while maintaining a consistent
        API for the caller.

    Args:
        cfg: The centralized configuration object.

    Returns:
        A configured text splitter instance ready for use.

    Implementation Notes:
        For the character-budget path, the base splitter is initialized with
        ``chunk_overlap=0`` because the ``_OverlapWrapper`` is responsible for
        injecting the overlap, preventing conflicts.
    """
    if cfg.overlap_unit == "tokens":
        return UnicodeSafeTokenTextSplitter(
            encoding_name=cfg.encoding_name,
            chunk_size=cfg.chunk_size,
            chunk_overlap=cfg.chunk_overlap,
            overlap_unit="tokens",
        )

    # For character budgets, delegate to the robust word-aware recursive splitter.
    base = RecursiveCharacterTextSplitter(
        chunk_size=cfg.chunk_size,
        chunk_overlap=0,  # Overlap is injected by the wrapper.
    )
    return _OverlapWrapper(
        base,
        cfg.chunk_overlap,
        cfg.encoding_name,
        unit="characters",
    )
