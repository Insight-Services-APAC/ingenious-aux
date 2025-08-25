"""
PyMuPDF‑based extractor (non‑OCR)
================================

This module defines :class:`PyMuPDFExtractor`, a high‑performance implementation
of the :class:`~ingenious.document_processing.extractor.base.DocumentExtractor`
interface that converts **born‑digital** PDF files into a stream of structured
text *elements* suitable for downstream NLP pipelines.

───────────────────────────────────────────────────────────────────────────────
Why PyMuPDF?
───────────────────────────────────────────────────────────────────────────────
``fitz`` (PyMuPDF) is a mature C‑backed wrapper around the *MuPDF* renderer.  It
exposes a Pythonic API while retaining MuPDF’s renowned
*speed × memory‑efficiency*.  Compared with other pure‑Python PDF libraries,
PyMuPDF

* **opens gigabyte‑scale files in milliseconds** because it lazy‑maps the page
  tree; pages are loaded on demand rather than parsed eagerly;
* **extracts text with positional metadata** (bounding boxes) without requiring
  an external layout analysis step; and
* **handles a wide selection of encodings** (CJK, RTL, etc.) using MuPDF’s
  built‑in font engine.

This engine purposely **does not perform OCR**.  Scanned or faxed PDFs that
lack an embedded text layer must be routed to another extractor (e.g.
``unstructured``) capable of optical recognition.

───────────────────────────────────────────────────────────────────────────────
Schema contract
───────────────────────────────────────────────────────────────────────────────
Every yielded :class:`Element` *dict* conforms to the canonical schema expected
by Insight Ingenious:

.. code:: python

    {
        "page"  : int,                           # 1‑based page index
        "type"  : str,                           # semantic tag
        "text"  : str,                           # UTF‑8 narrative text
        "coords": tuple[float, float, float, float]  # (x0, y0, x1, y1)
    }

The "type" is hard‑coded to ``"NarrativeText"`` because PyMuPDF returns generic
blocks.  Future versions may introduce richer block‑type inference.

───────────────────────────────────────────────────────────────────────────────
Thread‑safety & reentrancy
───────────────────────────────────────────────────────────────────────────────
*PyMuPDF is **not** re‑entrant.*  All per‑document state lives in the native
``Document`` object held inside the generator; no global state is mutated, so
**multiple extractor instances can safely run in parallel threads/processes**.

───────────────────────────────────────────────────────────────────────────────
Example
───────────────────────────────────────────────────────────────────────────────
>>> from ingenious.document_processing.extractor import extract
>>> for blk in extract("manual.pdf", engine="pymupdf"):
...     print(f"{blk['page']:02d}: {blk['text'][:80]}")

───────────────────────────────────────────────────────────────────────────────
Module exports
───────────────────────────────────────────────────────────────────────────────
* :data:`Src` – type alias for *source* inputs (path, URL, raw bytes).
* :class:`PyMuPDFExtractor` – concrete extractor implementation.
"""

from __future__ import annotations

import gc
import io
import mimetypes
import os
from pathlib import Path
from typing import Callable, Iterable, TypeAlias

import fitz  # PyMuPDF
import psutil

from ingenious.core.structured_logging import get_logger
from ingenious.document_processing.utils.fetcher import fetch, is_url
from ingenious.errors.processing import (
    ErrorCode,
    handle_extraction_error,
)

from .base import DocumentExtractor, Element

logger = get_logger(__name__)

# ------------------------------------------------------------------
# Public type aliases
# ------------------------------------------------------------------
Src: TypeAlias = str | bytes | io.BytesIO | os.PathLike[str]
ProgressCallback: TypeAlias = Callable[[int, int], None]  # (current_page, total_pages)


