"""
Provides shared session-scoped fixtures for pytest.

Purpose & Context
-----------------
This module, likely used as a `conftest.py` file, defines reusable data fixtures
for the Insight Ingenious test suite. Its primary purpose is to supply standardized,
reproducible test data (e.g., text files, structured data) to various test
functions, particularly those testing file I/O, data processing, and text chunking
logic found within the `ingenious/` application core.

By centralizing fixture definitions, we ensure test consistency, reduce code
duplication across test files, and improve test suite performance by creating
costly resources only once per session.

Key Algorithms & Design Choices
-------------------------------
- **Session-Scoped Fixtures**: All fixtures are defined with `@pytest.fixture(scope="session")`.
  This is a performance optimization that ensures the fixture setup code (like
  creating temporary files) runs only once for the entire test run, rather than
  before every single test function. The results are cached and reused.
- **`tmp_path_factory`**: We use pytest's built-in `tmp_path_factory` fixture to
  create temporary files and directories. This is the standard, robust way to
  handle temporary data in tests, as pytest guarantees the cleanup of these
  directories after the test session concludes.
- **Predictable Test Data**: The sample data (`_SAMPLE_TXT`, `_SAMPLE_MD`, etc.) is
  defined as module-level constants to ensure that all tests run against the
  exact same inputs, making test outcomes deterministic.
"""

import json
import pathlib

import pytest
from pytest import TempPathFactory

# Module-level constants for generating reproducible test data.
_SAMPLE_TXT = "The quick brown fox jumps over the lazy dog.\n" * 80
_SAMPLE_MD = "# Title\n\nParagraph\n\n## Subtitle\n\nMore text."
_SAMPLE_UNICODE = "日本語123 😀 " * 40


@pytest.fixture(scope="session")
def sample_text(tmp_path_factory: TempPathFactory) -> pathlib.Path:
    """Provides the path to a temporary text file with simple ASCII content.

    Rationale:
        This fixture uses `scope="session"` for high performance, as the file is
        created only once per test run. It leverages the standard `tmp_path_factory`
        for robust, automatically cleaned-up temporary file creation. The content
        is large enough to be suitable for testing streaming, reading, and basic
        text processing components.

    Args:
        tmp_path_factory: The pytest fixture for creating temporary directories.

    Returns:
        A `pathlib.Path` object pointing to the newly created `.txt` file.
    """
    p = tmp_path_factory.mktemp("data_for_test") / "doc.txt"
    p.write_text(_SAMPLE_TXT, encoding="utf-8")
    return p


@pytest.fixture(scope="session")
def sample_md(tmp_path_factory: TempPathFactory) -> pathlib.Path:
    """Provides the path to a temporary Markdown file.

    Rationale:
        Similar to `sample_text`, this fixture efficiently provides a file for
        testing. The Markdown content is specifically designed for testing more
        advanced text splitters or parsers that need to handle structured text
        (e.g., by splitting on headers or paragraphs).

    Args:
        tmp_path_factory: The pytest fixture for creating temporary directories.

    Returns:
        A `pathlib.Path` object pointing to the newly created `.md` file.
    """
    p = tmp_path_factory.mktemp("data") / "doc.md"
    p.write_text(_SAMPLE_MD, encoding="utf-8")
    return p


@pytest.fixture(scope="session")
def unicode_text() -> str:
    """Provides an in-memory string with Unicode and emoji characters.

    Rationale:
        This fixture is essential for testing the robustness of any text
        processing logic against multi-byte characters. It helps catch common
        bugs related to character counting, encoding/decoding, and tokenization
        where algorithms incorrectly assume ASCII-only text. As it's just a
        string, no file I/O is needed, making it very fast.

    Returns:
        A `str` containing Japanese characters, numbers, and an emoji.
    """
    return _SAMPLE_UNICODE


@pytest.fixture(scope="session")
def tiny_chunks_jsonl(tmp_path_factory: TempPathFactory) -> pathlib.Path:
    """Provides a path to a temp JSONL file containing pre-chunked text.

    Rationale:
        This fixture simulates the output of the `ingenious.chunk` module. It is
        used to test downstream components (e.g., embedding or indexing agents)
        that consume chunked data. By providing pre-computed chunks, we can test
        these components in isolation, making tests faster and more focused, as
        we don't need to re-run the chunking process every time.

    Args:
        tmp_path_factory: The pytest fixture for creating temporary directories.

    Returns:
        A `pathlib.Path` object pointing to the newly created `.jsonl` file.

    Implementation Notes:
        The `ingenious` imports are local to the function. This can be a
        deliberate choice in `conftest.py` files to avoid circular dependencies
        or to speed up test collection by deferring slow imports until the
        fixture is actually used.
    """
    # Defer imports to avoid potential circular dependencies or slow test discovery.
    from ingenious.chunk.config import ChunkConfig
    from ingenious.chunk.factory import build_splitter

    # Use a sample text and a specific config to produce predictable chunks.
    text = "A " * 1000
    cfg = ChunkConfig(strategy="token", chunk_size=20, chunk_overlap=10)
    splitter = build_splitter(cfg)
    chunks = splitter.split_text(text)

    # Write chunks to a JSONL file, where each line is a JSON object.
    p = tmp_path_factory.mktemp("data_for_tiny_chunks") / "tiny_chunks.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            rec = {"text": chunk, "meta": {"page": 0}}
            f.write(json.dumps(rec) + "\n")
    return p
