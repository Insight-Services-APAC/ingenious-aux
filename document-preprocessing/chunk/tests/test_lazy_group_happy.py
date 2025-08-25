"""
Tests for the LazyGroup CLI command loader.

This module contains tests for the `ingenious.utils.lazy_group.LazyGroup` class,
which is a core component of the Insight Ingenious CLI architecture.

Purpose & Context
-----------------
The `LazyGroup` class allows the main `ingen` CLI to define subcommands (like
`chunk` or `scan`) that are loaded on-demand from optional extras. This
prevents `ImportError` exceptions and reduces application startup time if a
user has not installed a specific extension (e.g., via `pip install .[chunk]`).
These tests verify that the loading mechanism works correctly under various
conditions.

Key Algorithms & Design Choices
-------------------------------
The tests heavily rely on `pytest`'s `monkeypatch` fixture to simulate the
presence or absence of extension modules in `sys.modules`. This is a critical
design choice, as it makes the tests fast and self-contained, avoiding the need
for slow, stateful, and complex virtual environment manipulations or actual
package installations during the CI/CD pipeline.
"""

import sys
from types import ModuleType
from typing import TYPE_CHECKING

import typer
from typer.testing import CliRunner

from ingenious.utils.lazy_group import LazyGroup

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def test_lazy_group_happy_path(monkeypatch: "MonkeyPatch") -> None:
    """Verifies LazyGroup successfully executes a subcommand when its module is available.

    Rationale:
        This is the primary "smoke test" for the lazy-loading mechanism. It
        confirms that the core logic—resolving a command name to a module,
        importing it, and dispatching the call—works as intended in the ideal
        case. Using `monkeypatch` makes the test fast and isolated, avoiding
        any dependency on the actual `[chunk]` extra being installed.

    Args:
        monkeypatch: The pytest fixture used to modify `sys.modules`,
            simulating the presence of the `ingenious.chunk.cli` module.

    Returns:
        None. The function uses `assert` to signal test success or failure.

    Implementation Notes:
        The test is structured in four clear steps:
        1.  **Build a dummy sub-CLI:** A minimal `Typer` app (`sub_app`) is
            created to stand in for the real `ingen chunk` command group.
            A no-op callback (`_sub_root`) is included to ensure `Typer`
            treats it as a `click.Group`, mirroring the real CLI's structure.
        2.  **Simulate installation:** `monkeypatch.setitem` injects the dummy
            module into `sys.modules`. This is the key trick that makes
            `import ingenious.chunk.cli` succeed within the `LazyGroup`.
        3.  **Instantiate LazyGroup:** A root `Typer` app is created using
            `cls=LazyGroup` to activate the custom loading behavior.
        4.  **Invoke and assert:** The `CliRunner` invokes the `chunk ping`
            command, and assertions verify the correct exit code and output.
    """
    # ── 1. Build a dummy sub-CLI to represent `ingenious.chunk.cli` ───────
    sub_app = typer.Typer()

    # A no-op callback forces Typer to create a click.Group, which is
    # necessary for LazyGroup's discovery to work correctly. Without this,
    # a single-command app would be collapsed into a plain click.Command.
    @sub_app.callback()
    def _sub_root() -> None:  # noqa: D401
        """no-op – keeps sub_app a group"""

    @sub_app.command()
    def ping() -> None:  # noqa: D401
        """Emit a friendly pong."""
        typer.echo("pong")

    # Build a synthetic module and attach the Typer app.
    dummy_mod = ModuleType("ingenious.chunk.cli")
    setattr(dummy_mod, "cli", sub_app)

    # ── 2. Pretend the `chunk` extra is installed by patching sys.modules ──
    monkeypatch.setitem(sys.modules, "ingenious.chunk.cli", dummy_mod)

    # ── 3. Root Typer application that uses LazyGroup ─────────────────────
    root = typer.Typer(cls=LazyGroup)

    @root.callback()
    def _root() -> None:
        """no-op"""

    # ── 4. Invoke "chunk ping" and assert success ─────────────────────────
    runner = CliRunner()
    result = runner.invoke(root, ["chunk", "ping"])
    assert result.exit_code == 0, f"CLI command failed with output:\n{result.output}"
    assert "pong" in result.output
