"""
Negative-path unit test for the *Ingenious Chunking* CLI.

Purpose & context
-----------------
This test module exercises the CLI’s behaviour when a caller specifies an
*unknown* chunk-splitting strategy via the ``--strategy`` flag. In the wider
Insight Ingenious architecture the CLI is the primary user-facing entry-point
for generating semantic or token-based chunks, so validating its defensive
failure modes is critical.

Key design choices & trade-offs
-------------------------------
* **Typer CliRunner** – keeps the test process-isolated yet in-process, making
  it OS-agnostic and <10 ms to run, versus spawning a full subprocess.
* **Minimal fixture I/O** – the temporary source file contains a single token
  ("oops") to reduce disk overhead while still exercising the CLI’s Pydantic
  validation layer.
* **Explicit assertions** – we assert both a non-zero exit code *and* that an
  exception is propagated so future refactors cannot silently swallow
  validation errors.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from ingenious.chunk.cli import cli

__all__ = ["test_cli_unknown_strategy"]


def test_cli_unknown_strategy(tmp_path: Path) -> None:
    """Fail gracefully when an **unknown** strategy is requested via the CLI.

    Rationale
        Safeguards against silent regressions in the CLI’s argument-parsing or
        validation layers. A negative-path test ensures that unsupported
        strategies are *rejected* with a clear, propagated error.

    Args:
        tmp_path: PyTest fixture providing an isolated, writable directory. A
            dummy source file is written here to simulate user input.

    Returns:
        None. PyTest captures assertions; the function should terminate
        normally *only* when the CLI signals failure as intended.

    Raises:
        AssertionError: If the CLI exits with code 0 or suppresses the
            validation exception.

    Implementation Notes
        * Pydantic performs the underlying validation; this test ensures
          those errors are not swallowed.
        * ``CliRunner`` executes the command in-process, eliminating the cost
          of starting a new Python interpreter.
    """

    # Arrange – create a minimal source document
    src = tmp_path / "doc.txt"
    src.write_text("oops", encoding="utf-8")

    # Act – invoke the CLI with an invalid strategy flag
    result = CliRunner().invoke(
        cli,
        [
            "run",
            str(src),
            "--strategy",
            "does-not-exist",
        ],
    )

    # Assert – the CLI must *not* exit successfully and must surface the error
    assert result.exit_code != 0, "CLI should fail for unknown strategy"
    assert result.exception is not None, (
        "Validation error should propagate to the test harness"
    )
