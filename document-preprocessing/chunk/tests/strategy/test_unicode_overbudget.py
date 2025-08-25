"""
Purpose & context
-----------------
This test module validates that the token‑based chunk‑splitting strategy used
in *Insight Ingenious* handles single‑grapheme inputs that individually exceed
the configured ``chunk_size``. Such inputs must be emitted intact to avoid
introducing malformed UTF‑16 sequences or corrupting user text. The module
lives inside ``ingenious/chunk/tests`` and verifies behaviour of the public
factory helper :pyfunc:`ingenious.chunk.factory.build_splitter`.

Key algorithms / design choices
-------------------------------
The splitter operates on OpenAI's ``tiktoken`` encodings rather than raw byte
or code‑point counts, because downstream cost and context windows are measured
in tokens. The test purposefully selects the 😀 emoji (U+1F600) whose encoded
token length (2–3 tokens in ``cl100k_base``) guarantees the "over budget"
condition with minimal noise.
"""

from __future__ import annotations

from tiktoken import get_encoding

from ingenious.chunk.config import ChunkConfig
from ingenious.chunk.factory import build_splitter


def test_unicode_single_grapheme_overbudget() -> None:
    """Ensure an over‑budget single grapheme remains intact.

    Rationale
        The chunk splitter must *never* break apart a grapheme that encodes to
        more tokens than ``chunk_size``—doing so would violate Unicode
        boundaries and could yield invalid UTF‑16. Instead, it should emit the
        grapheme as its own chunk, even though it exceeds the budget.

    Args
        None

    Returns
        None – the test passes if no assertion fails.

    Raises
        AssertionError
            If the splitter returns multiple fragments or any fragment is not
            valid UTF‑16.

    Implementation Notes
        * The 😀 emoji encodes to 2–3 tokens in ``cl100k_base``; subtracting one
          from that count guarantees the "over‑budget" scenario while remaining
          deterministic across tokenizer releases.
        * An explicit ``encode("utf-16", "strict")`` verifies the resulting
          text contains only well‑formed surrogate pairs.
    """
    emoji = "😀"  # 2–3 tokens, depending on encoding
    enc = get_encoding("cl100k_base")
    budget = len(enc.encode(emoji)) - 1  # guarantee “over budget”

    cfg = ChunkConfig(strategy="token", chunk_size=budget, chunk_overlap=0)
    splitter = build_splitter(cfg)

    chunks = splitter.split_text(emoji)
    non_empty = [c for c in chunks if c]  # drop any leading empty strings

    assert non_empty == [emoji]  # must keep whole grapheme
    non_empty[0].encode("utf-16", "strict")  # must remain valid UTF‑16
