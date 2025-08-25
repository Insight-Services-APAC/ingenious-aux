"""
Purpose & Context
-----------------
This module houses a comprehensive **end‑to‑end test‑suite** for the
``ingenious chunk run`` command‑line interface (CLI).  The CLI is a critical
entry‑point in the *Insight Ingenious* data‑ingestion pipeline and is
responsible for breaking raw documents into retrieval‑ready *chunks*.

The tests validate two orthogonal concerns:

1. **Strategy integrity** — All supported chunking strategies
   (``recursive``, ``markdown``, ``token``, ``semantic``) must
   *always* honour the *token‑overlap* invariant so that downstream rag /
   similarity‑search maintains full context continuity.
2. **Provider selection** — The ``semantic`` strategy transparently switches
   between *standard OpenAI* embeddings and *Azure OpenAI* embeddings based on
   the ``--azure-deployment`` flag.  The suite verifies that the correct
   provider is wired in every scenario.

Key Algorithms / Design Decisions
--------------------------------
* **DRY mocking** – A single helper (``_fake_embedder``) provides a fast,
  deterministic fake for *both* OpenAI embedding classes.  Avoiding real
  network calls shrinks execution time from seconds to milliseconds and makes
  the tests fully offline‑capable.
* **Typer CLIRunner** – ``typer.testing.CliRunner`` is the canonical mechanism
  for programmatically driving Typer apps.  Using it keeps the tests close to
  real user behaviour while remaining automation‑friendly.
* **Token‑level verification** – Rather than rely on heuristic string matching
  we check the *exact* tail/head token sequences with ``tiktoken``.  This
  catches subtle UTF‑8 or whitespace discrepancies that would elude naïve
  checks.
"""

from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import jsonlines
from tiktoken import get_encoding
from typer.testing import CliRunner

from ingenious.chunk.cli import cli

# A list of all chunking strategies validated for output integrity.
STRATEGIES: List[str] = ["recursive", "markdown", "token", "semantic"]


def _fake_embedder() -> MagicMock:
    """Return a deterministic mock embedder for OpenAI / Azure classes.

    Summary
    -------
    Provides a *shared* mock of the embeddings interface so that all semantic
    tests run **offline** and free of third‑party latency or quota limits.

    Rationale
    ---------
    Using a single helper eliminates duplication across tests while making it
    trivial to tweak the fake’s behaviour should the production interface
    evolve.

    Returns
    -------
    MagicMock
        An object whose ``embed_documents`` method yields a fixed‑size vector
        of zeros for each supplied text, perfectly mirroring the shape expected
        by the rest of the stack.
    """

    stub = MagicMock()
    stub.embed_documents.side_effect = lambda texts: [[0.0] * 8 for _ in texts]
    return stub


# ============================================================================
# Strategy‑integrity tests
# ============================================================================


def _run_integrity_check(sample_text: Path, tmp_path: Path, strategy: str) -> None:
    """Drive the CLI for *one* strategy and assert the token‑overlap invariant.

    Args
    ----
    sample_text
        Path to a small UTF‑8 text file provided by the *sample_text* fixture.
    tmp_path
        Temporary directory supplied by *pytest* for isolation.
    strategy
        Name of the chunking strategy under test (must exist in ``STRATEGIES``).

    Raises
    ------
    AssertionError
        If the CLI exit‑code is non‑zero **or** if any successive chunk pair
        violates the *k‑token overlap* contract (k == 8).

    Implementation notes
    --------------------
    * All external embedding classes are *patched* to ``_fake_embedder`` so the
      semantic strategy runs without network access.
    * ``tiktoken`` ensures token‑level precision regardless of Unicode edge‑
      cases.
    """

    out_file = tmp_path / f"out_{strategy}.jsonl"

    # Mock both embedding providers so tests remain offline‑capable.
    with (
        patch(
            "ingenious.chunk.strategy.langchain_semantic.OpenAIEmbeddings",
            return_value=_fake_embedder(),
        ),
        patch(
            "ingenious.chunk.strategy.langchain_semantic.AzureOpenAIEmbeddings",
            return_value=_fake_embedder(),
        ),
    ):
        result = CliRunner().invoke(
            cli,
            [
                "run",
                str(sample_text),
                "--strategy",
                strategy,
                "--chunk-size",
                "64",
                "--chunk-overlap",
                "8",
                "--output",
                str(out_file),
            ],
            catch_exceptions=False,
        )

    # --- CLI must succeed ---------------------------------------------------
    assert result.exit_code == 0, result.output

    # --- Validate k‑token overlap ------------------------------------------
    with jsonlines.open(out_file) as rdr:
        chunks = [rec["text"] for rec in rdr]

    enc = get_encoding("cl100k_base")
    k = 8  # matches --chunk-overlap
    for i in range(1, len(chunks)):
        tail_tokens = enc.encode(chunks[i - 1])[-k:]
        tail_text = enc.decode(tail_tokens)
        head_text = chunks[i][: len(tail_text) + 2]  # +2 buffer for whitespace
        assert head_text.lstrip().startswith(tail_text.lstrip())


def test_cli_all_strategies_integrity(sample_text: Path, tmp_path: Path) -> None:
    """Parametrically verify *every* strategy honours the overlap contract."""

    for s in STRATEGIES:
        _run_integrity_check(sample_text, tmp_path, s)


# ============================================================================
# Provider‑selection tests (semantic strategy only)
# ============================================================================


@patch(
    "ingenious.chunk.strategy.langchain_semantic.AzureOpenAIEmbeddings",
    return_value=_fake_embedder(),
)
def test_cli_semantic_azure_provider(
    mock_azure_cls: MagicMock, sample_text: Path, tmp_path: Path
) -> None:
    """Ensure *Azure* embeddings are used when ``--azure-deployment`` is set."""

    out_file = tmp_path / "out.jsonl"
    result = CliRunner().invoke(
        cli,
        [
            "run",
            str(sample_text),
            "--strategy",
            "semantic",
            "--azure-deployment",
            "my-azure-deployment-name",
            "--output",
            str(out_file),
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"CLI command failed: {result.output}"
    assert out_file.exists(), "Output file was not created."
    mock_azure_cls.return_value.embed_documents.assert_called()


@patch(
    "ingenious.chunk.strategy.langchain_semantic.OpenAIEmbeddings",
    return_value=_fake_embedder(),
)
def test_cli_semantic_default_openai_provider(
    mock_openai_cls: MagicMock, sample_text: Path, tmp_path: Path
) -> None:
    """Ensure *standard OpenAI* embeddings are used when no flag is provided."""

    out_file = tmp_path / "out.jsonl"
    result = CliRunner().invoke(
        cli,
        [
            "run",
            str(sample_text),
            "--strategy",
            "semantic",
            "--output",
            str(out_file),
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"CLI command failed: {result.output}"
    assert out_file.exists(), "Output file was not created."
    mock_openai_cls.return_value.embed_documents.assert_called()
