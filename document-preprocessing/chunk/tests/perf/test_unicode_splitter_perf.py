"""
Guards UnicodeSafeTokenTextSplitter against performance regressions.

This module provides a performance regression test for the
`UnicodeSafeTokenTextSplitter` class, ensuring its text-splitting algorithm
maintains linear-time complexity.

Purpose & Context
-----------------
The splitter is a core component within the Insight Ingenious data processing
pipeline (`ingenious.chunk.strategy`), responsible for breaking down large
documents into token-aware chunks for language models. An early implementation
of this splitter exhibited quadratic ($O(N^2)$) complexity because it re-encoded
the entire text buffer on each grapheme iteration. This module's test prevents
any future code changes from reintroducing such super-linear behaviour, which
could severely degrade performance on large inputs.

Key Algorithms / Design Choices
-------------------------------
The test employs a call-counting strategy instead of wall-clock timing to
achieve deterministic and reliable results in a CI/CD environment. It uses
`pytest`'s `monkeypatch` fixture to wrap the underlying `tiktoken.Encoding.encode`
method. By counting how many times this expensive method is invoked, we can
directly measure the algorithm's computational complexity.

The test asserts that the number of calls is bound by a linear function of the
input size ($4 \times N$, where $N$ is the number of graphemes). This provides a
generous but firm upper bound that is orders of magnitude lower than the
$O(N^2)$ behaviour we are guarding against.
"""

from __future__ import annotations

import regex as re
from pytest import MonkeyPatch

from ingenious.chunk.strategy.langchain_token import UnicodeSafeTokenTextSplitter


def test_encode_call_count(monkeypatch: MonkeyPatch) -> None:
    """Asserts that `split_text` complexity is linear by counting `encode` calls.

    Rationale:
        This test safeguards against performance regressions in the token splitting
        logic. Using call counting instead of wall-clock timing provides a
        deterministic and robust measure of algorithmic complexity, making it
        ideal for automated CI checks. A regression to quadratic behavior would
        cause the call count to rise dramatically and fail the test.

    Args:
        monkeypatch (MonkeyPatch): The `pytest` fixture used to dynamically
            replace the `encode` method with a counting wrapper.

    Returns:
        None

    Raises:
        AssertionError: If the number of calls to `encode()` exceeds the
            calculated linear-time threshold ($4 \times N$), indicating a
            potential performance regression to super-linear complexity.

    Implementation Notes:
        The test performs five key steps:
        1.  Constructs a multi-kilobyte string with a mix of ASCII and
            multi-byte Unicode characters (extended grapheme clusters) to provide
            a realistic test case.
        2.  Initializes the `UnicodeSafeTokenTextSplitter` with a small chunk size
            to force many chunk-splitting operations.
        3.  Uses `monkeypatch` to replace the `tiktoken.Encoding.encode` method
            with a wrapper that increments a counter before calling the original.
        4.  Executes the `splitter.split_text()` method on the test string.
        5.  Asserts that the final call count is less than or equal to `4 * N`,
            where `N` is the number of graphemes in the input text.
    """
    # 1. Build a medium-size input: repeating "A😀 " (3 graphemes) so
    #    we get a mix of ASCII and multi-code-point emoji clusters.
    #    4,000 iterations → 12,000 graphemes, enough to exhibit
    #    previously quadratic behaviour without slowing the test suite.
    text: str = ("A😀 " * 4000).strip()
    clusters = re.findall(r"\X", text)  # \X = extended grapheme cluster
    n = len(clusters)

    # 2. Instantiate the tokenizer-aware splitter under test.
    splitter = UnicodeSafeTokenTextSplitter(
        encoding_name="cl100k_base",  # same default used in production
        chunk_size=64,  # tiny budget to force many flushes
        chunk_overlap=0,
        overlap_unit="tokens",
    )
    enc = splitter._enc  # tiktoken.Encoding instance (cached)

    # 3. Monkey-patch `enc.encode` with a counting wrapper so we can
    #    measure how many times the optimiser calls it.
    call_counter = {"n": 0}
    original_encode = enc.encode

    def _counting_encode(s: str) -> list[int]:
        """Increment counter and proxy the call to the original `encode`."""
        call_counter["n"] += 1
        return original_encode(s)

    monkeypatch.setattr(enc, "encode", _counting_encode)

    # 4. Run the split – all encode() invocations will now be tallied.
    splitter.split_text(text)

    # 5. Assertion – linear-time guard.
    #    Allow up to 4 * N encode calls; anything above indicates an
    #    accidental O(N^2) regression. The factor of 4 is a generous
    #    allowance based on the algorithm's implementation details.
    max_allowed = 4 * n
    actual_calls = call_counter["n"]
    assert actual_calls <= max_allowed, (
        f"O(N^2) regression detected: encode() called {actual_calls:,} times "
        f"for {n:,} graphemes (limit {max_allowed:,})"
    )
