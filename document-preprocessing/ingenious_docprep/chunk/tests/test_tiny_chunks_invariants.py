"""
Tests invariants for the text chunking algorithm.

Purpose & Context:
    This module contains pytest tests that verify critical invariants of the output
    produced by the text chunking component (located in `ingenious.chunk`).
    The primary goal is to ensure that every text chunk generated adheres to
    strict rules regarding maximum token size and inter-chunk overlap.

    These invariants are essential for the reliability of downstream consumers in the
    Insight Ingenious architecture, particularly Retrieval-Augmented Generation (RAG)
    agents. Predictable chunk sizes and correct overlaps guarantee that context is
    neither lost nor unnecessarily duplicated when chunks are ingested into a vector
    database or processed by a language model.

Key Algorithms & Design Choices:
    The tests are data-driven, operating on a pre-generated JSONL file provided by
    the `tiny_chunks_jsonl` pytest fixture. This decouples the tests from the
    live chunking process, allowing for focused validation of the chunker's output
    artifact.

    Tokenization is handled by `tiktoken` with the `cl100k_base` encoding, which
    is the standard for modern OpenAI models. This ensures that the token counts
    and sequences used for validation precisely match those seen by the LLMs.
    Assertions are performed on the token ID lists for robustness.

Usage Example:
    These tests are executed via the pytest runner. From the project root:

    .. code-block:: bash

        pytest ingenious/chunk/tests/test_tiny_chunks_invariants.py
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from tiktoken import get_encoding

# --- Constants ---
# Use the cl100k_base encoding, standard for GPT-3.5/4 models.
ENC = get_encoding("cl100k_base")

# Nominal chunk size and overlap size (in tokens). These must match the
# parameters used to generate the test fixture data.
CHUNK = 20
K = 10

# The chunker aims for CHUNK size but may exceed it to avoid splitting a word.
# The hard cap represents the absolute maximum size a chunk can be, accommodating
# the nominal chunk size, the overlap, and a small buffer.
HARD_CAP = CHUNK + K + 1  # 31


def _load(path: Path) -> List[Dict[str, Any]]:
    """Loads a JSON Lines (JSONL) file into a list of dictionaries.

    Rationale:
        This is a private helper function to encapsulate the file-reading and
        parsing logic, keeping the main test function clean and focused on the
        assertion logic. Reading line-by-line is efficient for the JSONL format.

    Args:
        path: The `pathlib.Path` object pointing to the JSONL file.

    Returns:
        A list of Python dictionaries, where each dictionary corresponds to a
        JSON object from a line in the input file.

    Raises:
        FileNotFoundError: If the `path` does not exist.
        json.JSONDecodeError: If a line in the file contains invalid JSON.
    """
    with path.open(encoding="utf-8") as fp:
        return [json.loads(line) for line in fp]


def test_chunk_size_and_overlap(tiny_chunks_jsonl: Path) -> None:
    """Verifies that generated chunks adhere to size and overlap invariants.

    Summary:
        This test validates two critical properties of the chunked output:
        1.  No chunk exceeds the pre-defined maximum token limit (`HARD_CAP`).
        2.  Consecutive chunks from the same source page have the correct
            token overlap (`K`).

    Rationale:
        This test is crucial for guaranteeing that the chunking output is
        predictable and well-formed. Incorrect chunking can lead to significant
        downstream issues in RAG systems, such as missed context or broken
        semantic units. By checking invariants on the tokenized output, the
        test ensures compatibility with language models and the retrieval index.
        The test operates on a fixture to remain independent of the chunker's
        execution, focusing solely on the correctness of its artifact.

    Args:
        tiny_chunks_jsonl: A pytest fixture that provides the `pathlib.Path` to
            a JSONL file containing chunked output to be tested.

    Raises:
        AssertionError: If any of the invariants are violated.

    Implementation Notes:
        - The test iterates through pairs of consecutive records to check for
          overlap. This is an efficient O(N) approach.
        - Overlap is only checked for chunks from the same page. This test
          assumes the input fixture contains records from a single document,
          making the page number a sufficient key for grouping.
        - The token lists are compared directly (`tail == head`), which is a
          robust method for confirming that the content of the overlap is
          identical.
    """
    recs = _load(tiny_chunks_jsonl)

    # 1️⃣ Verify that every chunk is smaller than or equal to the hard cap.
    #    This ensures that no chunk will exceed model context length limits.
    assert all(len(ENC.encode(r["text"])) <= HARD_CAP for r in recs)

    # 2️⃣ Verify that overlap is present and correct *within* the same page.
    #    No overlap is expected across page boundaries.
    for prev, curr in zip(recs, recs[1:]):
        # Only check for overlap if the page metadata matches. The test data is
        # assumed to be from a single source file.
        if prev["meta"]["page"] == curr["meta"]["page"]:
            prev_tokens = ENC.encode(prev["text"])
            curr_tokens = ENC.encode(curr["text"])

            tail = prev_tokens[-K:]
            head = curr_tokens[:K]

            assert tail == head, (
                f"Overlap mismatch on page {prev['meta']['page']}. "
                f"Expected head {head} to match tail {tail}."
            )