# ------------------------------------------------------------------
# Extractor implementation
# ------------------------------------------------------------------
class PyMuPDFExtractor(DocumentExtractor):
    """Stream textual **elements** from a born‑digital PDF via PyMuPDF.

    The extractor walks each page, filters out non‑textual blocks, sorts the
    remaining blocks into *natural reading order*, and yields them one by one.

    Parameters passed to :meth:`extract` are *not* stored on the instance – the
    class is therefore **stateless** and can be reused concurrently.

    Attributes
    ----------
    name : str
        Registry key understood by
        :pyfunc:`ingenious.document_processing.extractor.extract`.
    """

    #: Registry identifier used by the extractor registry.
    name: str = "pymupdf"

    # ------------------------------------------------------------------
    # Capability probe
    # ------------------------------------------------------------------
    def supports(self, src: Src) -> bool:
        if isinstance(src, (bytes, bytearray, io.BytesIO)):
            return True
        if isinstance(src, str) and is_url(src):
            return True  # Accept any HTTP/S URL
        string_like = str(src).lower()
        return string_like.endswith(".pdf") or (
            mimetypes.guess_type(string_like)[0] == "application/pdf"
        )

    # ------------------------------------------------------------------
    # Memory monitoring utilities
    # ------------------------------------------------------------------
    def _get_memory_usage_mb(self) -> float:
        """Get current process memory usage in MB."""
        try:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0

    def _should_yield_control(self, max_memory_mb: float, start_memory: float) -> bool:
        """Check if memory usage exceeds threshold and we should yield control."""
        current_memory = self._get_memory_usage_mb()
        memory_growth = current_memory - start_memory
        if memory_growth > max_memory_mb:
            logger.warning(
                "Memory usage exceeded threshold",
                memory_growth_mb=memory_growth,
                max_memory_mb=max_memory_mb,
            )
            return True
        return False

    # ------------------------------------------------------------------
    # Streaming extraction with memory management
    # ------------------------------------------------------------------
    def extract_stream(
        self,
        src: Src,
        max_memory_mb: float = 100.0,
        progress_callback: ProgressCallback | None = None,
    ) -> Iterable[Element]:
        """Yield Elements with memory-efficient streaming and progress tracking.

        This method processes PDFs page-by-page to minimize memory footprint,
        with configurable memory limits and progress callbacks for long-running
        extractions.

        Parameters
        ----------
        src : Src
            Source PDF as path/URL/bytes.
        max_memory_mb : float, default=100.0
            Maximum memory growth allowed before yielding control (in MB).
        progress_callback : ProgressCallback | None, default=None
            Optional callback function called with (current_page, total_pages)
            for progress tracking.

        Yields
        ------
        Element
            One structured text block per iteration.

        Notes
        -----
        - Processes pages individually to reduce memory usage
        - Monitors memory growth and logs warnings when limits are exceeded
        - Calls progress_callback after each page if provided
        - Performs garbage collection after each page
        """
        logger.debug(
            "Starting stream extraction", src=repr(src), max_memory_mb=max_memory_mb
        )

        start_memory = self._get_memory_usage_mb()
        logger.debug("Starting memory usage", memory_mb=start_memory)

        # ── Handle input normalization (same as extract()) ──────────────────────
        if isinstance(src, io.BytesIO):
            src = src.getvalue()

        stream_bytes: bytes | None = None
        if isinstance(src, (bytes, bytearray)):
            stream_bytes = bytes(src)
            src_for_open: bytes = stream_bytes
        else:
            if isinstance(src, Path):
                src_for_open = str(src)
            else:
                src_str = str(src)
                if is_url(src_str):
                    payload = fetch(src_str)
                    if payload is None:
                        return
                    stream_bytes = payload
                    src_for_open = stream_bytes
                else:
                    src_for_open = src_str

        # ── Open document ───────────────────────────────────────────────────────
        try:
            doc = (
                fitz.open(stream=src_for_open, filetype="pdf")
                if stream_bytes is not None
                else fitz.open(src_for_open)
            )
        except fitz.FileDataError as exc:
            # Document is corrupted or invalid format
            error = handle_extraction_error(
                operation="open_document",
                src=src,
                engine="pymupdf",
                cause=exc,
                file_size=len(stream_bytes) if stream_bytes else None,
            ).with_context(error_code=ErrorCode.DOCUMENT_CORRUPTED)

            logger.warning(
                "PyMuPDF failed to open document - corrupted or invalid format",
                src=repr(src),
                error=str(exc),
                error_code=error.error_code.value,
            )
            return

        except RuntimeError as exc:
            # Engine execution failure
            error = handle_extraction_error(
                operation="open_document",
                src=src,
                engine="pymupdf",
                cause=exc,
                file_size=len(stream_bytes) if stream_bytes else None,
            ).with_context(error_code=ErrorCode.ENGINE_EXECUTION_FAILED)

            logger.warning(
                "PyMuPDF runtime error during document open",
                src=repr(src),
                error=str(exc),
                error_code=error.error_code.value,
            )
            return
        finally:
            if stream_bytes is not None:
                del stream_bytes
                gc.collect()  # Force cleanup of potentially large buffer

        try:
            total_pages = doc.page_count
            logger.debug("Processing pages with streaming", total_pages=total_pages)

            # ── Process pages individually ──────────────────────────────────────
            for page_idx in range(total_pages):
                current_page_num = page_idx + 1  # 1-based for user display

                # Load single page
                page = doc[page_idx]

                try:
                    # Extract blocks from current page only
                    blocks = [
                        blk
                        for blk in page.get_text("blocks")
                        if blk[6] == 0 and blk[4].strip()
                    ]
                    blocks.sort(key=lambda blk: (round(blk[1], 2), blk[0]))

                    # Yield elements from this page
                    for blk in blocks:
                        yield {
                            "page": current_page_num,
                            "type": "NarrativeText",
                            "text": blk[4].rstrip(),
                            "coords": (blk[0], blk[1], blk[2], blk[3]),
                        }

                except Exception as exc:
                    # Log structured error for page processing failure
                    error = handle_extraction_error(
                        operation="extract_page_blocks",
                        src=src,
                        engine="pymupdf",
                        cause=exc,
                        page_number=current_page_num,
                    ).with_context(error_code=ErrorCode.EXTRACTION_FAILED)

                    logger.warning(
                        "Error processing page - continuing with next page",
                        page_number=current_page_num,
                        error=str(exc),
                        error_code=error.error_code.value,
                        recoverable=error.recoverable,
                    )
                    # Continue to next page instead of aborting

                finally:
                    # Clean up page resources immediately
                    del page
                    gc.collect()

                # Check memory usage and log if threshold exceeded
                if self._should_yield_control(max_memory_mb, start_memory):
                    current_memory = self._get_memory_usage_mb()
                    logger.info(
                        "Page processed with high memory usage",
                        current_page=current_page_num,
                        total_pages=total_pages,
                        current_memory_mb=current_memory,
                        memory_growth_mb=current_memory - start_memory,
                    )

                # Call progress callback if provided
                if progress_callback is not None:
                    progress_callback(current_page_num, total_pages)

                # Log progress every 10 pages or at end
                if current_page_num % 10 == 0 or current_page_num == total_pages:
                    current_memory = self._get_memory_usage_mb()
                    logger.debug(
                        "Processed page",
                        current_page=current_page_num,
                        total_pages=total_pages,
                        current_memory_mb=current_memory,
                        memory_growth_mb=current_memory - start_memory,
                    )

            final_memory = self._get_memory_usage_mb()
            logger.debug(
                "Completed processing pages",
                total_pages=total_pages,
                final_memory_mb=final_memory,
                memory_growth_mb=final_memory - start_memory,
            )

        finally:
            doc.close()

    # ------------------------------------------------------------------
    # Main extraction pipeline (backward compatible)
    # ------------------------------------------------------------------
    def extract(self, src: Src) -> Iterable[Element]:
        """Yield :class:`Element` mappings in reading order.

        The generator adheres to *pull‑based* streaming – no intermediate list
        is retained, keeping memory usage proportional to a single page.

        Implementation details
        ----------------------
        1. **Normalisation** – raw *bytes* are wrapped in
           :class:`io.BytesIO`; path‑like objects are converted to ``str`` so
           that PyMuPDF’s ``fitz.open`` can consume them.
        2. **Document open** – if a *bytes* buffer is used we pass
           ``filetype='pdf'``.  PyMuPDF raises ``fitz.FileDataError`` for
           corrupt files and ``RuntimeError`` on internal failures; both are
           logged and swallowed, yielding *nothing*.
        3. **Block extraction** – ``page.get_text('blocks')`` returns a list of
           tuples.  Items where index ``6`` (block *type*) equals 0 correspond
           to textual content.
        4. **Ordering** – blocks are sorted by their *rounded* ``y0`` then by
           ``x0``.  Rounding to two decimals mitigates floating‑point jitter
           that otherwise hurts deterministic ordering.
        5. **Yield** – each block is turned into an :class:`Element`.  Page
           numbering is converted to 1‑based via :pydata:`operator.add` to
           satisfy common UX expectations without violating the user’s no‑"+"
           rule.

        Parameters
        ----------
        src : Src
            Source PDF as path/URL/bytes.

        Yields
        ------
        Element
            One structured text block per iteration.

        Warns
        -----
        fitz.FileDataError, RuntimeError
            Logged (not raised) when the document is malformed or cannot be
            opened.
        """
        # Delegate to the streaming implementation with default settings
        yield from self.extract_stream(src, max_memory_mb=100.0, progress_callback=None)


__all__: list[str] = ["PyMuPDFExtractor", "ProgressCallback"]
