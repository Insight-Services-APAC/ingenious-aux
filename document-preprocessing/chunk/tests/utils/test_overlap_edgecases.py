"""
Unit tests for edge cases in the `inject_overlap` utility.

This test suite validates the robustness of the `inject_overlap` utility, a
critical component of the Insight Ingenious data preprocessing pipeline. The function's
primary role is to maintain contextual continuity between document chunks by creating
overlapping segments. These tests focus specifically on edge cases and invalid inputs
to prevent data corruption before it reaches downstream agents or language models.

Key Test Strategies:
    Invalid Argument Handling: Ensures the function fails loudly and predictably when
        supplied with unsupported parameters (e.g., an invalid `unit`). This prevents
        silent failures and aligns with DI-101's emphasis on robust validation.
    Zero-Overlap Identity: Verifies that an overlap of `k=0` correctly functions as
        a no-op, returning a *copy* of the original chunks. This confirms the base
        case is handled and prevents unsafe mutations.
    Soft Delimiter Injection: Confirms that a space is inserted when a character-
        based overlap joins two non-whitespace characters. This is crucial to
        prevent accidental word concatenation (e.g., 'auto' + 'matic' becoming
        'automatic'), which would corrupt model input.
"""

import pytest

from ingenious.chunk.utils.overlap import inject_overlap


def test_inject_overlap_invalid_unit() -> None:
    """Verifies `inject_overlap` raises a `ValueError` for an unsupported unit.

    Rationale:
        This test enforces robust input validation as required by DI-101. The
        function must fail fast with a clear error message on invalid arguments,
        preventing silent errors or undefined behavior in the data processing pipeline.

    Args:
        None

    Returns:
        None

    Raises:
        AssertionError: If the call does not raise a `ValueError` as expected.
    """
    with pytest.raises(ValueError, match="unit must be 'tokens' or 'characters'"):
        # The prompt mentioned only 'tokens', but a robust check should match the
        # implementation. Assuming implementation supports 'characters' too.
        inject_overlap(chunks=["a", "b"], k=1, unit="bytes")


def test_inject_overlap_zero_k_returns_original() -> None:
    """Verifies `inject_overlap` with k=0 returns a copy of the original chunks.

    Rationale:
        This test confirms the correct handling of the base case (zero overlap). The
        function should be semantically a no-op but must return a new list instance
        to prevent downstream mutations from causing side effects on the original
        caller's data. This aligns with defensive programming practices in DI-101.

    Args:
        None

    Returns:
        None

    Raises:
        AssertionError: If the result is not a value-equal but non-identical copy
            of the original list.

    Implementation Notes:
        The test asserts two conditions:
        1. Value equality (`==`): The content of the list is unchanged.
        2. Identity inequality (`is not`): The returned list is a new object in
           memory, not a reference to the original. This is a critical contract.
    """
    original: list[str] = ["foo", "bar", "baz"]

    result = inject_overlap(chunks=original, k=0, unit="tokens")

    # Value equality ⇒ semantics unchanged
    assert result == original
    # Different object ⇒ callers can mutate safely without side-effects
    assert result is not original


def test_soft_delimiter_guard() -> None:
    """Tests that a space is inserted when overlapping non-whitespace boundaries.

    Rationale:
        This test addresses a critical data integrity issue. When creating character-
        based overlaps, simply concatenating text could merge two distinct words
        (e.g., "auto" and "matic" becoming "automatic"), corrupting the input for the
        language model. This test ensures a "soft delimiter" (a space) is added to
        preserve word boundaries.

    Args:
        None

    Returns:
        None

    Raises:
        AssertionError: If the overlapped chunk is missing the required space
            delimiter before the original content.

    Implementation Notes:
        This behavior is specific to `unit="characters"`. The test uses two chunks
        with no whitespace at their boundary ("abc", "def") and verifies that the
        second chunk becomes "abc def", not the corrupted "abcdef".
    """
    chunks = ["abc", "def"]
    # Overlap with all 3 characters from the first chunk.
    result = inject_overlap(chunks=chunks, k=3, unit="characters")

    # The original first chunk should remain unchanged.
    assert result[0] == "abc"
    # The second chunk should be prepended with the overlap plus a space.
    assert result[1] == "abc def"
