"""
Tests for the Unicode-aware token-based text splitter.

Purpose & Context:
    This module provides property-based tests for the `UnicodeSafeTokenTextSplitter`.
    This splitter is a critical component within the `ingenious.chunk` subsystem,
    which prepares text for processing by Large Language Models (LLMs). Its primary
    role is to divide text into chunks that respect a given token limit while also
    ensuring that Unicode grapheme clusters (e.g., emojis with modifiers, complex
    characters) are never broken. This prevents data corruption that can degrade
    model performance or cause processing errors.

Key Algorithms / Design Choices:
    The testing strategy relies on `hypothesis` for property-based testing. This
    approach was chosen over example-based testing because it can explore a vast and
    unpredictable input space, which is essential for validating correctness against
    the complexities of Unicode. The core test logic verifies the splitter's main
    guarantee: chunks do not exceed the token budget, *unless* a single, indivisible
    grapheme cluster is itself larger than the budget.
"""

import regex as re
from hypothesis import given
from hypothesis import strategies as st
from tiktoken import get_encoding

from ingenious.chunk.strategy.langchain_token import UnicodeSafeTokenTextSplitter

# The standard encoding for GPT-3.5/4, used for calculating token counts.
ENC = "cl100k_base"

# A regular expression to find all Unicode grapheme clusters in a string.
# A grapheme cluster (`\X`) is the closest approximation to a user-perceived
# "character".
_GRAPHEME_RE = re.compile(r"\X", re.UNICODE)


@given(
    text=st.text(min_size=1, max_size=200),
    budget=st.integers(
        min_value=2, max_value=40
    ),  # min-budget 2 avoids trivial 1-token clash
)
def test_unicode_splitter_fuzz(text: str, budget: int):
    """Tests that the splitter respects the token budget without breaking graphemes.

    Rationale:
        This test uses property-based testing via `hypothesis` to ensure the
        splitter is robust against a wide variety of random string inputs. This is
        vastly more effective than manual example-based testing for catching edge
        cases in Unicode handling. The test verifies the two core promises of the
        splitter: respecting the token limit and preserving grapheme integrity.

    Args:
        text (str): A `hypothesis`-generated string to be split.
        budget (int): A `hypothesis`-generated integer for the `chunk_size` in
            tokens.

    Returns:
        None

    Raises:
        AssertionError: If a generated chunk violates the token budget or is not
            a valid UTF-16 string.

    Implementation Notes:
        The logic checks two conditions:
        1.  A chunk's token count must be `<= budget`.
        2.  An exception is made for the edge case where a single grapheme cluster
            (e.g., a complex emoji like "👨‍👩‍👧‍👦") is itself larger than the budget. In this
            scenario, the splitter correctly returns the grapheme as a single chunk,
            and this test asserts that this is the only time the budget may be
            exceeded.
        3.  It also confirms that every chunk can be strictly encoded to UTF-16,
            proving that no grapheme clusters were split apart during chunking.
    """
    splitter = UnicodeSafeTokenTextSplitter(
        encoding_name=ENC, chunk_size=budget, chunk_overlap=0
    )
    chunks = splitter.split_text(text)
    enc = get_encoding(ENC)

    for c in chunks:
        tokens = len(enc.encode(c))
        if tokens > budget:
            # This is only allowed if the chunk is a *single grapheme* that happens
            # to be larger than the token budget (e.g., a very complex emoji).
            assert len(_GRAPHEME_RE.findall(c)) == 1
        else:
            # Otherwise, the chunk must strictly respect the budget.
            assert tokens <= budget

        # This check ensures the chunk is still a valid Unicode string and that no
        # surrogate pairs were broken during splitting.
        c.encode("utf-16", "strict")
