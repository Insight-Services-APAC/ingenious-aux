"""
Memory‑robust document loader that **streams large JSON payloads** to keep
peak RAM bounded – even on resource‑constrained workers.

Purpose & Context
-----------------
This module lives inside the **chunking** subsystem of the Insight Ingenious
architecture (`ingenious/chunk/...`). Its primary role is to transform file
paths or glob patterns into a uniform list of
:class:`~langchain_core.documents.Document` objects. This list serves as the
canonical input for subsequent *semantic* or *token-based* chunking strategies.

The loader is designed to handle plain text, Markdown, JSON Lines, and standard
JSON files, which are the primary formats produced by the upstream
`ingenious document-processing` pipeline.

Key Algorithms & Design Choices
-------------------------------
- **Adaptive Loading**: To balance speed and memory safety, the loader uses an
  adaptive strategy. Files smaller than a configurable threshold
  (:data:`_STREAM_THRESHOLD`, 10 MiB by default) are loaded eagerly into memory
  using the standard :mod:`json` library for maximum performance. Larger files
  are parsed incrementally using the optional :pypi:`ijson` library. This
  ensures that the process's memory footprint grows only with the size of the
  largest single record within the JSON, not the entire file.
- **Minimal Metadata**: Each loaded record is wrapped in a `Document` object
  containing only essential traceability information: the original `source` file
  path and a synthetic `page` index. This approach prevents memory bloat from
  excessive metadata while ensuring every chunk can be traced back to its
  origin.
- **Graceful Degradation**: If a large JSON file is encountered but the `ijson`
  library is not installed, the loader raises a descriptive
  :class:`RuntimeError`. This provides a clear, actionable error message,
  prompting the user to install the necessary dependency (e.g., via
  `pip install ingenious[chunk]`) and retry.

Usage Example
-------------
.. code-block:: python

    from ingenious.chunk.loader import load_documents

    # Load all JSON Lines files from a dataset directory.
    docs = load_documents("datasets/**/*.jsonl")

    print(f"Loaded {len(docs)} documents.")
    if docs:
        print("First document metadata:", docs[0].metadata)
"""

from __future__ import annotations

import enum
import json
import logging
import os
from glob import glob
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, List

import jsonlines
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

try:  # optional streaming backend (pure‑Python, MIT)
    import ijson  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    ijson = None  # sentinel used later

# --------------------------------------------------------------------------- #
# Loader helpers                                                              #
# --------------------------------------------------------------------------- #
_STREAM_THRESHOLD = int(os.getenv("INGEN_JSON_STREAM_THRESHOLD", 10 << 20))  # 10 MiB


class _Mode(enum.Enum):
    """Internal switch for selecting the appropriate loading strategy."""

    SMALL = "small"  # eager json.load path
    STREAM = "stream"  # incremental parse via ijson
    FAIL = "fail"  # large but no ijson – raise


def _iter_files(pattern: str) -> Iterable[Path]:
    """Yields all valid, non-directory files matched by the input pattern.

    Rationale:
        This helper centralizes file discovery logic, handling three distinct
        cases: a single file, a directory to be recursively searched, or a
        glob pattern. Using `pathlib` and `glob` provides a robust,
        cross-platform implementation.

    Args:
        pattern: A file path, directory path, or a glob pattern (e.g.,
            `**/*.json`) understood by :py:func:`glob.glob`.

    Yields:
        Path: A `pathlib.Path` object for each file found.
    """
    p = Path(pattern)
    if p.exists():
        if p.is_file():
            yield p
        else:  # is a directory
            yield from (fp for fp in p.rglob("*") if fp.is_file())
    else:  # glob expansion
        yield from (Path(m) for m in glob(pattern, recursive=True) if Path(m).is_file())


_KEY_CANDIDATES = ("text", "page_content", "body")


def _extract_text(rec: dict[str, Any]) -> str:
    """Returns the first non-blank string value from a set of standard keys.

    Rationale:
        Different document sources may use different keys for the main text
        content. This function normalizes access by checking a list of common
        candidates (`text`, `page_content`, `body`), making the parsers more
        resilient to variations in input data schemas.

    Args:
        rec: A dictionary-like object, typically from a JSON structure.

    Returns:
        The first non-empty string found, or an empty string if no candidate
        key contains valid text.
    """
    for k in _KEY_CANDIDATES:
        v = rec.get(k, "")
        if isinstance(v, str) and v.strip():
            return v
    return ""


# --------------------------------------------------------------------------- #
# JSON helpers – streaming vs eager                                           #
# --------------------------------------------------------------------------- #


