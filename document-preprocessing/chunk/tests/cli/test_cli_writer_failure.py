"""
Purpose & context
-----------------
Validate that the Insight Ingenious Chunking CLI (`ingenious.chunk.cli.cli`) fails
gracefully when it cannot write the output JSON Lines file.

The test monkey‑patches `jsonlines.open` so it always raises `OSError("disk full")`
to emulate a full‑disk scenario. We then run the CLI via Typer's `CliRunner`
and assert that:

* the process exits with status code **1**;
* the error message contains the lower‑cased reason ("disk full");
* the message is prefixed with the standard ❌ failure glyph used across Insight
  Ingenious CLIs for human‑readable errors.

Key algorithms / design choices
-------------------------------
Hermetic testing: the monkey‑patch avoids real I/O, making the test deterministic
and fast. Capturing the CLI result via `CliRunner.invoke` allows us to check both
exit code and stderr/stdout in one place.
"""

from __future__ import annotations

from pathlib import Path

import jsonlines
import pytest
from typer.testing import CliRunner

from ingenious.chunk.cli import cli


def test_cli_write_failure(
    monkeypatch: pytest.MonkeyPatch,
    sample_text: Path,
    tmp_path: Path,
) -> None:
    """Simulate a disk‑write *OSError* and verify graceful CLI failure.

    Rationale:
        A full or read‑only disk is a common edge‑case. The CLI must surface a
        clear, user‑actionable error and exit with a non‑zero status so that
        calling scripts/CI pipelines can detect the failure.

    Args:
        monkeypatch: Pytest fixture for dynamic attribute replacement.
        sample_text: Path to a short UTF‑8 text file fed to the CLI.
        tmp_path: Temporary directory provided by pytest for outputs.

    Raises:
        AssertionError: If the CLI does not obey the failure contract.

    Implementation Notes:
        ``jsonlines.open`` is monkey‑patched with a stub (`_boom`) that raises
        ``OSError`` to avoid touching the real filesystem. The asserted ❌ glyph
        comes from the shared `ingenious.cli._rich` helpers.
    """

    def _boom(*_: object, **__: object) -> None:
        """Deterministically fail when the CLI tries to open the output file."""
        raise OSError("disk full")

    monkeypatch.setattr(jsonlines, "open", _boom)

    result = CliRunner().invoke(
        cli,
        [
            "run",
            str(sample_text),
            "--chunk-size",
            "64",
            "--chunk-overlap",
            "8",
            "--output",
            str(tmp_path / "out.jsonl"),
        ],
    )

    assert result.exit_code == 1
    assert "disk full" in result.output.lower()
    assert "❌" in result.output
