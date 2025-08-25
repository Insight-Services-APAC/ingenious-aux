"""
Tests the streaming JSON capabilities of the document loader.

Purpose & Context:
    This module contains unit tests for the streaming JSON parsing logic within
    the `ingenious.chunk.loader` module, specifically targeting code paths that
    are activated for large JSON files. In the Insight Ingenious architecture,
    efficiently loading large datasets without incurring out-of-memory (OOM)
    errors is critical for data ingestion agents. These tests verify that the
    system correctly uses the `ijson` library to handle such files.

Key Algorithms / Design Choices:
    The testing strategy relies heavily on `pytest` fixtures to simulate specific
    conditions:
    - `tmp_path`: Creates temporary JSON files on disk for the loader to read,
      avoiding the need to store large test assets in the repository.
    - `monkeypatch`: This is used extensively to force the loader into specific
      internal states (`_Mode.STREAM`, `_Mode.FAIL`) and to simulate the
      absence of the optional `ijson` dependency. This decouples the tests
      from the loader's file-size detection logic, allowing for direct and
      focused validation of the streaming parser itself.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

import pytest

from ingenious.chunk import loader
from ingenious.chunk.loader import load_documents

if TYPE_CHECKING:
    from _pytest.logging import LogCaptureFixture
    from _pytest.monkeypatch import MonkeyPatch


# --------------------------------------------------------------------------- #
# 1. Happy‑path: large JSON array streamed via ijson                          #
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(loader.ijson is None, reason="ijson extra not installed")
def test_stream_large_json(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Verifies that `load_documents` correctly streams a large JSON array.

    Rationale:
        This is the primary happy-path test for streaming ingestion. It ensures
        that for a large array of JSON objects, which is a common data format,
        the `ijson`-based parser is used and processes all records correctly
        without loading the entire file into memory. Forcing `_Mode.STREAM`
        isolates the test to the streaming logic itself.

    Args:
        tmp_path: The pytest fixture providing a temporary directory path.
        monkeypatch: The pytest fixture for modifying objects, classes, or
            modules during testing.

    Returns:
        None

    Raises:
        AssertionError: If the document count or content is incorrect.

    Implementation Notes:
        A 5,000-record array is generated to be large enough to trigger
        streaming logic in a real scenario, but the test forces the mode
        via monkeypatching for determinism.
    """
    recs = [{"text": f"row-{i}"} for i in range(5_000)]
    p = tmp_path / "big.json"
    p.write_text(json.dumps(recs), encoding="utf-8")

    # Force STREAM mode regardless of actual size
    monkeypatch.setattr(loader, "_select_mode", lambda *_: loader._Mode.STREAM)

    docs = list(load_documents(str(p)))
    assert len(docs) == 5_000
    assert docs[0].page_content == "row-0"
    assert docs[-1].page_content == "row-4999"


# --------------------------------------------------------------------------- #
# 2. Failure: large file but *no* ijson available                             #
# --------------------------------------------------------------------------- #


def test_stream_without_ijson(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """Ensures a `RuntimeError` is raised if streaming is needed but `ijson` is absent.

    Rationale:
        A critical aspect of the user experience is providing clear, actionable
        error messages. This test validates a key failure scenario: the system
        determines streaming is necessary but the required dependency (`ijson`)
        is not installed. The test confirms that we fail fast with a helpful
        log message guiding the user to a solution, per DI-101.

    Args:
        tmp_path: The pytest fixture providing a temporary directory path.
        monkeypatch: The pytest fixture for modifying objects.
        caplog: The pytest fixture for capturing log output.

    Returns:
        None

    Raises:
        AssertionError: If the expected exception or log message is not produced.
    """
    payload = {"text": "hello"}
    p = tmp_path / "one.json"
    p.write_text(json.dumps(payload), encoding="utf-8")

    # Simulate `ijson` not being installed and force the failure code path.
    monkeypatch.setitem(sys.modules, "ijson", ModuleType("ijson"))
    monkeypatch.setattr(loader, "ijson", None)
    monkeypatch.setattr(loader, "_select_mode", lambda *_: loader._Mode.FAIL)

    with caplog.at_level(logging.ERROR, "ingenious.chunk.loader"):
        with pytest.raises(RuntimeError):
            load_documents(str(p))

    assert "install 'ingenious[chunk]' or 'ijson'" in caplog.text


# --------------------------------------------------------------------------- #
# 3. Huge *single‑object* JSON streamed via kvitems                           #
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(loader.ijson is None, reason="ijson extra not installed")
def test_stream_huge_single_object(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Validates streaming of a large top-level JSON object (not an array).

    Rationale:
        Real-world JSON data is not always structured as a top-level array.
        This test covers the case of a large dictionary (object), which must
        be handled by iterating over its key-value pairs. This ensures the
        loader's use of `ijson.kvitems` is correct, providing robustness for
        varied data structures.

    Args:
        tmp_path: The pytest fixture providing a temporary directory path.
        monkeypatch: The pytest fixture for modifying objects.

    Returns:
        None

    Raises:
        AssertionError: If the document count or content is incorrect.

    Implementation Notes:
        A JSON object with 10,000 top-level keys is created to specifically
        exercise the `kvitems` logic path in the streaming implementation.
    """
    big = {str(i): {"text": f"row-{i}"} for i in range(10_000)}
    p = tmp_path / "big_object.json"
    p.write_text(json.dumps(big), encoding="utf-8")

    monkeypatch.setattr(loader, "_select_mode", lambda *_: loader._Mode.STREAM)

    docs = list(load_documents(str(p)))
    assert len(docs) == 10_000
    assert docs[0].page_content == "row-0"
    assert docs[-1].page_content == "row-9999"
