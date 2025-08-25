"""
Tests for the source path normalization utility.

Purpose & Context
-----------------
This module contains the unit tests for the `_norm_source` utility function
located in `ingenious.chunk.utils.id_path`. This function is a core component
of the data ingestion pipeline, responsible for converting raw file paths into
stable, consistent, and configuration-driven source identifiers for "chunks".

The choice of identifier format is governed by the `id_path_mode` setting in
the `ChunkConfig` object, which supports absolute paths (`abs`), project-relative
paths (`rel`), or obfuscated hashes (`hash`). These tests ensure that each mode
behaves as expected under various conditions, which is critical for data
provenance, debugging, and deduplication within the Insight Ingenious multi-agent
framework.

Key Algorithms / Design Choices
-------------------------------
The test suite is structured using pytest and is organized by the `id_path_mode`
being tested.

- **Isolation**: It heavily relies on the `tmp_path` fixture to create isolated,
  temporary file systems for each test, ensuring that tests do not interfere
  with each other or the host system.
- **Environment Simulation**: The `monkeypatch` fixture is used to simulate
  changes in the environment, such as modifying the current working directory
  (`CWD`), to test context-dependent behaviors.
- **Robustness**: Assertions for hash digest lengths are not hard-coded. They
  are dynamically calculated from the configuration (`cfg.id_hash_bits // 4`)
  to ensure the tests remain valid even if the default hash bit length is
  changed in future versions (see ticket M-4).
"""

from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch

from ingenious.chunk.config import ChunkConfig
from ingenious.chunk.utils.id_path import _norm_source

# --------------------------------------------------------------------------- #
# Helper – common expectations
# --------------------------------------------------------------------------- #
_HEX = set("0123456789abcdef")


def _is_hex(s: str) -> bool:
    """Checks if a string consists solely of lowercase hexadecimal characters.

    Rationale:
        This is a simple, efficient helper for validating hash outputs in
        multiple tests. Using set operations is Pythonic and performant for
        this kind of membership check.

    Args:
        s: The string to validate.

    Returns:
        True if the string contains only characters from '0'-'9' and 'a'-'f',
        False otherwise.
    """
    return set(s) <= _HEX


# --------------------------------------------------------------------------- #
# 1. abs-mode – must round-trip the absolute path verbatim
# --------------------------------------------------------------------------- #
def test_abs_mode(tmp_path: Path) -> None:
    """Verifies `_norm_source` returns a POSIX-style absolute path in 'abs' mode.

    Rationale:
        This test ensures that when users configure the system for absolute paths
        (e.g., for maximum clarity in local debugging), the function correctly
        resolves and formats the path. Using POSIX-style paths (`/`) ensures
        cross-platform consistency for identifiers.

    Args:
        tmp_path: The pytest fixture for a temporary directory path.
    """
    src = tmp_path / "foo.txt"
    cfg = ChunkConfig(id_path_mode="abs")

    assert _norm_source(src, cfg) == src.resolve().as_posix()


