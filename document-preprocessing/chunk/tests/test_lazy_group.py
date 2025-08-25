"""
Tests for the LazyGroup utility for Typer-based CLIs.

Purpose & Context:
    This module contains unit tests for the `ingenious.utils.lazy_group.LazyGroup`
    class. `LazyGroup` is a custom `typer.Typer` subclass designed to solve a
    common problem in extensible applications: handling optional command groups
    whose dependencies may not be installed.

    In the Insight Ingenious architecture, features like data chunking (`chunk`) are
    packaged as optional extras (`pip install ingenious[chunk]`). `LazyGroup` allows
    the main CLI to register the `chunk` command without immediately importing its
    code. The import is deferred until a user actually invokes `ingenious chunk`.
    If the import fails (because the extra is not installed), `LazyGroup` catches
    the `ModuleNotFoundError` and presents a user-friendly message instead of a
    stack trace.

Key Algorithms / Design Choices:
    The tests leverage `pytest`'s `monkeypatch` fixture to simulate the
    `ModuleNotFoundError` that occurs when an optional dependency is missing.
    This is a robust and standard testing technique that allows us to verify the
    exception-handling logic of `LazyGroup` in isolation, without needing complex
    setup or manipulation of the Python environment (`sys.path`).
"""

import importlib
from types import ModuleType
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from ingenious.utils.lazy_group import LazyGroup


def test_lazy_group_missing_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies LazyGroup prints a helpful error if a command's module is missing.

    Rationale:
        This test validates the primary purpose of `LazyGroup`: to provide a
        graceful failure mode when a user tries to invoke a command from an
        uninstalled optional extra. Instead of a raw `ModuleNotFoundError`
        traceback, the user should receive a clear, actionable instruction to
        install the necessary package. Monkeypatching `importlib` is the most
        direct and reliable way to simulate this failure condition in a unit test.

    Args:
        monkeypatch (pytest.MonkeyPatch): The pytest fixture used to dynamically
            replace the `import_module` function during the test.

    Returns:
        None

    Raises:
        AssertionError: If the test's assertions about exit code or output fail.

    Implementation Notes:
        - A fake `import_module` function is created to raise `ModuleNotFoundError`
          specifically when the test attempts to import the subcommand's module.
        - A minimal Typer app is constructed using `LazyGroup` as its group class.
        - The `CliRunner` invokes the app with an argument corresponding to the
          missing subcommand ('chunk').
        - The test asserts that the process exits with a non-zero status code (1)
          and that the output contains the expected user-friendly error message.
    """

    def _fake_import(name: str, *args: Any, **kwargs: Any) -> ModuleType:
        """A patched import_module that fails for the chunk CLI module."""
        if name == "ingenious.chunk.cli":
            raise ModuleNotFoundError(f"No module named '{name}'")
        return importlib.import_module(name)

    monkeypatch.setattr(importlib, "import_module", _fake_import)

    # A minimal Typer app to simulate the main `ingenious` CLI application.
    # The `cls=LazyGroup` is the critical piece under test.
    app = typer.Typer(cls=LazyGroup)

    # A dummy callback is required for typer.testing.CliRunner to correctly
    # build the underlying Click command object for invocation.
    @app.callback()
    def _root() -> None:
        pass

    runner = CliRunner()
    result = runner.invoke(app, ["chunk"])

    assert result.exit_code == 1, "App should exit with code 1 on import failure."
    assert "[chunk] extra not installed" in result.output.lower(), (
        "Output should contain the helpful installation message for the '[chunk]' extra."
    )
