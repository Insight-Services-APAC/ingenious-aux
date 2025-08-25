"""
Purpose & Context:
    This module contains the `pytest` unit tests for the text splitting
    functionality defined in `ingenious.chunk`. The chunking components are
    a foundational part of the Insight Ingenious architecture, responsible for
    preparing large documents for processing by language models. Correct chunking
    is critical for retrieval-augmented generation (RAG) flows and other agent
    behaviors that depend on processing text segments. These tests ensure that
    the various splitting strategies are reliable, performant, and behave as
    specified.

Key Algorithms & Design Choices:
    The tests are designed to be self-contained and validate specific behaviors
    of the `build_splitter` factory and the splitters it produces. Each test
    focuses on a distinct feature, such as adherence to `chunk_size` or correct
    implementation of `chunk_overlap`. We use token-level assertions via the
    `tiktoken` library to verify correctness, as this is how LLMs will ultimately
    "see" the chunks.
"""

from tiktoken import get_encoding

from ingenious.chunk.config import ChunkConfig
from ingenious.chunk.factory import build_splitter


def test_recursive_respects_overlap():
    """Verifies the recursive splitter correctly implements `chunk_overlap`.

    Rationale:
        This is a critical regression test for the chunking mechanism. An
        incorrect overlap implementation can lead to a loss of semantic context
        between consecutive chunks, which severely degrades the performance of
        downstream RAG and summarization agents. This test provides confidence
        that the boundary condition between chunks is correctly maintained.

    Raises:
        AssertionError: If the last `chunk_overlap` tokens of a preceding
            chunk do not exactly match the first `chunk_overlap` tokens of the
            succeeding chunk.

    Implementation Notes:
        The test constructs a long, repetitive string (`"A " * 300`) to ensure
        that tokenization is uniform and predictable. It then configures a
        splitter with a specific `chunk_size` and `chunk_overlap` (in tokens).

        The core assertion logic iterates through the generated chunks and uses
        the `tiktoken` encoder to compare the token IDs. It checks that the
        slice of tokens at the end of chunk `i-1` is identical to the slice of
        tokens at the beginning of chunk `i`, where the slice size is equal to
        the configured overlap. The token count is used as the ground truth,
        as this is the unit the `RecursiveCharacterTextSplitter` from LangChain
        (which this system uses) operates on.
    """
    # 1. ARRANGE: Create a long, simple text and a config with overlap.
    text = "A " * 300
    cfg = ChunkConfig(strategy="recursive", chunk_size=20, chunk_overlap=5)
    splitter = build_splitter(cfg)
    enc = get_encoding(cfg.encoding_name)

    # 2. ACT: Split the text into chunks.
    chunks = splitter.split_text(text)

    # 3. ASSERT: Verify the overlap is present and correct at the token level.
    for i in range(1, len(chunks)):
        previous_chunk_tokens = enc.encode(chunks[i - 1])
        current_chunk_tokens = enc.encode(chunks[i])

        # The last `chunk_overlap` tokens of the previous chunk should match
        # the first `chunk_overlap` tokens of the current one.
        assert (
            previous_chunk_tokens[-cfg.chunk_overlap :]
            == current_chunk_tokens[: cfg.chunk_overlap]
        )
