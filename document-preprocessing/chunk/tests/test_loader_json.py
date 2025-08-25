"""
Tests for the document loader at `ingenious.chunk.loader.load_documents`.

Purpose & Context:
    This module contains the unit test suite for the `load_documents` function, which is a
    critical first step in the Insight Ingenious data ingestion pipeline. This loader
    is responsible for reading various file formats (JSON, JSONL) from a given path
    and converting them into a standardized list of `Document` objects. Correct parsing
    at this stage is essential for subsequent chunking, embedding, and indexing processes.

Key Algorithms / Design Choices:
    The tests leverage the `pytest` framework, particularly the `tmp_path` fixture.
    This approach ensures that file I/O operations are tested against a temporary,
    isolated filesystem, preventing side effects and ensuring test idempotency. Each
    test case covers a specific, common data format that the loader is expected to handle:
    1.  A single JSON object.
    2.  An array of JSON objects.
    3.  A stream of JSON objects in JSON Lines (`.jsonl`) format.
"""

import json
from pathlib import Path

import jsonlines

from ingenious.chunk.loader import load_documents


def test_loader_single_json_object(tmp_path: Path) -> None:
    """Verifies `load_documents` correctly handles a file with a single JSON object.

    Rationale:
        This test case validates a common scenario where a data source might provide
        a file containing just one record. The loader must correctly parse this into a
        list containing a single `Document` object, ensuring it doesn't fail on
        non-array JSON inputs.

    Args:
        tmp_path (Path): The `pytest` fixture providing a temporary directory path.

    Returns:
        None

    Implementation Notes:
        The test creates a temporary file `single.json` within the path provided by
        the `tmp_path` fixture. It asserts that the loader returns exactly one
        document and that its content and default metadata (`page=0`) are parsed
        correctly.
    """
    f = tmp_path / "single.json"
    f.write_text(json.dumps({"text": "hello"}), encoding="utf-8")
    docs = load_documents(str(f))
    assert len(docs) == 1
    assert docs[0].page_content == "hello"
    assert docs[0].metadata["page"] == 0


def test_loader_json_array(tmp_path: Path) -> None:
    """Verifies `load_documents` correctly handles a file with a JSON array.

    Rationale:
        This is the most standard JSON input format, where multiple records are
        enclosed in a single top-level array. This test ensures the loader can
        iterate through the array and convert each JSON object into a `Document`.

    Args:
        tmp_path (Path): The `pytest` fixture providing a temporary directory path.

    Returns:
        None

    Implementation Notes:
        The test writes a JSON array with three distinct objects to `array.json`.
        It checks that the number of documents matches and that the `page_content`
        is correctly extracted from various possible keys (`text`, `page_content`,
        `body`), demonstrating the loader's field-name flexibility.
    """
    payload = [{"text": "a"}, {"page_content": "b"}, {"body": "c"}]
    f = tmp_path / "array.json"
    f.write_text(json.dumps(payload), encoding="utf-8")
    docs = load_documents(str(f))
    assert [d.page_content for d in docs] == ["a", "b", "c"]


def test_loader_jsonl(tmp_path: Path) -> None:
    """Verifies `load_documents` correctly handles a JSON Lines (.jsonl) file.

    Rationale:
        JSON Lines is a common format for streaming large datasets, as it allows
        records to be read one by one without loading the entire file into memory.
        This test confirms that the loader correctly integrates with a `jsonlines`
        reader to process such files efficiently.

    Args:
        tmp_path (Path): The `pytest` fixture providing a temporary directory path.

    Returns:
        None

    Implementation Notes:
        The test uses the `jsonlines` library to write three separate JSON objects,
        each on a new line, to `stream.jsonl`. It then asserts that the loader
        correctly parses all three objects into distinct `Document` instances.
    """
    f = tmp_path / "stream.jsonl"
    with jsonlines.open(f, mode="w") as w:
        for k in ["foo", "bar", "baz"]:
            w.write({"body": k})
    docs = load_documents(str(f))
    assert [d.page_content for d in docs] == ["foo", "bar", "baz"]
