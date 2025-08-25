"""
Insight Ingenious – unit tests for ``_iter_sources``
===================================================

This test-suite validates :pyfunc:`ingenious.document_processing.cli._iter_sources`,
a helper generator that **normalises* user-supplied locations** (file paths,
directories, or HTTP/S URLs) into a `(label, source)` pair::

    (label: str, source: Union[bytes, pathlib.Path])

What we verify
--------------
1. **Local paths**
   • *Single file* – yields exactly that file.
   • *Directory*  – finds every PDF/DOCX/PPTX/… below the root via a
     **suffix-aware, short-circuiting ``os.walk``**.

2. **Remote URLs**
   • Downloads the document through ``fetcher.fetch`` (Requests under the hood).
   • On *404* (or any error) the iterator stays empty (fail-soft contract).

3. **Directory filtering**
   • Non-supported suffixes are skipped.
   • Empty directories produce no output.

4. **Scalability guard**
   • A synthetic tree with 10 000 irrelevant files **must** finish within
     one second and yield exactly one result (our single valid PDF).

Why this matters
----------------
``_iter_sources`` powers the document-processing CLI.  A regression here would
surface as missing inputs or crashes in production.  Tests therefore:

* Stub out all network traffic.
* Build tiny, synthetic file trees.
* Run fast and deterministically on CI hardware.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, Tuple

import pytest
from requests import HTTPError

from ingenious.document_processing.cli import _iter_sources

# ---------------------------------------------------------------------------#
# Test constants                                                             #
# ---------------------------------------------------------------------------#
REMOTE_PDF_URL: str = "https://unec.edu.az/application/uploads/2014/12/pdf-sample.pdf"


# ---------------------------------------------------------------------------#
# Test helpers                                                               #
# ---------------------------------------------------------------------------#
class _StubResp:
    """
    Ultra-lightweight stand-in for :class:`requests.Response`.

    The real ``fetcher.fetch`` only touches a handful of attributes /
    methods, so we imitate just those:

    * ``content``     – the raw body returned by the server.
    * ``headers``     – only *Content-Length* is consulted.
    * ``raise_for_status`` – raises :class:`requests.HTTPError` on demand.
    * ``iter_content`` – yields bytes chunks (we emit a single chunk).
    * Context-manager protocol ( ``__enter__``, ``__exit__`` ).

    Keeping the shim minimal avoids importing Requests in earnest and
    guarantees lightning-fast, deterministic unit tests.
    """

    # ---- construction ----------------------------------------------------#
    def __init__(self, payload: bytes, *, status_ok: bool = True) -> None:
        self.content: bytes = payload
        self._status_ok: bool = status_ok
        # ``fetcher.fetch`` reads Content-Length once to pre-allocate a buffer.
        self.headers: dict[str, str] = {"Content-Length": str(len(payload))}

    # ---- context-manager protocol ----------------------------------------#
    def __enter__(self):  # noqa: D401 (one-liner acceptable)
        return self

    def __exit__(self, exc_type, _exc, _tb) -> bool:
        # Return *False* → propagate any exception exactly like Requests.
        return False

    # ---- requests-like API ----------------------------------------------#
    def raise_for_status(self) -> None:
        """Mimic :pymeth:`requests.Response.raise_for_status`."""
        if not self._status_ok:
            raise HTTPError("404 – Not Found")

    def iter_content(self, chunk_size: int = 1 << 14):
        """
        Yield bytes chunks.

        Production streams 16 KiB chunks (``1 << 14``),
        but tests can simply emit the whole payload at once.
        """
        yield self.content


# ---------------------------------------------------------------------------#
# 1. Local path / recursive directory tests                                  #
# ---------------------------------------------------------------------------#
@pytest.mark.parametrize(
    "scenario", ["single_file", "nested_dir"], ids=["file", "nested_dir"]
)
def test_iter_sources_local(scenario: str, tmp_path: Path, pdf_path: Path) -> None:
    """
    Verify local-filesystem discovery.

    * **single_file** – supplying an explicit path should yield that file.
    * **nested_dir**  – supplying a directory should yield the PDF cloned
      *somewhere* beneath it, discovered via the suffix-aware walker.
    """
    if scenario == "single_file":
        labels = [lbl for lbl, _ in _iter_sources(pdf_path)]
        assert str(pdf_path) in labels
    else:  # nested directory
        deep_dir = tmp_path / "deep"
        deep_dir.mkdir()
        cloned = deep_dir / pdf_path.name
        cloned.write_bytes(pdf_path.read_bytes())

        labels = [lbl for lbl, _ in _iter_sources(tmp_path)]
        assert str(cloned) in labels


# ---------------------------------------------------------------------------#
# 2. Remote URL branch                                                       #
# ---------------------------------------------------------------------------#
@pytest.mark.parametrize("ok", [True, False], ids=["200", "404"])
def test_iter_sources_remote(
    monkeypatch: pytest.MonkeyPatch,
    pdf_bytes: bytes,
    ok: bool,
) -> None:
    """
    Exercise the **URL** code-path.

    * **200** – iterator yields exactly one ``(label, bytes)`` tuple.
    * **404** – iterator stays empty (graceful failure).
    """
    from ingenious.document_processing.utils.fetcher import requests

    # Patch ``requests.get`` to return the stub response.
    monkeypatch.setattr(
        requests,
        "get",
        lambda *_a, **_kw: _StubResp(pdf_bytes, status_ok=ok),
        raising=True,
    )

    if ok:
        lbl, src = next(_iter_sources(REMOTE_PDF_URL))
        assert lbl.startswith("http")
        assert isinstance(src, bytes) and src == pdf_bytes
    else:
        assert list(_iter_sources(f"{REMOTE_PDF_URL}?missing")) == []


# ---------------------------------------------------------------------------#
# 3. Directory filtering                                                     #
# ---------------------------------------------------------------------------#
@pytest.mark.parametrize(
    ("fixture_builder", "expected"),
    [("empty", 0), ("mixed", 1)],
    ids=["empty_dir", "filter_non_pdf"],
)
def test_iter_sources_directory_filter(
    fixture_builder: str,
    expected: int,
    tmp_path: Path,
    pdf_path: Path,
) -> None:
    """
    Confirm suffix filtering behaves as documented.

    * **empty_dir**    – iterator exhausts immediately.
    * **filter_non_pdf** – only supported suffixes are yielded.
    """
    root = tmp_path
    if fixture_builder == "mixed":
        (root / "note.txt").write_text("ignore me")  # unsupported
        target = root / pdf_path.name  # supported
        target.write_bytes(pdf_path.read_bytes())

    results: Iterator[Tuple[str, object]] = _iter_sources(root)
    labels = [lbl for lbl, _ in results]

    assert len(labels) == expected
    if labels:  # mixed case
        assert labels[0].endswith(".pdf")


# ---------------------------------------------------------------------------#
# 4. Scalability probe – large directory                                     #
# ---------------------------------------------------------------------------#
@pytest.mark.timeout(1.0)  # fail if traversal >1 s on CI hardware
def test_iter_sources_large_tree(tmp_path: Path, pdf_path: Path) -> None:
    """
    Ensure the suffix-aware ``os.walk`` scales linearly.

    Build a tree with 10 000 junk files **plus one** valid PDF and assert:

    1. Exactly one ``(label, src)`` tuple is produced.
    2. The tuple points to the planted PDF.
    3. The traversal finishes within the one-second timeout.
    """
    deep_dir = tmp_path / "deep" / "nested" / "branch"
    deep_dir.mkdir(parents=True, exist_ok=True)

    # 10 000 irrelevant files
    for i in range(10_000):
        (deep_dir / f"ignore_{i}.tmp").write_text("x")

    # One valid target
    target = deep_dir / pdf_path.name
    target.write_bytes(pdf_path.read_bytes())

    results = list(_iter_sources(tmp_path))
    assert results == [(str(target), target)]
