"""
Purpose & Context
-----------------
End‑to‑end **pytest** test that verifies the Insight Ingenious chunking CLI
(`ingenious.chunk.cli`) correctly enforces a fixed *K*-character overlap when
`--overlap-unit characters` is supplied. This regression test protects against
boundary‑condition bugs in the recursive splitting strategy that could result
in lost or duplicated text across chunk boundaries.

Key Algorithm / Design Choices
------------------------------
1. A deterministic ~240‑character corpus is written to a temporary file using
   the `tmp_path` fixture.
2. The public Typer CLI is executed via `CliRunner` rather than importing
   internal helpers, ensuring the argument‑parsing layer is also exercised.
3. The produced JSONL output is parsed and the last *K* characters of each
   chunk are compared with the first *K* characters of the subsequent chunk to
   assert exact overlap.
"""

from __future__ import annotations

from pathlib import Path

import jsonlines
from typer.testing import CliRunner

from ingenious.chunk.cli import cli

K: int = 5  # overlap window size in characters


def test_cli_character_overlap(tmp_path: Path) -> None:
    """Assert that the CLI honours a *K*-character overlap window.

    Rationale
    ---------
    Overlap correctness is critical for downstream embedding alignment; an
    off‑by‑one error would propagate through the RAG pipeline and degrade
    retrieval recall. Testing through the public CLI surface catches
    mis‑configurations between CLI flags and the underlying splitter logic.

    Args
    ----
    tmp_path : pathlib.Path
        Temporary directory fixture supplied by **pytest** for writing all
        intermediate artefacts in isolation.

    Returns
    -------
    None

    Raises
    ------
    AssertionError
        If the CLI exits with a non‑zero status, produces no output file, or
        the overlap invariant (`chunks[i‑1][-K:] == chunks[i][:K]`) fails for
        any consecutive pair.

    Implementation Notes
    --------------------
    * The corpus pattern "abcde " simplifies manual visual inspection.
    * We require at least two chunks to avoid false‑positive success when the
      splitter accidentally emits a single chunk.
    """
    # ---------------- prepare a tiny text file ------------------------- #
    text = "abcde " * 40  # ~240 chars ensures multiple chunks
    source_file = tmp_path / "document.txt"
    source_file.write_text(text, encoding="utf-8")

    output_file = tmp_path / "out.jsonl"

    # ---------------- run CLI ------------------------------------------ #
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "run",
            str(source_file),
            "--strategy",
            "recursive",
            "--chunk-size",
            "25",
            "--chunk-overlap",
            str(K),
            "--overlap-unit",
            "characters",
            "--output",
            str(output_file),
        ],
    )
    assert result.exit_code == 0, result.output
    assert output_file.exists() and output_file.stat().st_size > 0

    # ---------------- validate overlap -------------------------------- #
    with jsonlines.open(output_file) as reader:
        chunks = [obj["text"] for obj in reader]

    # Must have split into more than one chunk
    assert len(chunks) >= 2

    # Each consecutive pair must share exactly *K* trailing/leading characters
    for i in range(1, len(chunks)):
        assert chunks[i - 1][-K:] == chunks[i][:K]
