"""
Implements the central registry for all text chunking strategies.

Purpose & Context
-----------------
This module provides the plug-in loading and registration mechanism for text chunking
strategies within the Insight Ingenious framework. It dynamically discovers and
registers different splitting algorithms (e.g., "recursive", "semantic", "token"),
making them available to the rest of the application through a central factory.

This design decouples the core application logic from the specific chunking
implementations. To add a new strategy, a developer simply needs to add a new
Python module to this directory and use the ``@register`` decorator; no changes
are needed in this file or in consumer code.

Key Algorithms & Design Choices
-------------------------------
1.  **Registry Pattern**: The core of the system is the ``_SPLITTER_REGISTRY``, a
    simple dictionary that maps strategy names to their factory functions. This is
    an effective and lightweight implementation of the service registry pattern.
2.  **Decorator-Based Registration**: Strategies self-register using the
    ``@register("name")`` decorator. This provides an elegant, declarative, and
    decentralized way for plug-ins to announce themselves, avoiding a manually
    maintained central list and reducing the risk of merge conflicts.
3.  **Dynamic Discovery via Auto-Import**: The key to the plug-in system is the
    auto-import loop at the end of this file. By programmatically importing all
    sibling modules, it ensures that their ``@register`` decorators are executed
    when the ``ingenious.chunk.strategy`` package is first imported. This makes
    the entire registration process automatic and highly extensible.

Usage Example
-------------
This module is used internally by the ``ingenious.chunk.factory``. A developer
would typically interact with it indirectly by building a splitter.

.. code-block:: python

    from ingenious.chunk.config import ChunkConfig
    from ingenious.chunk.factory import build_splitter

    # The `build_splitter` function uses this module's registry to find the
    # factory associated with the given strategy name.

    # 1. Request the "recursive" strategy
    recursive_config = ChunkConfig(strategy="recursive", chunk_size=1000)
    recursive_splitter = build_splitter(recursive_config)

    # 2. Request the "semantic" strategy
    semantic_config = ChunkConfig(strategy="semantic", chunk_overlap=50)
    semantic_splitter = build_splitter(semantic_config)

    # 3. Adding a new strategy (e.g., "new_strategy.py") makes it available:
    # new_config = ChunkConfig(strategy="new_strategy", ...)
    # new_splitter = build_splitter(new_config)

"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict

from ..config import ChunkConfig

if TYPE_CHECKING:
    from langchain_text_splitters.base import TextSplitter

# The private registry mapping strategy names to their factory functions.
_SPLITTER_REGISTRY: Dict[str, Callable[[ChunkConfig], "TextSplitter"]] = {}


def register(
    name: str,
) -> Callable[
    [Callable[[ChunkConfig], "TextSplitter"]], Callable[[ChunkConfig], "TextSplitter"]
]:
    """A decorator that registers a chunking strategy factory function.

    Rationale:
        Using a decorator provides a clean, declarative syntax for plug-in modules
        to register themselves. This avoids the need for a central, manually edited
        list of strategies, making the system more extensible and less prone to
        merge conflicts.

    Args:
        name: The unique public name for the strategy (e.g., "recursive", "token").

    Returns:
        A decorator function that accepts a factory, registers it, and returns it.

    Implementation Notes:
        This is a higher-order function. It is called with the strategy name and
        returns an inner function (`_decorator`). This inner function is the actual
        decorator that performs the registration in the `_SPLITTER_REGISTRY`.
    """

    def _decorator(
        fn: Callable[[ChunkConfig], "TextSplitter"],
    ) -> Callable[[ChunkConfig], "TextSplitter"]:
        _SPLITTER_REGISTRY[name] = fn
        return fn

    return _decorator


def get(name: str) -> Callable[[ChunkConfig], "TextSplitter"]:
    """Retrieves a registered chunking strategy factory by its public name.

    Rationale:
        This function provides a controlled access point to the registry,
        abstracting the dictionary implementation from consumers. It includes robust
        error handling to provide clear, actionable feedback when a requested
        strategy is not available.

    Args:
        name: The name of the strategy to retrieve.

    Returns:
        The factory function associated with the requested name.

    Raises:
        ValueError: If no strategy with the given name has been registered.
    """
    try:
        return _SPLITTER_REGISTRY[name]
    except KeyError as exc:
        raise ValueError(f"Unknown chunking strategy: '{name}'") from exc


# --- Auto-import sibling modules to execute their @register decorators ---
# This loop is the core of the dynamic plug-in system. It runs when the
# `ingenious.chunk.strategy` package is first imported, ensuring the registry
# is populated before it is ever used.
_current_directory = Path(__file__).parent
for module_path in _current_directory.glob("*.py"):
    if module_path.stem not in {"__init__"}:
        import_module(f"{__name__}.{module_path.stem}")