def _select_mode(path: Path) -> _Mode:
    """Decides whether to load a JSON file eagerly or via streaming.

    Rationale:
        This function implements the core adaptive loading strategy. By checking
        the file size against `_STREAM_THRESHOLD`, it chooses the optimal path:
        fast, in-memory parsing for small files and memory-safe streaming for
        large ones. It also handles the case where streaming is required but
        the necessary library (`ijson`) is not available.

    Args:
        path: The path to the JSON file.

    Returns:
        The appropriate loading mode (`_Mode.SMALL`, `_Mode.STREAM`, or
        `_Mode.FAIL`).
    """
    if path.stat().st_size <= _STREAM_THRESHOLD:
        return _Mode.SMALL
    if ijson is None:
        return _Mode.FAIL
    return _Mode.STREAM


def _stream_array(path: Path) -> Iterator[dict[str, Any]]:
    """Yields objects from a top-level JSON array one by one using ijson.

    Rationale:
        This is a memory-efficient way to process a JSON file structured as a
        list of objects (`[{...}, {...}]`). `ijson.items` with the prefix "item"
        iterates through the top-level array elements without loading the
        entire list into memory.

    Args:
        path: The path to the JSON file, which must contain a top-level array.

    Yields:
        A dictionary for each item in the JSON array.
    """
    with path.open("rb") as fp:
        yield from ijson.items(fp, "item")


def _stream_object(path: Path) -> Iterator[Document]:
    """Streams a top-level JSON object's values as individual documents.

    Rationale:
        This handles large JSON files structured as a dictionary where each
        value is a document. `ijson.kvitems` iterates through the key-value
        pairs at the root, allowing us to process each sub-object as a
        separate document without loading the entire parent object.

    Args:
        path: The path to the JSON file, which must contain a top-level object.

    Yields:
        A `Document` for each value in the top-level JSON object that contains
        extractable text.

    Raises:
        RuntimeError: If `ijson` is not installed.

    Implementation Notes:
        The JSON structure is assumed to be `{"key1": {"text": "..."}, ...}`.
        The key is discarded, and the value is treated as the document record.
        A synthetic `page` index is created from the iteration order.
    """
    if ijson is None:  # pragma: no cover – callers guard first
        raise RuntimeError("ijson must be installed for streaming mode")

    with path.open("rb") as fp:
        # kvitems returns an iterator of (key, value) pairs at the given prefix.
        for idx, (_, value) in enumerate(ijson.kvitems(fp, "")):
            # Accept either a bare string OR an object embedding the text.
            txt = value if isinstance(value, str) else _extract_text(value)
            if isinstance(txt, str) and txt.strip():
                yield Document(
                    txt,
                    metadata={
                        "source": str(path),
                        "page": idx,  # preserve positional semantics
                    },
                )


def _root_char(path: Path) -> str:
    """Returns the first non-whitespace character of a file.

    Rationale:
        This is a cheap and fast probe to determine if a JSON file's root
        element is an array (`[`) or an object (`{`). By reading only the first
        few bytes, we can select the correct streaming strategy
        (`_stream_array` vs. `_stream_object`) without parsing any of the file,
        avoiding unnecessary work and memory usage.

    Args:
        path: The path to the file to inspect.

    Returns:
        The first non-whitespace character, or an empty string if the file is
        empty or contains only whitespace.
    """
    with path.open("rb") as fp:
        while b := fp.read(1):
            ch = chr(b[0])
            if not ch.isspace():
                return ch
    return ""


# --------------------------------------------------------------------------- #
# Per-extension parser functions                                              #
# --------------------------------------------------------------------------- #


def _parse_jsonl(path: Path) -> Iterator[Document]:
    """Parses a JSON Lines (`.jsonl`) file lazily.

    Rationale:
        The `jsonlines` library is purpose-built for this format and reads one
        record at a time, making it inherently memory-efficient. This function
        wraps its reader to convert each valid line into a `Document`.

    Args:
        path: The path to the JSON Lines file.

    Yields:
        A `Document` for each line in the file containing extractable text.
    """
    with jsonlines.open(path) as rdr:
        for i, rec in enumerate(rdr):
            if txt := _extract_text(rec):
                yield Document(txt, metadata={"source": str(path), "page": i})


