"""
Ensures chunker token budgets are honored with custom encodings.

Purpose & Context
-----------------
This module provides a regression test for issue M-7. The core problem
addressed is ensuring that when a custom ``encoding_name`` is supplied via
``ChunkConfig``, all token-based splitting strategies correctly use the
corresponding tokenizer to calculate chunk size. This is critical for the
Insight Ingenious architecture, where different models (e.g., via different
agents) may use different tokenizers (e.g., `cl100k_base` for GPT-4 vs.
`p50k_base` for older models). Failure to honor the specified encoding could
lead to oversized chunks, causing downstream API errors or silent truncation.

This test file is located under ``ingenious/chunk/tests/`` and validates the
behavior of the splitter factory and its constructed strategies in
``ingenious/chunk/``.

Key Algorithms & Design Choices
-------------------------------
The test employs a matrix-based validation approach using ``pytest``'s
parameterization feature. It iterates through a combination of:
1.  **Splitting Strategies**: All strategies that support token-based sizing
    (`recursive`, `markdown`, `token`) are included, plus the `semantic`
    strategy as a control case.
2.  **Encodings**: A list of non-default ``tiktoken`` encodings.

To isolate the chunking logic, external services (OpenAI and Azure embedding
APIs) are mocked using ``unittest.mock.patch``. This makes the test suite
fast, deterministic, and runnable without network access or API keys.

A key design decision is the special handling for the "semantic" strategy. Since
semantic chunking groups text by topic rather than token count, it is
explicitly exempted from the token budget assertion. This prevents a false
negative and correctly reflects the strategy's intended behavior.
"""

from __future__ import annotations

from itertools import product
from typing import List
from unittest.mock import MagicMock, patch

import pytest
from tiktoken import get_encoding

from ingenious.chunk.config import ChunkConfig
from ingenious.chunk.factory import build_splitter

# --------------------------------------------------------------------------- #
# Test‑matrix parameters
# --------------------------------------------------------------------------- #
ENCODINGS: List[str] = ["p50k_base", "r50k_base"]  # Non-default encodings
STRATEGIES: List[str] = ["recursive", "markdown", "token", "semantic"]

TEXT = "alpha beta gamma delta " * 200  # Large enough to force splits
CHUNK_SIZE = 32
OVERLAP = 8
# A relaxed budget to account for how some splitters add overlap. The effective
# maximum size of a chunk can be slightly larger than CHUNK_SIZE.
MAX_ALLOWED = CHUNK_SIZE + 2 * OVERLAP


def _fake_embedder() -> MagicMock:
    """
    Creates a mock embedding object to prevent real network calls during tests.

    Rationale:
        This test helper isolates the chunking logic from external dependencies
        like the OpenAI or Azure embedding services. Using a ``MagicMock``
        ensures that tests are fast, deterministic, and can execute in
        environments without network access or API credentials, adhering to
        DI-101 testing principles.

    Returns:
        MagicMock:
            An object simulating an embedding model, with a side effect
            configured for its ``embed_documents`` method.

    """
    stub = MagicMock()
    stub.embed_documents.side_effect = lambda txts: [[0.0] * 5 for _ in txts]
    return stub


# --------------------------------------------------------------------------- #
# Parametrised test
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("enc_name,strategy", product(ENCODINGS, STRATEGIES))
@patch(
    "ingenious.chunk.strategy.langchain_semantic.OpenAIEmbeddings",
    return_value=_fake_embedder(),
)
@patch(
    "ingenious.chunk.strategy.langchain_semantic.AzureOpenAIEmbeddings",
    return_value=_fake_embedder(),
)
def test_encoding_override_budget(_, __, enc_name: str, strategy: str) -> None:
    """
    Verifies that token-based splitters respect the configured ``encoding_name``.

    Rationale:
        This test directly addresses regression issue M-7. By parameterizing
        over multiple strategies and encodings, it provides robust coverage to
        ensure that a custom tokenizer setting is correctly propagated from
        the ``ChunkConfig`` to the underlying splitter implementation. This
        prevents oversized chunks when using models with different tokenizers.

    Args:
        _:
            MagicMock patch for ``OpenAIEmbeddings``. Ignored in the test body.
        __:
            MagicMock patch for ``AzureOpenAIEmbeddings``. Ignored.
        enc_name (str):
            The name of the ``tiktoken`` encoding to test (e.g., "p50k_base").
            Injected by ``pytest.mark.parametrize``.
        strategy (str):
            The name of the chunking strategy to test (e.g., "recursive").
            Injected by ``pytest.mark.parametrize``.

    Raises:
        AssertionError: If a splitter produces no chunks or if any chunk's
            token count exceeds the maximum allowed budget for its strategy.

    Implementation Notes:
        - The "semantic" strategy is explicitly skipped from the budget check
          as it chunks based on thematic breaks, not token counts.
        - The check for chunk content handles both raw strings and LangChain
          ``Document`` objects to make the test resilient to the splitter's
          return type.
        - The maximum allowed budget is relaxed to ``CHUNK_SIZE + 2 * OVERLAP``
          to accommodate how some strategies handle overlapping text.
    """
    cfg = ChunkConfig(
        strategy=strategy,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=OVERLAP,
        encoding_name=enc_name,
    )
    splitter = build_splitter(cfg)

    chunks = splitter.split_text(TEXT)
    assert chunks, "Splitter produced no chunks, making the test invalid."

    # The semantic strategy intentionally ignores `chunk_size` for sizing,
    # so we skip the budget assertion for it. Its purpose is different.
    if strategy == "semantic":
        return

    enc = get_encoding(enc_name)
    assert all(
        len(enc.encode(c if isinstance(c, str) else c.page_content)) <= MAX_ALLOWED
        for c in chunks
    ), f"Strategy '{strategy}' with encoding '{enc_name}' emitted an over-budget chunk."
