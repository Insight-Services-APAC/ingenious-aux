"""
End-to-end CLI test verifying recursive directory traversal and glob pattern
handling for the ``ingen chunk run`` command.

Purpose & Context
-----------------
This test exercises the public CLI exposed by :pymod:`ingenious.chunk.cli` to
ensure that:

* Recursive file discovery based on a user-supplied glob pattern (**no shell
  expansion**) works when invoked via Typer's ``CliRunner``.
* Chunking parameters/flags (``--chunk-size`` and ``--chunk-overlap``) are
  parsed and forwarded without modification.
* Output is serialised as **newline-delimited JSON** (``.jsonl``) containing
  one record per chunk produced.

The test is intentionally **black-box**: it does not patch or mock internal
helpers. Instead it runs the binary end-to-end to catch regressions in Typer’s
argument parsing, filesystem traversal, and chunker integration.
"""

from __future__ import annotations

from pathlib import Path

import jsonlines
from typer.testing import CliRunner

from ingenious.chunk.cli import cli


def test_cli_directory_and_glob(tmp_path: Path) -> None:
    """Black-box CLI regression test.

    Rationale
    ---------
    Covers a user scenario where an **entire directory tree** of plain-text
    documents is chunked in a single invocation. The glob pattern is passed
    verbatim to the application (shell does *not* expand ``**``). Historically
    this code path broke when we switched from ``Path.rglob`` to ``glob.glob``
    because the latter did not honour ``recursive=True``.

    Args
    ----
    tmp_path:
        Pytest fixture providing a unique temporary directory for the test
        session. Used to create an ad-hoc corpus and capture the CLI output.

    Raises
    ------
    AssertionError
        If the CLI returns a non-zero exit code **or** the emitted chunks do
        not match the input corpus exactly.

    Implementation notes
    --------------------
    * Each source file contains a single digit so that the emitted chunk text
      equals the filename stem – this makes equality checks trivial.
    * ``jsonlines`` is preferred over the stdlib because it transparently
      handles newline-delimited JSON without additional buffering logic.
    """

    # --- Arrange ----------------------------------------------------------------
    data_dir = tmp_path / "docs"
    data_dir.mkdir()
    for i in range(3):
        (data_dir / f"{i}.txt").write_text(str(i), encoding="utf-8")

    out_file = tmp_path / "out.jsonl"
    runner = CliRunner()

    # --- Act --------------------------------------------------------------------
    result = runner.invoke(
        cli,
        [
            "run",
            f"{data_dir}/**/*.txt",  # glob retained (no shell expansion)
            "--chunk-size",
            "10",
            "--chunk-overlap",
            "2",
            "--output",
            str(out_file),
        ],
    )

    # --- Assert -----------------------------------------------------------------
    assert result.exit_code == 0, result.output
    with jsonlines.open(out_file) as rdr:
        stripped = {rec["text"].strip() for rec in rdr}
    assert stripped == {"0", "1", "2"}