def _parse_json(path: Path) -> Iterator[Document]:
    """Parses a regular JSON file, choosing between eager and streaming modes.

    Rationale:
        This is the core dispatcher for `.json` files. It uses `_select_mode`
        to decide on a strategy. For small files, it performs a fast, eager
        load. For large files, it uses `_root_char` to peek at the structure
        and then delegates to the appropriate streaming function. This ensures
        both performance for common cases and safety for large inputs.

    Args:
        path: The path to the JSON file.

    Yields:
        A `Document` for each record found in the JSON file.

    Raises:
        RuntimeError: If the file is large and `ijson` is not installed.
        json.JSONDecodeError: If the file is malformed or has an unsupported
            top-level structure (e.g., a bare number or string).
    """
    mode = _select_mode(path)

    # ---------- eager small‑file path ------------------------------------ #
    if mode is _Mode.SMALL:
        payload = json.loads(path.read_text(encoding="utf-8"))
        records: Iterable[dict[str, Any]]
        if isinstance(payload, list):
            records = payload
        elif isinstance(payload, dict):
            # If the object *itself* is a document, wrap it; otherwise its
            # values are the documents.
            records = [payload] if _extract_text(payload) else payload.values()
        else:
            records = []  # unsupported JSON structure (e.g., a root literal)

        for i, rec in enumerate(records):
            if isinstance(rec, dict) and (txt := _extract_text(rec)):
                yield Document(txt, metadata={"source": str(path), "page": i})
        return

    # ---------- large file but cannot stream ---------------------------- #
    if mode is _Mode.FAIL:  # pragma: no cover
        size_mb = path.stat().st_size / (1 << 20)
        raise RuntimeError(
            f"{path} is {size_mb:,.1f} MB – install 'ingenious[chunk]' or "
            f"'ijson' to enable streaming of large JSON files."
        )

    # ---------- streaming path (array or single object) ----------------- #
    assert ijson is not None  # for type-checkers

    first = _root_char(path)
    if first == "[":  # top-level array
        for i, rec in enumerate(_stream_array(path)):
            if txt := _extract_text(rec):
                yield Document(txt, metadata={"source": str(path), "page": i})
    elif first == "{":  # top-level map
        yield from _stream_object(path)
    else:  # malformed or exotic JSON
        raise json.JSONDecodeError("Unsupported JSON structure", doc=str(path), pos=0)


def _parse_text(path: Path) -> Iterator[Document]:
    """Wraps an entire text-based file as a single `Document`.

    Rationale:
        This is a straightforward loader for unstructured or semi-structured
        text files like `.txt` and `.md`. The entire content is read into a
        single `Document`, as these formats lack an internal record structure.

    Args:
        path: The path to the text or Markdown file.

    Yields:
        A single `Document` containing the file's text, if it is not blank.
    """
    txt = path.read_text(encoding="utf-8", errors="replace")
    if txt.strip():
        yield Document(txt, metadata={"source": str(path.resolve())})


# Dispatch table – *every* accepted extension must appear exactly once.
_PARSERS: dict[str, Callable[[Path], Iterator[Document]]] = {
    ".jsonl": _parse_jsonl,
    ".ndjson": _parse_jsonl,
    ".json": _parse_json,
    ".txt": _parse_text,
    ".md": _parse_text,
    ".markdown": _parse_text,
}

_ALLOWED_EXTS = ", ".join(sorted(_PARSERS))


# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #


def load_documents(pattern: str) -> List[Document]:
    """Expands a glob pattern into files and parses each into `Document`s.

    Rationale:
        This is the single public entry point for the module, providing a
        simple and powerful interface for document ingestion. It orchestrates
        file discovery, parser selection, and error handling. By iterating
        through files and catching non-fatal errors, it enables robust batch
        processing where a single bad file won't halt the entire operation.

    Args:
        pattern: A path, directory, or glob pattern identifying the source
            files to load.

    Returns:
        A flat list of `langchain_core.documents.Document` objects, aggregated
        from all successfully parsed files.

    Raises:
        FileNotFoundError: If the `pattern` matches no parsable documents.
        ValueError: If a file with an unsupported extension is found.
        RuntimeError: When an oversized JSON file is encountered but streaming
            support is unavailable (`ijson` is not installed).

    Implementation Notes:
        Non-fatal `OSError`, `json.JSONDecodeError`, and `jsonlines.Error`
        exceptions are caught, logged as warnings, and the problematic file is
        skipped. This allows batch ingestion to continue uninterrupted. A fatal
        `RuntimeError` from the JSON parser is re-raised after logging.
    """
    docs: list[Document] = []

    for file_path in _iter_files(pattern):
        if file_path.is_dir():
            continue

        ext = file_path.suffix.lower()
        parser = _PARSERS.get(ext)
        if not parser:
            # This check is important for user feedback, as globs might
            # unintentionally match unsupported files (e.g., .DS_Store).
            logger.warning(
                "Skipping unsupported file extension %r in %s. Accepted: %s.",
                ext,
                file_path,
                _ALLOWED_EXTS,
            )
            continue

        try:
            docs.extend(parser(file_path))
        except (OSError, json.JSONDecodeError, jsonlines.Error) as exc:
            # Non‑fatal I/O or parse error – skip file but keep going.
            logger.warning("%s skipped (%s)", file_path, exc)
        except RuntimeError as exc:
            # 🔴 Fatal: large JSON requires streaming but ijson is missing.
            logger.error("%s", exc)
            raise

    if not docs:
        raise FileNotFoundError(f"No parsable documents found for {pattern!r}")

    logger.info("Loaded %d documents from pattern %r", len(docs), pattern)
    return docs
