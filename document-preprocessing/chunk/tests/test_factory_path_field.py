"""
Tests for the text splitter factory in the Insight Ingenious framework.

Purpose & Context:
    This test module ensures the reliability and correctness of the splitter factory,
    located at `ingenious.chunk.factory.build_splitter`. The factory pattern is a
    core design principle in the Insight Ingenious architecture, allowing for the
    decoupled and configurable creation of components. In this case, it constructs
    text splitter instances based on a `ChunkConfig` object. These tests validate
    that the factory can handle various configurations, including complex data types
    that might arise from Pydantic model validation.

Key Algorithms / Design Choices:
    The primary design choice under test is the interaction between the Pydantic-based
    `ChunkConfig` and the `build_splitter` factory. Specifically, `ChunkConfig`
    employs validators that can dynamically inject non-primitive objects, such as
    `pathlib.Path`, into the configuration. The tests in this module verify that
    the factory is robust enough to handle these objects without serialization or
    type-checking errors.
"""

from pathlib import Path

from ingenious.chunk.config import ChunkConfig
from ingenious.chunk.factory import build_splitter


def test_factory_handles_path_field() -> None:
    """Verifies `build_splitter` correctly handles `ChunkConfig` with `pathlib.Path`.

    Rationale:
        The `ChunkConfig` model uses a Pydantic validator to inject a
        `pathlib.Path` object representing the current working directory when
        `id_path_mode` is set to "rel". This test ensures that the factory
        logic, which may involve serialization or deep copying of the config, is
        compatible with this non-primitive `Path` type. It's a regression test
        to prevent future changes in the factory from breaking this behavior.

    Args:
        None

    Returns:
        None

    Raises:
        AssertionError: If the splitter object is not created successfully.

    Implementation Notes:
        This is a smoke test designed to confirm that object instantiation does
        not raise an unexpected exception (e.g., `TypeError`, `ValidationError`).
        It does not inspect the internal state of the returned `splitter`, as
        other unit tests are responsible for verifying the splitter's functional
        behavior.
    """
    # The Pydantic validator on ChunkConfig is expected to inject `id_base_path`
    # as `Path.cwd()` when `id_path_mode` is "rel".
    cfg = ChunkConfig(id_path_mode="rel", id_base_path=Path.cwd())
    splitter = build_splitter(cfg)  # Should not raise an exception.
    assert splitter is not None
