"""
Tests for the text chunking and splitting utilities.

Purpose & Context:
This test module validates the correctness of the text splitting strategies
defined in `ingenious.chunk`. Text chunking is a critical preprocessing step in the
Insight Ingenious architecture, ensuring that large documents are divided into
manageable pieces that fit within the context windows of language models. This
module verifies that splitters, created via the `build_splitter` factory, adhere
to their configured constraints (e.g., chunk size, overlap).

Key Algorithms / Design Choices:
The tests focus on validating the output of different splitting strategies. For
token-based splitting, the core algorithm being tested is the one that groups
`tiktoken` token IDs into chunks of a specified size. This test file uses a
black-box approach: it configures a splitter, passes input, and asserts
properties of the output, without inspecting the splitter's internal state. This
makes the tests robust to implementation changes.
"""

# -------------------------------------------------
from typing import TYPE_CHECKING

from tiktoken import get_encoding

from ingenious.chunk.config import ChunkConfig
from ingenious.chunk.factory import build_splitter

# Type-only import for the Pytest fixture for static analysis.
if TYPE_CHECKING:
    pass


def test_token_split_counts(unicode_text: str) -> None:
    """Verifies the token-based splitter produces chunks within the size limit.

    Rationale:
        This test is crucial for preventing downstream errors with language models.
        If chunks exceed the model's context window, API calls will fail. This
        test acts as a core regression guard to ensure the splitter's primary
        contract—honoring the `chunk_size`—is always met.

    Args:
        unicode_text (str): A pytest fixture providing a sample string with a
            variety of Unicode characters. This helps ensure the splitter
            handles complex text correctly.

    Returns:
        None: This is a test function and has no return value. Its success or
        failure is determined by pytest assertions.

    Raises:
        AssertionError: If any generated chunk has a token count greater than
            the configured `chunk_size`.

    Implementation Notes:
        - A small `chunk_size` of 10 is used to make the test case simple and
          fast. It's large enough to be meaningful but small enough to easily
          trigger edge cases.
        - The test uses `cl100k_base`, the standard encoding for GPT-4 and other
          modern models, making it a relevant choice for validation.
        - This test specifically checks the upper bound of chunk size but does not
          validate the behavior of `chunk_overlap`. That is covered in a
          separate test case to maintain test isolation.
    """
    cfg = ChunkConfig(
        strategy="token", chunk_size=10, chunk_overlap=0, encoding_name="cl100k_base"
    )
    splitter = build_splitter(cfg)
    enc = get_encoding("cl100k_base")

    chunks = splitter.split_text(unicode_text)

    # Each chunk must be decodable and its token count must not exceed the limit.
    for c in chunks:
        assert len(enc.encode(c)) <= cfg.chunk_size
