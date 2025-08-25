"""
Quick smoke test for CLI ``ingen chunk run`` error handling.

Purpose & context
-----------------
This module verifies that the chunking CLI gracefully handles the case
where the user passes a glob that matches no parsable documents. When no
such documents are found the CLI is expected to:

* return a non-zero exit code (``1``),
* emit a red cross (``❌``) marker, and
* print the explanatory message "No parsable documents found".

This test protects against regressions in the CLI plumbing layer and
ensures a consistent user experience in build pipelines that rely on the
process exit status.

Key design choices
------------------
* Typer's built-in ``CliRunner`` is used to execute the command in-process.
  This keeps the test hermetic and fast (<5 ms).
* The ``tmp_path`` fixture provides an isolated filesystem sandbox. A
  bogus glob (``*.doesnotexist``) is created within that sandbox so that
  the test never touches real project data.
* No external fixtures or mocks are required, following the "lean test"
  principle in DI-101.
"""

from pathlib import Path

from typer.testing import CliRunner

from ingenious.chunk.cli import cli


def test_cli_no_matching_files(tmp_path: Path) -> None:
    """Ensure ``ingen chunk run`` exits with code 1 and a clear error.

    Summary
    -------
    Validate that invoking the CLI with a glob that matches *no* input
    files results in:

    1. An exit status of ``1`` (generic failure).
    2. A ❌ emoji to draw user attention.
    3. The phrase "No parsable documents found" in the output.

    Rationale
    ---------
    Users occasionally mistype glob patterns or point to empty
    directories. Failing fast with an explicit message prevents silent
    mis-configurations in downstream ETL pipelines.

    Args
    ----
    tmp_path: pytest's per-test temporary directory fixture.

    Raises
    ------
    AssertionError
        If the CLI deviates from the contract described above.

    Implementation notes
    --------------------
    * The ``*.doesnotexist`` suffix guarantees the glob matches nothing.
    * The ❌ symbol is asserted verbatim, mirroring the CLI's UX choice
      rather than a plain-text fallback, providing stronger regression
      protection.
    """

    pattern = tmp_path / "*.doesnotexist"
    res = CliRunner().invoke(cli, ["run", str(pattern)])

    assert res.exit_code == 1
    assert "❌" in res.output
    assert "No parsable documents found" in res.output
