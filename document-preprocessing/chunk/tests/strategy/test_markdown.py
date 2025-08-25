"""
Tests for Markdown-aware token splitting
=======================================

Purpose & context
-----------------
This pytest module validates that the *markdown* chunking strategy keeps
section semantics intact by ensuring Markdown headings remain at the
start of each produced chunk. It belongs to the Insight Ingenious
*chunk* test‑suite and protects `ingenious.chunk.strategy.markdown` from
regressions.

Key algorithms / design choices
-------------------------------
* **Factory usage** – Construction of the splitter is delegated to
  :pyfunc:`ingenious.chunk.factory.build_splitter` so the test exercises
  the public API rather than an internal class.
* **Fixture-driven I/O** – The parameter *sample_md* declares the input
  Markdown document as a pytest fixture, keeping the test fast and
  self‑contained.
"""

from pathlib import Path

from ingenious.chunk.config import ChunkConfig
from ingenious.chunk.factory import build_splitter


def test_markdown_respects_headings(sample_md: Path) -> None:
    """Validate that Markdown headings are preserved at chunk boundaries.

    Rationale
    ---------
    The downstream LLM pipeline relies on heading tokens (`#`, `##`, ...)
    being present at the start of each chunk to reconstruct document
    structure during retrieval‑augmented generation. If the splitter
    drops or repositions headings, contextual information is lost.

    Args
    ----
    sample_md: Path
        Pytest fixture pointing to a Markdown file that contains a top‑
        level heading ``# Title`` and a sub‑heading ``## Subtitle``.

    Raises
    ------
    AssertionError
        If the produced chunks do **not** begin with ``# Title`` or if no
        chunk contains ``## Subtitle``.
    """

    cfg = ChunkConfig(strategy="markdown", chunk_size=40, chunk_overlap=0)
    splitter = build_splitter(cfg)

    md_text = sample_md.read_text()
    chunks = splitter.split_text(md_text)

    # Ensure heading separators are honoured
    assert chunks[0].startswith("# Title")
    assert any("## Subtitle" in c for c in chunks)
