"""
Tests for the chunker factory in the Insight Ingenious framework.

Purpose & Context:
    This module contains unit tests for the `build_splitter` function located in
    `ingenious.chunk.factory`. The factory is a critical component that
    instantiates different text splitting strategies based on a configuration
    object (`ChunkConfig`). Correctly dispatching to and configuring the
    requested splitter is essential for the reliable processing of documents
    before they are passed to language models or vector stores.

Key Algorithms / Design Choices:
    The tests use a black-box approach, focusing on the public API of the
    factory (`build_splitter`) and the resulting splitter object. The core
    verification strategy is to:
    1.  Provide a valid `ChunkConfig` for a specific strategy.
    2.  Invoke the factory to build the splitter.
    3.  Pass sample text to the splitter.
    4.  Assert that the output chunks adhere to the configuration constraints,
        such as `chunk_size` and `chunk_overlap`.
"""

from typing import NoReturn

from tiktoken import get_encoding

from ingenious.chunk.config import ChunkConfig
from ingenious.chunk.factory import build_splitter

ENC = "cl100k_base"


def test_factory_dispatch_recursive() -> NoReturn:
    """Verifies the factory builds a recursive splitter with correct constraints.

    Rationale:
        This test validates the most common code path: creating a
        `RecursiveCharacterTextSplitter`. It ensures the factory correctly
        interprets the `ChunkConfig` and that the resulting splitter respects
        the specified token limits for chunk size and overlap, which is
        fundamental to the system's token management.

    Args:
        None

    Returns:
        None

    Raises:
        AssertionError: If the splitter produces no chunks or if any chunk
            exceeds the maximum allowed token size.

    Implementation Notes:
        -   The test uses a long, repetitive string (`"foo\n\nbar" * 50`) to
            ensure that splitting is actually required.
        -   The maximum allowed size is calculated as `chunk_size + 2 * chunk_overlap`.
            This accounts for a worst-case scenario where a chunk has overlap
            added to both its beginning and its end by the splitter logic.
            See ticket [CH-144] for background on this calculation.
        -   Token length is verified using the same `tiktoken` encoder
            (`cl100k_base`) that the splitter is configured to use internally.
    """
    cfg = ChunkConfig(
        strategy="recursive",
        chunk_size=50,
        chunk_overlap=10,
        encoding_name=ENC,
    )
    splitter = build_splitter(cfg)
    chunks = splitter.split_text("foo\n\nbar" * 50)

    enc = get_encoding(ENC)
    # A chunk can have overlap prepended and appended, so the theoretical max
    # size of a chunk's content is the target size plus overlap on both sides.
    max_allowed = cfg.chunk_size + 2 * cfg.chunk_overlap
    assert chunks, "Splitter should always produce at least one chunk."
    assert all(len(enc.encode(c)) <= max_allowed for c in chunks), (
        "A generated chunk exceeded the maximum allowed token limit."
    )
