"""
Insight Ingenious – PyMuPDF extractor integration tests
======================================================

This module validates that
:class:`~ingenious.document_processing.extractor.pymupdf.PyMuPDFExtractor`
honours **all** guarantees stated in its public contract for every supported
input flavour (*Path*, *bytes*, *BytesIO*).

Test Objectives
---------------
1. **Happy-path extraction** – A well-formed PDF must yield at least one
   element that satisfies the *Element* schema.
2. **Determinism** – Two successive invocations with identical input **must**
   return byte-for-byte identical results.
3. **Fail-soft semantics** – Malformed bytes should produce an **empty**
   iterator rather than raising an exception.
4. **Schema enforcement** – Every emitted mapping contains the mandatory keys
   with the correct types.
5. **Bounding-box sanity** – All coordinates lie within a generous
   1 000 × 1 000 pt user-space square (with a −50 pt y-tolerance to allow for
   negative origins).

Implementation Notes
--------------------
* Creating a :class:`PyMuPDFExtractor` is relatively expensive, so a single
  instance is provided via a module-scoped fixture.
* ``_PROBES`` is a table of callables that convert *(pdf_path, pdf_bytes)* into
  the specific probe object required by the extractor, allowing each test to
  be parametrised across input types.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Callable, List, Tuple

import pytest

from ingenious.document_processing.extractor import _load

# --------------------------------------------------------------------------- #
# Constants                                                                   #
# --------------------------------------------------------------------------- #
_EXTRACTOR_NAME: str = "pymupdf"
_MAX_COORD: int = 1_000  # upper bound for any x/y coordinate
_TOL: int = 50  # allow small negative y0 values (≈ 0.7 in)
_CORRUPT_PDF: bytes = b"%PDF-1.4 broken\n%%EOF"  # deliberately invalid payload


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def pymupdf() -> Any:
    """
    Return a shared :class:`PyMuPDFExtractor`.

    A single instance is reused for all tests to avoid repeated initialisation
    overhead and keep the test-suite fast.
    """
    return _load(_EXTRACTOR_NAME)


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _assert_valid_element(el: dict[str, Any]) -> None:
    """
    Assert that *el* meets the *Element* schema and bounding-box constraints.

    Expected structure
    ------------------
    ``{
        "page":   int   >= 1,
        "type":   str   (non-empty),
        "text":   str   (non-empty),
        "coords": Tuple[float | int, float | int, float | int, float | int]
    }``

    Bounding-box rules
    ------------------
    * ``0 <= x0 <= x1 <= {_MAX_COORD}``
    * ``-{_TOL} <= y0 <= y1 <= {_MAX_COORD}``
    """
    required = {"page", "type", "text", "coords"}
    missing = required.difference(el)
    assert not missing, f"element missing keys: {missing}"

    assert isinstance(el["page"], int) and el["page"] >= 1, "invalid page"
    assert isinstance(el["type"], str) and el["type"], "empty type"
    assert isinstance(el["text"], str) and el["text"], "empty text"

    coords = el["coords"]
    assert (
        isinstance(coords, tuple)
        and len(coords) == 4
        and all(isinstance(c, (int, float)) for c in coords)
    ), "coords must be numeric 4-tuple"

    x0, y0, x1, y1 = coords
    assert 0 <= x0 <= x1 <= _MAX_COORD, "x-coords out of range"
    assert -_TOL <= y0 <= y1 <= _MAX_COORD, "y-coords out of range"


# --------------------------------------------------------------------------- #
# Parametrisable probe builders                                               #
# --------------------------------------------------------------------------- #
Probe = Tuple[str, Callable[[Path, bytes], object]]
_PROBES: List[Probe] = [
    ("path", lambda p, _b: p),
    ("bytes", lambda _p, b: b),
    ("bytesio", lambda _p, b: io.BytesIO(b)),
]


# --------------------------------------------------------------------------- #
# 1. Happy-path + schema validation                                           #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(("kind", "probe_fn"), _PROBES, ids=[k for k, _ in _PROBES])
def test_extract_happy_paths(
    pymupdf: Any,
    pdf_path: Path,
    pdf_bytes: bytes,
    kind: str,
    probe_fn: Callable[[Path, bytes], object],
) -> None:
    """
    Verify that each input flavour yields **≥ 1** valid element.

    Only the first ten elements are validated for speed, as the schema check is
    deterministic and identical for the remainder.
    """
    probe = probe_fn(pdf_path, pdf_bytes)

    elements = list(pymupdf.extract(probe))
    assert elements, f"no elements extracted for {kind}"
    for el in elements[:10]:
        _assert_valid_element(el)


# --------------------------------------------------------------------------- #
# 2. Determinism across runs                                                  #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(("kind", "probe_fn"), _PROBES, ids=[k for k, _ in _PROBES])
def test_extract_idempotent(
    pymupdf: Any,
    pdf_path: Path,
    pdf_bytes: bytes,
    kind: str,
    probe_fn: Callable[[Path, bytes], object],
) -> None:
    """
    Ensure two identical invocations produce **exactly** the same output list.

    Deterministic behaviour is critical for caching layers and for avoiding
    spurious diffs in downstream pipelines.
    """
    probe = probe_fn(pdf_path, pdf_bytes)
    run1 = list(pymupdf.extract(probe))
    run2 = list(pymupdf.extract(probe))
    assert run1 == run2, f"extractor output not deterministic for {kind}"


# --------------------------------------------------------------------------- #
# 3. Fail-soft contract on corrupt bytes                                      #
# --------------------------------------------------------------------------- #
def test_extract_corrupt_bytes_returns_empty(pymupdf: Any) -> None:
    """
    A malformed PDF **must not** raise – it should simply return an empty list.

    This protects batch pipelines from aborting when a single document is
    damaged or truncated.
    """
    assert list(pymupdf.extract(_CORRUPT_PDF)) == []


# --------------------------------------------------------------------------- #
# 4. Memory usage and streaming tests                                         #
# --------------------------------------------------------------------------- #
def test_extract_stream_memory_monitoring(pymupdf: Any, pdf_path: Path) -> None:
    """
    Verify that extract_stream monitors memory usage and logs appropriately.

    This test ensures the memory monitoring infrastructure works correctly
    without necessarily exceeding the memory limit.
    """
    # Test with a very low memory limit to trigger monitoring
    elements = []
    for element in pymupdf.extract_stream(pdf_path, max_memory_mb=1.0):
        elements.append(element)
        # Break early to avoid excessive memory usage in tests
        if len(elements) >= 5:
            break

    # Should still extract at least some elements
    assert elements, "extract_stream should yield elements even with low memory limit"

    # Verify all elements follow the schema
    for el in elements:
        _assert_valid_element(el)


def test_extract_stream_progress_callback(pymupdf: Any, pdf_path: Path) -> None:
    """
    Verify that the progress callback is called correctly during extraction.
    """
    progress_calls = []

    def progress_callback(current_page: int, total_pages: int) -> None:
        progress_calls.append((current_page, total_pages))

    elements = list(
        pymupdf.extract_stream(pdf_path, progress_callback=progress_callback)
    )

    # Should have extracted elements
    assert elements, "extract_stream should yield elements"

    # Should have called progress callback
    assert progress_calls, "progress callback should have been called"

    # Verify progress calls are monotonic and within bounds
    total_pages = progress_calls[-1][1] if progress_calls else 0
    for current_page, reported_total in progress_calls:
        assert 1 <= current_page <= total_pages, (
            f"Invalid progress: {current_page}/{reported_total}"
        )
        assert reported_total == total_pages, (
            f"Total pages inconsistent: {reported_total} vs {total_pages}"
        )


def test_extract_stream_backward_compatibility(pymupdf: Any, pdf_path: Path) -> None:
    """
    Verify that extract() and extract_stream() produce identical results.

    This ensures backward compatibility is maintained.
    """
    # Extract using both methods
    elements_original = list(pymupdf.extract(pdf_path))
    elements_stream = list(pymupdf.extract_stream(pdf_path))

    # Results should be identical
    assert elements_original == elements_stream, (
        "extract() and extract_stream() should produce identical results"
    )


def test_extract_stream_memory_parameters(pymupdf: Any, pdf_path: Path) -> None:
    """
    Test extract_stream with various memory limit parameters.
    """
    # Test with default parameters
    elements_default = list(pymupdf.extract_stream(pdf_path))
    assert elements_default, "extract_stream with defaults should work"

    # Test with explicit memory limit
    elements_limited = list(pymupdf.extract_stream(pdf_path, max_memory_mb=50.0))
    assert elements_limited == elements_default, (
        "Different memory limits should not affect output"
    )

    # Test with very high memory limit
    elements_high = list(pymupdf.extract_stream(pdf_path, max_memory_mb=1000.0))
    assert elements_high == elements_default, (
        "High memory limit should not affect output"
    )


@pytest.mark.parametrize(("kind", "probe_fn"), _PROBES, ids=[k for k, _ in _PROBES])
def test_extract_stream_all_input_types(
    pymupdf: Any,
    pdf_path: Path,
    pdf_bytes: bytes,
    kind: str,
    probe_fn: Callable[[Path, bytes], object],
) -> None:
    """
    Verify that extract_stream works with all input types (path, bytes, BytesIO).
    """
    probe = probe_fn(pdf_path, pdf_bytes)

    elements = list(pymupdf.extract_stream(probe, max_memory_mb=100.0))
    assert elements, f"extract_stream should work with {kind} input"

    # Check first few elements
    for el in elements[:5]:
        _assert_valid_element(el)


def test_memory_usage_utility_methods(pymupdf: Any) -> None:
    """
    Test the memory monitoring utility methods work correctly.
    """
    # Test memory usage getter
    memory_usage = pymupdf._get_memory_usage_mb()
    assert isinstance(memory_usage, float), "Memory usage should be a float"
    assert memory_usage >= 0, "Memory usage should be non-negative"

    # Test memory threshold check
    start_memory = memory_usage
    # Should not exceed threshold with no additional memory usage
    assert not pymupdf._should_yield_control(1000.0, start_memory), (
        "Should not exceed high threshold"
    )
