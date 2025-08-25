"""
Tests the robustness of the document loader against filesystem edge cases.

Purpose & Context:
    This test module verifies that `ingenious.chunk.loader.load_documents` can
    gracefully handle real-world filesystem issues. It is a critical component
    of the data ingestion pipeline for agents that process local user files. These
    tests ensure the system is resilient to common problems like permission
    errors and supports international file naming conventions.

Key Algorithms / Design Choices:
    The tests leverage pytest's `tmp_path` fixture to create an isolated,
    temporary filesystem for each test case. This prevents side effects and
    ensures test reproducibility.
    - Permission Test: Uses the `stat` module to manipulate file permissions
      (`chmod`), simulating a scenario where the loader encounters a file it
      cannot read.
    - Globbing Test: Uses non-ASCII filenames (Unicode) to verify that the
      underlying `glob` mechanism correctly handles international character sets.
"""

import stat
import sys
from pathlib import Path

import pytest

from ingenious.chunk.loader import load_documents


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="File permissions are not enforced on Windows in the same way as POSIX.",
)
def test_loader_skips_unreadable(tmp_path: Path) -> None:
    """Tests that the loader gracefully skips files with read permission errors.

    Rationale:
        In production, the system might be directed to scan directories containing
        inaccessible files (e.g., system files, other users' locked files).
        This test ensures that a single permission error does not crash the
        entire document ingestion process, making the application more resilient
        as per DI-101's error handling principles.

    Args:
        tmp_path (Path): The pytest fixture providing a temporary directory path.

    Implementation Notes:
        The test is skipped on Windows because `chmod(0)` does not prevent file
        reads by the file owner in the same way it does on POSIX systems. A
        `try...finally` block guarantees that file permissions are restored,
        preventing potential cleanup failures in CI/CD environments.
    """
    unreadable = tmp_path / "secret.txt"
    unreadable.write_text("top-secret", encoding="utf-8")
    unreadable.chmod(0)  # Remove all permissions.

    readable = tmp_path / "ok.txt"
    readable.write_text("hello", encoding="utf-8")

    # Ensure we restore permissions afterwards for CI clean-up.
    try:
        docs = load_documents(str(tmp_path))
        assert len(docs) == 1
        assert docs[0].page_content == "hello"
    finally:
        unreadable.chmod(stat.S_IWUSR | stat.S_IRUSR)


def test_loader_exotic_glob(tmp_path: Path) -> None:
    """Verifies `load_documents` correctly handles glob patterns with Unicode.

    Rationale:
        The Insight Ingenious platform is designed for global use. Users may
        have documents with names in various languages containing non-ASCII
        characters. This test confirms that our file discovery and loading
        mechanism is fully Unicode-aware, supporting internationalization (i18n).

    Args:
        tmp_path (Path): The pytest fixture providing a temporary directory path.

    Implementation Notes:
        This test creates files with Greek letters (α, β, γ) and then uses a
        glob pattern that also contains those characters. The assertion confirms
        that only the intended files (`α.txt`, `β.txt`) are matched and loaded.
    """
    for name in ["α.txt", "β.txt", "γ.md"]:
        (tmp_path / name).write_text(name, encoding="utf-8")

    # The glob pattern itself contains Unicode characters.
    docs = load_documents(str(tmp_path / "[αβ]*.txt"))
    assert {d.page_content for d in docs} == {"α.txt", "β.txt"}
