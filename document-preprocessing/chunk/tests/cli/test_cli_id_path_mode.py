"""
End-to-end tests for the chunker CLI's ID path generation modes.

Purpose & Context
-----------------
This module provides end-to-end tests for the `ingen chunk run` command, a core
component of the Insight Ingenious data ingestion pipeline. Specifically, it
validates the three distinct behaviors of the `--id-path-mode` option: `rel`,
`hash`, and `abs`.

Correct and predictable chunk ID generation is critical for data provenance,
deduplication, and content retrieval within the broader multi-agent framework.
These tests ensure that the chunk ID prefix (the part identifying the source
document) is generated correctly based on the source file's location relative
to a base directory or the current working directory.

Key Algorithms / Design Choices
-------------------------------
The tests are designed as end-to-end (E2E) validations rather than isolated
unit tests. They use the `typer.testing.CliRunner` to invoke the actual CLI
application as a subprocess. This approach was chosen because it verifies the
entire stack, including:
- Command-line argument parsing and validation by Typer.
- Configuration loading and application (e.g., `ChunkConfig.id_hash_bits`).
- The core normalization logic in `ingenious.chunk.utils.id_path._norm_source`.
- The final output formatting by the JSONL writer.

This provides higher confidence in the user-facing behavior compared to testing
the normalization function in isolation.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import jsonlines
from typer.testing import CliRunner

from ingenious.chunk.cli import cli
from ingenious.chunk.config import ChunkConfig  # ← for dynamic hash-length

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
# Hash prefix length expected by *default* configuration.
HEX_LEN = ChunkConfig().id_hash_bits // 4  # e.g. 64 bits → 16 hex

HEX_CHARS = set("0123456789abcdef")  # Quick membership test for hex strings.


# --------------------------------------------------------------------------- #
# Helper – one-shot execution of the CLI
# --------------------------------------------------------------------------- #
def _run_once(src: Path, mode: str, base: str | None, out: Path) -> str:
    """Invokes `ingen chunk run` once and returns the ID prefix of the first chunk.

    Rationale:
        This helper centralizes the boilerplate logic for invoking the CLI via
        `CliRunner`. By encapsulating argument setup, execution, success
        assertion, and result parsing, it keeps the individual test cases
        significantly more concise, readable, and focused on their specific
        validation logic.

    Args:
        src: Path to the source file to be chunked.
        mode: The `id-path-mode` to test (`rel`, `hash`, or `abs`).
        base: The `--id-base` directory path, or `None` if not used.
        out: The path for the output JSONL file.

    Returns:
        The ID prefix (the part before the "#" separator) of the first chunk.

    Raises:
        AssertionError: If the `CliRunner` invocation returns a non-zero exit
            code, which indicates a CLI failure.

    Implementation Notes:
        The function parses only the *first* chunk from the output file. This
        is a safe and efficient assumption because the ID prefix (path or hash)
        is guaranteed to be identical for all chunks generated from the same
        source file in a single run.
    """
    cmd = [
        "run",
        str(src),
        "--chunk-size",
        "12",
        "--chunk-overlap",
        "4",
        "--id-path-mode",
        mode,
        "--output",
        str(out),
    ]

    if base:
        cmd += ["--id-base", base]

    # `abs` mode requires an explicit acknowledgement flag.
    if mode == "abs":
        cmd += ["--force-abs-path"]

    res = CliRunner().invoke(cli, cmd, catch_exceptions=False)
    assert res.exit_code == 0, res.output

    with jsonlines.open(out) as rdr:
        first = next(iter(rdr))
    return first["id"].split("#")[0]


# --------------------------------------------------------------------------- #
# 1. rel-mode – digest *outside* base, path *inside* base
# --------------------------------------------------------------------------- #
def test_rel_mode_stable_across_locations(tmp_path: Path, monkeypatch) -> None:
    """Verifies `rel` mode creates a hash outside a base and a path inside.

    Rationale:
        This test confirms the core conditional behavior of the default `rel`
        mode. This mode is designed to provide human-readable, portable IDs for
        files within a known project context (e.g., a Git repository,
        represented by `id_base` or CWD) while generating stable,
        location-independent hashes for all other files. This hybrid approach
        balances readability and robustness.

    Args:
        tmp_path: The pytest fixture for a temporary directory.
        monkeypatch: The pytest fixture for modifying runtime behavior.

    Returns:
        None
    """
    # 1️⃣ Arrange: Create a source file in a generic temporary location.
    src = tmp_path / "alpha.txt"
    src.write_text("lorem ipsum")

    # Act: Run chunker on the file, which is "outside" any logical project root.
    pref_outside = _run_once(src, "rel", None, tmp_path / "out1.jsonl")

    # Assert: The prefix should be a hex digest of the default length.
    assert len(pref_outside) == HEX_LEN
    assert set(pref_outside) <= HEX_CHARS

    # 2️⃣ Arrange: Create a "repo" directory and a file of the same name inside it.
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / src.name).write_text("lorem ipsum")
    monkeypatch.chdir(repo)  # Set the CWD to the repo root.

    # Act: Run the chunker from inside the repo.
    pref_inside = _run_once(repo / src.name, "rel", None, tmp_path / "out2.jsonl")

    # Assert: The prefix should be a simple relative path, different from the hash.
    assert pref_inside == "alpha.txt"
    assert pref_inside != pref_outside


# --------------------------------------------------------------------------- #
# 2. rel-mode – identically-named files must hash to *different* digests
# --------------------------------------------------------------------------- #
def test_rel_mode_hash_uniqueness(tmp_path: Path) -> None:
    """Ensures two identically named files in different paths produce unique hashes.

    Rationale:
        This test guards against a potential collision where the hashing
        algorithm might mistakenly rely only on the filename (`basename`)
        instead of the full, unique absolute path. By asserting that
        `dirA/dup.txt` and `dirB/dup.txt` produce different hashes when they
        are both outside a project root, it verifies that the full path is a
        critical component of the hash input, ensuring ID uniqueness.

    Args:
        tmp_path: The pytest fixture for a temporary directory.

    Returns:
        None
    """
    # Arrange: Create two files with the same name but in different directories.
    a = tmp_path / "dirA" / "dup.txt"
    b = tmp_path / "dirB" / "dup.txt"
    a.parent.mkdir()
    b.parent.mkdir()
    a.write_text("foo")
    b.write_text("bar")

    # Act: Generate prefixes for both, ensuring they are outside any `id_base`.
    id_base = tmp_path / "unrelated_base"
    pref_a = _run_once(a, "rel", str(id_base), tmp_path / "o1.jsonl")
    pref_b = _run_once(b, "rel", str(id_base), tmp_path / "o2.jsonl")

    # Assert: The hashes must be different and correctly formatted.
    assert pref_a != pref_b
    assert len(pref_a) == len(pref_b) == HEX_LEN
    assert set(pref_a) <= HEX_CHARS and set(pref_b) <= HEX_CHARS


# --------------------------------------------------------------------------- #
# 3. hash-mode – global uniqueness smoke-test
# --------------------------------------------------------------------------- #
def test_hash_mode_no_collision(tmp_path: Path) -> None:
    """Performs a smoke test to check for hash collisions in `hash` mode.

    Rationale:
        While not a formal proof of cryptographic strength, this test acts as a
        practical regression check. It ensures that recent changes have not
        broken the hashing mechanism (e.g., by using a bad salt, truncating the
        hash too aggressively, or using a non-unique input). Generating many
        hashes and checking for duplicates provides a reasonable level of
        confidence in ID uniqueness for typical use cases.

    Args:
        tmp_path: The pytest fixture for a temporary directory.

    Returns:
        None
    """
    # Arrange: Create 50 unique small files.
    for i in range(50):
        (tmp_path / f"f{i}.txt").write_text("x")

    # Act: Generate a hash prefix for every file.
    prefixes: list[str] = [
        _run_once(p, "hash", None, tmp_path / f"{p.stem}.jsonl")
        for p in tmp_path.glob("*.txt")
    ]

    # Assert: Check that all generated prefixes are unique.
    dupes = [p for p, cnt in Counter(prefixes).items() if cnt > 1]
    assert not dupes, f"hash collision: {dupes!r}"
    assert all(len(p) == HEX_LEN for p in prefixes)


# --------------------------------------------------------------------------- #
# 4. abs-mode – prefix equals absolute POSIX path
# --------------------------------------------------------------------------- #
def test_abs_mode_contains_full_path(tmp_path: Path) -> None:
    """Verifies `abs` mode uses the full, absolute POSIX path as the ID prefix.

    Rationale:
        This test confirms the behavior of the `abs` mode, which is intended
        for scenarios where globally unique and explicit file paths are
        required for data lineage, and the potential non-portability of
        absolute paths is an accepted trade-off. It ensures no hashing or
        relativizing logic is incorrectly applied when this mode is active.

    Args:
        tmp_path: The pytest fixture for a temporary directory.

    Returns:
        None
    """
    # Arrange: Create a source file.
    src = tmp_path / "zzz.txt"
    src.write_text("hello")

    # Act: Generate its ID prefix using `abs` mode.
    pref = _run_once(src, "abs", None, tmp_path / "out.jsonl")

    # Assert: The prefix must match the resolved, POSIX-normalized absolute path.
    expected_path = str(src.resolve()).replace("\\", "/")
    assert expected_path == pref
