"""
Reconstruction helpers and regression test for the Unicode-safe token
chunker.

Purpose & context
-----------------
This test module guards against a historical bug (issue *M-1*) in the
`UnicodeSafeTokenTextSplitter` used throughout *Insight Ingenious* for
LLM-friendly chunking.  Prior to the fix, overlapping-window slicing
could **duplicate or omit graphemes** when the overlap equalled
`chunk_size − 1`.  The helper `_reconstruct()` re-assembles the list of
chunks while *skipping* the token-overlap window so we can assert that
the rebuilt text matches the source exactly.

Key algorithm / design choices
------------------------------
* **Token-aware reconstruction** – Uses *tiktoken*’s encoder/decoder to
  avoid Unicode-boundary issues.
* **Stateless helper** – `_reconstruct()` is pure and deterministic,
  making the regression test self-contained and side-effect-free.
"""

# -------------------------------------------------------------------
from tiktoken import get_encoding

from ingenious.chunk.config import ChunkConfig
from ingenious.chunk.factory import build_splitter


def _reconstruct(chunks: list[str], k: int, enc_name: str) -> str:
    """Re-assemble *chunks* by skipping the ``k``-token overlap window.

    Summary
        Concatenates the token lists of each chunk while discarding the
        first *k* tokens of every chunk except the first one.

    Rationale
        Mirrors the sliding-window logic of the production splitter so
        the regression test can detect duplicate or missing graphemes
        introduced by off-by-one errors.

    Args
        chunks: Ordered list of chunk strings produced by the splitter.
        k: Size of the overlap window (number of tokens skipped at each
           chunk boundary).
        enc_name: Encoding identifier understood by ``tiktoken``.

    Returns
        The reconstructed text *without* overlap artifacts.

    Raises
        KeyError: If *enc_name* is not a known encoding (propagated from
        ``tiktoken.get_encoding``).

    Implementation notes
        * Grapheme safety is delegated to ``tiktoken``.
        * Complexity: **O(N + M)** where *N* is the total number of
          tokens and *M* = ``len(chunks)`` (tokenisation overhead).
    """
    enc = get_encoding(enc_name)
    tokens: list[int] = []

    for i, chunk in enumerate(chunks):
        ids = enc.encode(chunk)
        tokens.extend(ids if i == 0 else ids[k:])

    return enc.decode(tokens)


def test_no_duplicate_or_missing_graphemes() -> None:
    """Regression test for issue M-1 (overlap duplication/loss).

    Ensures that reconstructing the text from overlapped chunks produced
    by ``UnicodeSafeTokenTextSplitter`` yields *exactly* the original
    input—no duplicated or dropped graphemes.

    Implementation notes
        * Uses 13 Greek letters to guarantee multiple windows.
        * Normalises whitespace because different tokenisers may treat
          consecutive spaces differently.
    """
    text = "α β γ δ ε ζ η θ ι κ λ μ"
    cfg = ChunkConfig(
        strategy="token",
        chunk_size=4,
        chunk_overlap=3,
        overlap_unit="tokens",
    )
    splitter = build_splitter(cfg)
    chunks = splitter.split_text(text)

    rebuilt = _reconstruct(chunks, cfg.chunk_overlap, cfg.encoding_name)

    assert " ".join(rebuilt.split()) == " ".join(text.split())
