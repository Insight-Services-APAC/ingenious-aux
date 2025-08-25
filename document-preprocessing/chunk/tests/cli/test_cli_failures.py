"""
Integration tests for the chunking command-line interface (CLI).

Purpose & Context:
This module verifies the behavior of the CLI application defined in
`ingenious.chunk.cli`. It ensures that the Typer-based interface correctly
handles user input, validates arguments, invokes the core chunking logic,
and provides clear, user-friendly feedback for both success and error
scenarios. These tests are a critical part of the Insight Ingenious
architecture as they confirm that the core data processing logic is
correctly exposed to and usable by end-users or automated scripts.

Key Algorithms / Design Choices:
The testing strategy relies on `typer.testing.CliRunner`. This utility allows
for in-process invocation of the CLI, simulating command-line arguments and
capturing stdout, stderr, and exit codes without spawning a new subprocess.
This approach is fast, reliable, and provides rich result objects for
detailed assertions. Tests use the `pytest` `tmp_path` fixture to create
temporary files, ensuring tests are isolated and have no side effects on the
filesystem.
"""

from pathlib import Path

from typer.testing import CliRunner

from ingenious.chunk.cli import cli


def test_cli_invalid_overlap(tmp_path: Path) -> None:
    """Tests the CLI exits with a non-zero code for invalid chunk overlap.

    Rationale:
        This test validates a critical business rule for the chunking algorithm:
        the chunk overlap must be strictly less than the chunk size to ensure
        the chunking process can make forward progress through a document.
        By testing this at the CLI boundary, we ensure that the validation logic
        is correctly wired into the user-facing application and that it provides
        clear, actionable feedback instead of an unhandled exception.

    Args:
        tmp_path (Path): A pytest fixture that provides a temporary directory
            path for creating test files.

    Returns:
        None

    Raises:
        AssertionError: If the CLI does not exit with the expected error code
            or if the output does not match the expected error message format.

    Implementation Notes:
        We use `CliRunner` to invoke the CLI in-process. `catch_exceptions=True`
        is essential; it captures `SystemExit` exceptions raised by Typer on
        validation failure, preventing them from terminating the test runner.
        This allows us to assert that the program exited intentionally and to
        inspect the output for the user-friendly error banner (`❌`).
    """
    src = tmp_path / "doc.txt"
    src.write_text("hello")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["run", str(src), "--chunk-size", "10", "--chunk-overlap", "10"],
        catch_exceptions=True,
    )

    # --- assertions ---------------------------------------------------- #
    # The CLI should exit with code 1, indicating a user error.
    # It must raise a clean `SystemExit`, not another unhandled exception.
    # The output should contain the standard error indicator for visibility.
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "❌" in result.output
