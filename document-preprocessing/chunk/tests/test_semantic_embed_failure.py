"""
Tests for the chunking CLI (`ingenious.chunk.cli`).

Purpose & Context:
    This module contains pytest unit tests for the command-line interface of the
    `ingenious.chunk` sub-package. The primary function of the chunking CLI is to
    provide a user-facing tool for splitting large documents into smaller,
    semantically meaningful pieces suitable for processing by RAG pipelines or
    other LLM-based agents within the Insight Ingenious architecture. This test
    suite ensures the CLI's robustness, correct argument parsing, and graceful
    handling of runtime errors, such as failures in external services like
    embedding providers.

Key Algorithms / Design Choices:
    The tests leverage the `typer.testing.CliRunner` to invoke the CLI programmatically
    and inspect its output and exit codes. This approach isolates the CLI from the
    rest of the system for focused testing.

    Dependencies on external services, specifically the `OpenAIEmbeddings` client,
    are managed using `unittest.mock.patch`. This allows for simulating various
    scenarios, including API failures (e.g., rate-limiting), without making actual
    network calls, ensuring tests are fast, deterministic, and can run in offline
    CI/CD environments.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from ingenious.chunk.cli import cli


class _Boom(Exception):
    """A private exception used to simulate a controlled failure in mocks."""

    pass


@patch("ingenious.chunk.strategy.langchain_semantic.OpenAIEmbeddings")
def test_cli_handles_embedding_failure(
    mock_embed: MagicMock, tmp_path: Path, sample_text: Path
) -> None:
    """Verifies the CLI exits gracefully when the embedding service fails.

    Rationale:
        This test ensures the application is robust against common, real-world
        failures from third-party APIs (e.g., network issues, rate limits, or
        authentication errors). By simulating an exception during the embedding
        process, we confirm that the CLI's top-level error handling correctly
        catches the exception, reports a meaningful error to the user via stdout/stderr,
        and exits with a non-zero status code. This prevents silent failures and
        provides a good user experience, aligning with DI-101.

    Args:
        mock_embed: A `MagicMock` object injected by `@patch` that replaces the
            `OpenAIEmbeddings` class.
        tmp_path: A `pytest` fixture providing a temporary directory (`pathlib.Path`)
            for writing test outputs.
        sample_text: A `pytest` fixture providing the path (`pathlib.Path`) to a
            sample input text file.

    Returns:
        None. This is a test function and relies on `assert` statements.

    Raises:
        AssertionError: If the test fails its validation checks.

    Implementation Notes:
        - The `_Boom` private exception is used to ensure we are catching the
          specific failure we triggered, not another unexpected `Exception`.
        - The mock is configured to raise this exception when its `embed_documents`
          method is called.
        - The test asserts two conditions:
            1. The exit code is non-zero, signaling failure to the shell.
            2. The specific error message ("rate-limit") is present in the CLI's
               output, confirming that the error was propagated to the user.
    """
    stub = MagicMock()
    stub.embed_documents.side_effect = _Boom("rate‑limit")
    mock_embed.return_value = stub

    res = CliRunner().invoke(
        cli,
        [
            "run",
            str(sample_text),
            "--strategy",
            "semantic",
            "--chunk-size",
            "64",
            "--chunk-overlap",
            "8",
            "--output",
            str(tmp_path / "out.jsonl"),
        ],
    )

    assert res.exit_code != 0
    assert "rate‑limit" in res.output.lower()