# --------------------------------------------------------------------------- #
# 2. rel-mode – default id_base is CWD
# --------------------------------------------------------------------------- #
def test_rel_mode_default_base(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Verifies 'rel' mode creates a CWD-relative path if `id_base` is unset.

    Rationale:
        This tests the default, user-friendly behavior of 'rel' mode. By using
        the current working directory (CWD) as the default `id_base`, the
        system generates human-readable identifiers for common use cases (e.g.,
        processing a local project) without requiring explicit configuration.

    Args:
        tmp_path: The pytest fixture for a temporary directory path.
        monkeypatch: The pytest fixture for modifying classes or functions.

    Implementation Notes:
        The `monkeypatch.chdir()` function is used to reliably set the CWD
        to the parent of the temporary test directory. This creates a
        predictable scenario where the source file is guaranteed to be inside
        the CWD, allowing for a stable assertion on the relative path.
    """
    src = tmp_path / "bar.txt"

    # Simulate running the CLI from the project root (parent of tmp_path)
    monkeypatch.chdir(tmp_path.parent)  # Path.cwd() <- parent directory

    cfg = ChunkConfig(id_path_mode="rel")

    assert _norm_source(src, cfg) == f"{tmp_path.name}/bar.txt"


# --------------------------------------------------------------------------- #
# 3. rel-mode – custom id_base
# --------------------------------------------------------------------------- #
def test_rel_mode_custom_base(tmp_path: Path) -> None:
    """Verifies 'rel' mode respects a custom `id_base`.

    Rationale:
        This test confirms that users can specify an arbitrary directory as the
        root for relative paths. This functionality is essential for projects
        where processed files are located in a structure that is not directly
        relative to the current working directory.

    Args:
        tmp_path: The pytest fixture for a temporary directory path.
    """
    base = tmp_path / "project"
    base.mkdir()

    src = base / "data" / "doc.md"
    src.parent.mkdir()  # create 'data/'

    cfg = ChunkConfig(id_path_mode="rel", id_base=base)

    assert _norm_source(src, cfg) == "data/doc.md"


# --------------------------------------------------------------------------- #
# 4. hash-mode – always a salted digest
# --------------------------------------------------------------------------- #
def test_hash_mode(tmp_path: Path) -> None:
    """Verifies 'hash' mode always returns a salted hex digest of correct length.

    Rationale:
        The 'hash' mode is critical for scenarios requiring anonymization or
        path obfuscation for privacy or security. This test validates that the
        output is always a hash and that its length correctly corresponds to
        the `id_hash_bits` configuration setting.

    Args:
        tmp_path: The pytest fixture for a temporary directory path.

    Implementation Notes:
        The test is designed to be robust against future changes. It
        dynamically calculates the expected hexadecimal length from the
        `cfg.id_hash_bits` value (1 hex char = 4 bits) rather than using a
        hard-coded length.
    """
    src = tmp_path / "secret.txt"
    cfg = ChunkConfig(id_path_mode="hash")

    out = _norm_source(src, cfg)

    expected_len = cfg.id_hash_bits // 4
    assert len(out) == expected_len
    assert _is_hex(out)


# --------------------------------------------------------------------------- #
# 5. rel-mode – two same-name files outside id_base must not collide
# --------------------------------------------------------------------------- #
def test_rel_mode_hash_on_outside_base(tmp_path: Path) -> None:
    """Verifies 'rel' mode falls back to hashing for paths outside `id_base`.

    Rationale:
        This test checks the critical fallback mechanism of 'rel' mode. When a
        source file is outside the designated base directory, generating a
        relative path is impossible or meaningless. The function must fall back
        to the secure hashing mechanism to produce a stable, non-colliding
        identifier and avoid runtime errors.

    Args:
        tmp_path: The pytest fixture for a temporary directory path.

    Implementation Notes:
        To test for collision avoidance, two files with the same name
        (`dup.txt`) are created in different directories. Both directories are
        outside the configured `id_base`. The core assertion `h1 != h2`
        verifies that the hash is salted with the full path, not just the
        filename, preventing identifier collisions.
    """
    # Prepare two directories, each containing a file called 'dup.txt'
    src1 = tmp_path / "dirA" / "dup.txt"
    src2 = tmp_path / "dirB" / "dup.txt"
    src1.parent.mkdir()
    src2.parent.mkdir()
    src1.write_text("a")
    src2.write_text("b")

    cfg = ChunkConfig(id_path_mode="rel", id_base=tmp_path / "dirC")  # unrelated base
    h1 = _norm_source(src1, cfg)
    h2 = _norm_source(src2, cfg)

    expected_len = cfg.id_hash_bits // 4

    # The digests must differ and respect the expected size/charset
    assert h1 != h2
    assert len(h1) == len(h2) == expected_len
    assert _is_hex(h1) and _is_hex(h2)
