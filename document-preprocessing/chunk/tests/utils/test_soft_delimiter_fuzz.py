"""
Fuzz tests for the soft delimiter logic in the `inject_overlap` utility.

Purpose & Context:
    This module provides property-based tests for the `inject_overlap` function
    located in `ingenious.chunk.utils.overlap`. Its primary focus is to validate
    the "soft delimiter" feature, which ensures a single space is injected
    between chunks when the left chunk doesn't end with whitespace and the right
    chunk doesn't start with one. This prevents words from merging during overlap
    creation, a critical behavior for maintaining semantic integrity in text
    processing pipelines within the Insight Ingenious architecture.

Key Algorithms / Design Choices:
    This test suite uses the `hypothesis` library for property-based testing (fuzzing).
    Instead of relying on a few handcrafted examples, this approach generates hundreds
    of random inputs that conform to specific strategies. This is highly effective
    for discovering edge cases in string manipulation logic that might be missed
    by traditional example-based tests.

    The strategies (`st.text`) are explicitly filtered to produce strings that
    create the exact boundary condition we need to test:
    1.  `left` string does not end with whitespace.
    2.  `right` string does not start with whitespace.
    This isolates the soft delimiter logic for robust verification.
"""

from hypothesis import given
from hypothesis import strategies as st

from ingenious.chunk.utils.overlap import inject_overlap


@given(
    left=st.text(min_size=1, max_size=10).filter(lambda s: not s[-1].isspace()),
    right=st.text(min_size=1, max_size=10).filter(lambda s: not s[0].isspace()),
)
def test_soft_delimiter_space_injected(left: str, right: str) -> None:
    """Verifies `inject_overlap` correctly injects a space as a soft delimiter.

    Rationale:
        This property-based test is crucial for ensuring that the chunking logic
        doesn't inadvertently merge words together. When two chunks are joined,
        if no natural whitespace exists at the boundary, a single space must be
        inserted to preserve word separation. This test validates that this
        behavior is consistent across a wide variety of randomly generated
        string inputs, confirming the robustness of the implementation.

    Args:
        left (str): An auto-generated string from `hypothesis` that is
            guaranteed to not end with a whitespace character.
        right (str): An auto-generated string from `hypothesis` that is
            guaranteed to not start with a whitespace character.

    Returns:
        None

    Raises:
        AssertionError: If the second overlapped chunk (`out[1]`) does not begin
            with the `left` string, a single space, and the first character of
            the `right` string.

    Implementation Notes:
        The `k` parameter for `inject_overlap` is set to `len(left)`, which
        creates a full overlap of the `left` string into the start of the next
        chunk. The assertion checks that the generated overlapped chunk correctly
        prepends `left`, adds the soft-delimiter space, and then continues
        with the `right` chunk.
    """
    out = inject_overlap([left, right], k=len(left), unit="characters")
    # out[1] should begin with the entirety of `left`, a SINGLE space,
    # and then the start of `right`.
    assert out[1].startswith(left + " " + right[0])
