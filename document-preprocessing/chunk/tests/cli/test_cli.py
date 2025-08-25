"""
Smoke‑tests for the *Ingenious Chunking* command‑line interface (CLI).

Purpose & context
-----------------
This module validates the high‑level behaviour of the *chunking* CLI
implemented in :pymod:`ingenious.chunk.cli`.  The CLI is the primary entry
point that operators and automation pipelines use to split large text files
into smaller, token‑bounded chunks.  Ensuring its correctness is therefore
critical to the overall reliability of the Insight Ingenious ingestion
pipeline.

Key algorithms / design choices
------------------------------
* **Typer's** :class:`~typer.testing.CliRunner` is used to invoke the CLI in
  an isolated subprocess‑like environment without spawning a real shell.
* A tiny input file and conservative chunk parameters keep runtimes short
  while still exercising the *recursive* strategy's overlap logic.
* The JSON Lines output is parsed with **jsonlines** to assert business‑level
  guarantees such as *globally unique* chunk identifiers.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import jsonlines
from typer.testing import CliRunner

from ingenious.chunk.cli import cli

__all__ = [
    "test_cli_writes_jsonl",
    "test_cli_ids_unique",
]


def test_cli_writes_jsonl(sample_text: Path, tmp_path: Path) -> None:
    """Ensure the CLI produces a non‑empty ``*.jsonl`` file.

    Rationale
        A happy‑path invocation should exit with status *0* and create the
        specified output artifact.  By using a tiny chunk size (``80``) with a
        modest overlap (``10``), the test executes quickly while still walking
        through the recursive strategy's boundary conditions.

    Args
        sample_text: Path to the input text file provided by the ``sample_text``
            pytest fixture.
        tmp_path: Temporary directory supplied by pytest for isolated writes.

    Raises
        AssertionError: If the CLI exits non‑zero or the output file is missing
            / empty.

    Implementation notes
        • Typer's :class:`~typer.testing.CliRunner` emulates a shell call
          without spawning a new process.
        • Output existence and size checks supplant expensive full‑file content
          comparisons.
    """

    out_file = tmp_path / "out.jsonl"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "run",
            str(sample_text),
            "--strategy",
            "recursive",
            "--chunk-size",
            "80",
            "--chunk-overlap",
            "10",
            "--output",
            str(out_file),
        ],
    )

    assert result.exit_code == 0, result.output
    assert out_file.exists() and out_file.stat().st_size > 0


def test_cli_ids_unique(sample_text: Path, tmp_path: Path) -> None:
    """Verify that chunk identifiers emitted by the CLI are *globally unique*.

    Rationale
        Duplicate IDs would break downstream deduplication and traceability
        guarantees in the Insight Ingenious data model.  The test therefore
        parses the output JSON Lines file and asserts set‑membership across
        all produced ``id`` fields.

    Args
        sample_text: Path to the input text file provided by the ``sample_text``
            pytest fixture.
        tmp_path: Temporary directory supplied by pytest for isolated writes.

    Raises
        AssertionError: If any identifier appears more than once.

    Implementation notes
        • Uses :pyclass:`collections.Counter` for O(*n*) counting; n = number of
          chunks.
        • Relies on :pypi:`jsonlines` for streaming deserialization to keep
          memory usage negligible even for large outputs.
    """

    out_file = tmp_path / "out.jsonl"
    runner = CliRunner()
    runner.invoke(
        cli,
        [
            "run",
            str(sample_text),
            "--chunk-size",
            "80",
            "--chunk-overlap",
            "10",
            "-o",
            str(out_file),
        ],
        catch_exceptions=False,
    )

    with jsonlines.open(out_file) as reader:
        ids = [record["id"] for record in reader]

    dupes = [count for count in Counter(ids).values() if count > 1]
    assert not dupes, "Duplicate IDs detected"
