"""
Tests for CLI resilience to OpenAI API network failures.

Purpose & Context
-----------------
This test module ensures the robustness of the `ingenious.chunk.cli` command-line
interface against network-related exceptions raised by the OpenAI API client.
When processing documents with the 'semantic' strategy, the CLI calls the
OpenAI embeddings endpoint. If this call fails due to timeouts, DNS issues, or
server-side errors (5xx), the CLI should not crash with an unhandled traceback.
Instead, it must exit cleanly with a non-zero status code and provide clear
user feedback.

This suite validates that behaviour, ensuring that data processing pipelines
which rely on the chunking CLI are resilient to transient external service
failures. It is a critical part of the test coverage for the core
`ingenious/chunk` module.

Key Algorithms & Design Choices
-------------------------------
The primary challenge this test addresses is the variation in exception
constructor signatures across different versions of the `openai` Python library
(e.g., v0.x vs. v1.x). To create a version-agnostic test suite, this module
uses a helper function, `_instantiate`, which attempts multiple strategies
(common constructor patterns, signature introspection) to create an instance of
a given exception class. This design makes the tests resilient to SDK upgrades.

Tests are parameterized using `pytest.mark.parametrize` to efficiently cover a
range of critical network exceptions like `APITimeoutError` and
`APIConnectionError`.
"""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ingenious.chunk.cli import cli

# ---------------------------------------------------------------------------#
# Helper – build a dummy instance even when __init__ has exotic signature   #
# ---------------------------------------------------------------------------#


def _instantiate(exc_cls: type[BaseException]) -> BaseException:
    """Robustly instantiates an exception class without knowing its __init__ signature.

    Rationale:
        The `openai` library has changed its exception constructor signatures
        between major versions (e.g., v0.x vs. v1.x). Hardcoding a specific
        instantiation like `exc(message='...')` would make these tests brittle
        and likely to break upon dependency updates. This helper ensures test
        stability by trying several common instantiation patterns in a cascade,
        making the test suite resilient to SDK upgrades.

    Args:
        exc_cls: The exception class to instantiate.

    Returns:
        An instance of the `exc_cls`.

    Implementation Notes:
        The function attempts four strategies in order of preference:
        1. A single positional string argument: `exc_cls("simulated")`.
        2. Common keyword arguments: `exc_cls(message="...", request=...)`.
        3. Signature introspection to fill all required params with `None`.
        4. Bypassing `__init__` via `__new__` as a last resort.
        This cascade covers most known signatures for `openai` API exceptions.
    """
    # 1. Single positional argument
    try:
        return exc_cls("simulated")
    except Exception:
        pass

    # 2. Common keyword arguments seen in OpenAI error types
    try:
        # Use type: ignore as signature is unknown and may cause mypy errors.
        return exc_cls(message="simulated", request=None)  # type: ignore[call-arg]
    except Exception:
        pass

    # 3. Introspect signature and supply None for every required parameter
    try:
        sig = inspect.signature(exc_cls)
        kwargs: Dict[str, Any] = {
            name: None
            for name, p in sig.parameters.items()
            if p.default is inspect.Parameter.empty
            and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
        }
        return exc_cls(**kwargs)  # type: ignore[arg-type]
    except Exception:
        pass

    # 4. Bypass __init__ entirely as a final fallback
    return exc_cls.__new__(exc_cls)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------#
# Parameterisation over available OpenAI exception classes                   #
# ---------------------------------------------------------------------------#
openai_mod = importlib.import_module("openai")
EXC_NAMES = ["APITimeoutError", "APIConnectionError", "ServiceUnavailableError"]
# Fallback to RuntimeError if an exception class is not found in the installed
# version of the openai library, preventing test collection failures.
EXC_TYPES = [getattr(openai_mod, n, RuntimeError) for n in EXC_NAMES]


@pytest.mark.parametrize("exc_type", EXC_TYPES)
@patch("ingenious.chunk.strategy.langchain_semantic.OpenAIEmbeddings")
def test_cli_network_failures(
    mock_embed: MagicMock,
    exc_type: type[BaseException],
    sample_text: Path,
    tmp_path: Path,
) -> None:
    """Verifies the CLI exits gracefully when the embedding service fails.

    Rationale:
        This test ensures a core user-facing tool (`ingenious chunk run`)
        provides clear feedback and a non-zero exit code upon network failures.
        This is crucial for CI/CD scripting and automated workflows, as it
        prevents silent failures or unhandled stack traces. The test validates
        that our global exception handler in the Typer CLI application is
        working as specified in DI-101.

    Args:
        mock_embed: A `MagicMock` object patching the `OpenAIEmbeddings` class.
        exc_type: The specific OpenAI exception to simulate, parameterized by
            `pytest.mark.parametrize`.
        sample_text: A pytest fixture providing a `pathlib.Path` to a sample
            text file for processing.
        tmp_path: A pytest fixture providing a temporary directory `pathlib.Path`
            for storing output files.

    Implementation Notes:
        The test works by mocking the `OpenAIEmbeddings` client at the point of
        import within our semantic chunking strategy. The mock's `embed_documents`
        method is configured with a `side_effect` that raises an instance of the
        parameterized exception `exc_type`. The test then invokes the CLI using
        `typer.testing.CliRunner` and asserts two conditions:
        1. The process exit code is 1 (indicating failure).
        2. The user-friendly error symbol (`❌`) is present in the STDERR/STDOUT,
           confirming our custom exception handler was triggered.
    """
    stub = MagicMock()
    stub.embed_documents.side_effect = _instantiate(exc_type)
    mock_embed.return_value = stub

    runner = CliRunner()
    result = runner.invoke(
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

    assert result.exit_code == 1, "CLI should exit with status code 1 on error."
    assert "❌" in result.output, "Error message should be prefixed with the ❌ symbol."
