"""Insight Ingenious ‒ CLI token‑chunking separator test
======================================================

Purpose & context
-----------------
This *pytest* module verifies that the **Insight Ingenious** chunking CLI
(`ingenious.chunk.cli`) correctly honours a *custom* separator string when the
*recursive* chunk‑splitting strategy is selected.  Ensuring this behaviour is
critical because down‑stream RAG and embedding pipelines rely on deterministic,
loss‑less segmentation when users provide domain‑specific delimiters (e.g.
`"---"` in Markdown outline documents).

Key design choices
------------------
* **Typer `CliRunner`** is employed to invoke the CLI in an isolated
  subprocess‑free context, dramatically speeding‑up the test suite compared to
  spawning a shell.
* A *very small* `--chunk-size` (4 characters) is used to force the splitter to
  respect the separator rather than naïvely cutting mid‑token.
* **Immutable temp directories** – the `tmp_path` fixture guarantees each test
  runs in a fresh workspace, avoiding cross‑test artefacts.
"""

from pathlib import Path

import jsonlines
from typer.testing import CliRunner

from ingenious.chunk.cli import cli


def test_cli_respects_custom_separator(tmp_path: Path) -> None:
    """Validate that the CLI honours a custom separator.

    Rationale
    ---------
    A bespoke delimiter (here ``"---"``) is often embedded in domain texts to
    demarcate logical sections. The test crafts a contrived string
    ``"A---B---C---D---E"`` where each letter represents a semantic fragment.
    By imposing a *hard 4‑character budget* and *zero overlap*, the only way to
    achieve five discrete chunks is for the splitter to respect the delimiter.

    Args
    ----
    tmp_path : Path
        *pytest* fixture supplying an ephemeral directory used to write both the
        synthetic source file and the JSONL output. The path is unique per test
        invocation and is automatically cleaned‑up by *pytest*.

    Returns
    -------
    None
        The function uses *pytest* ``assert`` statements for verification and
        therefore returns nothing on success.

    Raises
    ------
    AssertionError
        If the CLI exits with a non‑zero status or the produced chunks do not
        match the expected sequence ``['A', 'B', 'C', 'D', 'E']``.

    Implementation notes
    --------------------
    * ``CliRunner.invoke`` captures stdout/stderr, enabling failure diagnostics
      without polluting test output when successful.
    * The **jsonlines** reader converts each object stream back into a list for
      simple equality comparison.
    """

    # --- Arrange ------------------------------------------------------------
    text = "A---B---C---D---E"
    src = tmp_path / "src.txt"
    src.write_text(text)

    out_file = tmp_path / "out.jsonl"
    runner = CliRunner()

    # --- Act ----------------------------------------------------------------
    result = runner.invoke(
        cli,
        [
            "run",
            str(src),
            "--strategy",
            "recursive",
            "--chunk-size",
            "4",  # small char budget forces respect for separator
            "--chunk-overlap",
            "0",
            "--overlap-unit",
            "characters",
            "--separators",
            "---",
            "--output",
            str(out_file),
        ],
        catch_exceptions=False,  # surface CLI errors directly in the test log
    )

    # --- Assert -------------------------------------------------------------
    assert result.exit_code == 0, result.output

    with jsonlines.open(out_file) as rdr:
        chunks = [rec["text"] for rec in rdr]

    # Expect exactly 5 chunks: A, B, C, D, E (minus separator chars)
    assert [c.strip("-") for c in chunks] == ["A", "B", "C", "D", "E"]
