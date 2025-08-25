"""
Unit tests for the document loading functionality.

Purpose & Context
-----------------
This module contains the pytest unit tests for the `load_documents` function, located
in the `ingenious.chunk.loader` module. The `load_documents` function is a critical
first step in the Insight Ingenious data ingestion pipeline. Its responsibility is to
take a path-like string (which can be a file, a directory, or a glob pattern) and
load the contents into a list of `Document` objects. These documents are then passed
to other components within the architecture, such as chunking agents or embedding
processors.

Key Algorithms / Design Choices
-------------------------------
The testing strategy relies on `pytest` and its `tmp_path` fixture. This fixture
provides a unique temporary directory for each test function, ensuring that tests are
hermetic, independent, and do not pollute the filesystem.

The test suite covers the following core scenarios:
1.  **Single File Loading**: The most basic case to ensure individual files are read.
2.  **Directory Traversal**: Confirms recursive loading from a directory structure.
3.  **Glob Pattern Matching**: Verifies that wildcard paths are correctly expanded and
    all matching files are loaded.
4.  **Error Handling**: Ensures that a `FileNotFoundError` is raised for paths that
    do not resolve to any files, preventing silent failures.
"""

# -------------------------------------------------
from pathlib import Path

import pytest

from ingenious.chunk.loader import load_documents


def test_load_txt(tmp_path: Path) -> None:
    """Verifies that a single plain text file can be loaded correctly.

    Rationale:
        This test covers the most fundamental success case: loading a single,
        unambiguous file path. It establishes a baseline for the loader's
        core functionality before testing more complex scenarios like directories
        or glob patterns.

    Args:
        tmp_path (Path): The pytest fixture providing a temporary directory path.

    Raises:
        AssertionError: If the loaded document content or metadata does not
            match the expected values.
    """
    f = tmp_path / "a.txt"
    f.write_text("hello world", encoding="utf-8")
    docs = load_documents(str(f))
    assert len(docs) == 1
    assert docs[0].page_content == "hello world"
    assert docs[0].metadata["source"].endswith("a.txt")


def test_load_directory(tmp_path: Path) -> None:
    """Verifies that `load_documents` can recursively load files from a directory.

    Rationale:
        Users frequently need to ingest all documents from a specific folder.
        This test ensures that the function correctly handles directory paths,
        recursively finding and loading all supported file types within it.

    Args:
        tmp_path (Path): The pytest fixture providing a temporary directory path.

    Raises:
        AssertionError: If the documents within the directory are not loaded
            as expected.
    """
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.md").write_text("# Title\nBody", encoding="utf-8")
    docs = load_documents(str(tmp_path))
    assert len(docs) == 1
    assert "# Title" in docs[0].page_content


def test_load_glob(tmp_path: Path) -> None:
    """Checks if a glob pattern correctly loads multiple matching files.

    Rationale:
        Glob patterns offer a flexible and powerful way for users to specify a
        batch of files. This test confirms that the glob expansion logic works
        as intended and that all matched files are correctly processed into
        `Document` objects.

    Args:
        tmp_path (Path): The pytest fixture providing a temporary directory path.

    Raises:
        AssertionError: If the set of loaded documents does not match the set
            of created files.

    Implementation Notes:
        The assertion uses a set comprehension (`{d.page_content for d in docs}`)
        to verify the contents of all loaded documents. This makes the test
        robust against changes in the filesystem's or loader's file ordering.
    """
    for n in range(3):
        (tmp_path / f"{n}.txt").write_text(str(n), encoding="utf-8")
    docs = load_documents(str(tmp_path / "*.txt"))
    assert {d.page_content for d in docs} == {"0", "1", "2"}


def test_load_empty(tmp_path: Path) -> None:
    """Ensures a `FileNotFoundError` is raised for a non-existent path.

    Rationale:
        It is critical for the system to fail predictably when given invalid
        input. This test verifies that the loader correctly raises a
        `FileNotFoundError` when the path or glob does not match any files,
        preventing silent failures and providing clear feedback to the caller.

    Args:
        tmp_path (Path): The pytest fixture providing a temporary directory path.

    Raises:
        AssertionError: If `FileNotFoundError` is not raised by the function call.
    """
    with pytest.raises(FileNotFoundError):
        load_documents(str(tmp_path / "no_files_here"))
