"""
Provides a utility to inject contextual overlap between ordered text chunks.

Purpose & context
-----------------
This module solves the common problem of maintaining context between discrete text
chunks in Retrieval-Augmented Generation (RAG) pipelines. When a large document is
split into smaller pieces, splitting can occur at arbitrary points, severing
sentences or ideas. By prepending the tail of the previous chunk to the current
one, we ensure that the local context is preserved, which improves the performance
of downstream language models and embedding models.

This function is a core utility within the `ingenious/chunk` sub-package, designed
to be a shared, reusable component for any chunking strategy that requires overlap.
It supports both raw strings and LangChain `Document` objects to maintain
flexibility across different data processing flows.

Key algorithms / design choices
-------------------------------
1.  **Iterative Overlap Injection**: The function iterates through the input chunks
    and builds a new list. For each chunk, it takes the tail of the *previously
    processed* (and already overlapped) chunk from the output list. This ensures a
    consistent, rolling context window.
2.  **Generic Type Handling**: It uses `typing.TypeVar` and `@overload` to provide
    static type safety for inputs of `list[str]` or `list[Document]`, ensuring the
    output type matches the input type.
3.  **Data Isolation**: When processing `Document` objects, `copy.deepcopy` is used
    for the `metadata` dictionary. This prevents unintentional side effects where
    modifying one document's metadata would alter another's, a critical safeguard in
    our multi-agent architecture.
4.  **Soft-Delimiter Rule**: A helper function (`_concat`) intelligently inserts a
    space when joining text fragments that both end and start with non-whitespace
    characters. This mitigates token fusion issues (e.g., "word" + "one" -> "wordone")
    that can arise from aggressive text splitting.
"""

from __future__ import annotations

from copy import deepcopy
from typing import List, Sequence, TypeVar, overload

from langchain_core.documents import Document

from .token_len import _enc

T = TypeVar("T", str, Document)


# --------------------------------------------------------------------------- #
# Public overloads                                                            #
# --------------------------------------------------------------------------- #
@overload
def inject_overlap(
    chunks: List[str],
    k: int,
    *,
    unit: str = "tokens",
    enc_name: str = "cl100k_base",
) -> List[str]: ...


@overload
def inject_overlap(
    chunks: List[Document],
    k: int,
    *,
    unit: str = "tokens",
    enc_name: str = "cl100k_base",
) -> List[Document]: ...


# --------------------------------------------------------------------------- #
# Implementation                                                              #
# --------------------------------------------------------------------------- #
def inject_overlap(
    chunks: Sequence[T],
    k: int,
    *,
    unit: str = "tokens",
    enc_name: str = "cl100k_base",
) -> List[T]:
    """Prepends overlapping content from the previous chunk to each chunk.

    This function creates a new list of chunks where each element (from the
    second onwards) is prefixed with the last `k` units (tokens or characters)
    of the preceding, already-processed chunk.

    Rationale:
        This implementation was chosen for its clarity and robustness. The
        iterative approach is easy to reason about. Using helper functions for
        tail extraction (`_tail`) and concatenation (`_concat`) isolates logic.
        Deep-copying document metadata is a deliberate design choice to prevent
        aliasing bugs in the wider framework. Supporting both tokens and
        characters makes the utility versatile for various chunking strategies.

    Args:
        chunks: An ordered sequence of `str` or `langchain_core.documents.Document`
            to process.
        k: The desired size of the overlap. Must be a non-negative integer.
        unit: The unit for measuring overlap: 'tokens' or 'characters'.
            Defaults to 'tokens'.
        enc_name: The name of the `tiktoken` encoder to use when `unit` is
            'tokens'. Defaults to 'cl100k_base', used by GPT-3.5/4.

    Returns:
        A new list of the same type `T` with the specified overlap injected.
        The first chunk remains unchanged. If `k` is 0 or there are fewer
        than two chunks, a copy of the original list is returned.

    Raises:
        ValueError: If `unit` is not 'tokens' or 'characters'.

    Implementation notes:
        - The function has a time complexity of roughly $O(N cdot L)$, where $N$
          is the number of chunks and $L$ is their average length, due to
          string operations and tokenization within the loop.
        - The overlap is taken from the tail of the *previous output chunk*, not
          the original input chunk. This ensures the invariant:
          `output[i-1][-k:]` is prepended to `input[i]`.
        - The `type: ignore` comments are necessary because the type checker
          cannot statically prove that the `content` assigned to the output list
          matches the generic `T` in all branches, though the logic guarantees it.
    """
    if k == 0 or len(chunks) < 2:
        return list(chunks)

    if unit not in {"tokens", "characters"}:
        raise ValueError(f"unit must be 'tokens' or 'characters' (got {unit!r})")

    enc = _enc(enc_name)

    def _tail(text: str) -> str:
        """Return the last *k* tokens or characters of *text*."""
        if unit == "characters":
            return text[-k:]
        # For tokens, encode, slice the token IDs, and decode back to a string.
        return enc.decode(enc.encode(text)[-k:])

    def _concat(left: str, right: str) -> str:
        """Join *left* and *right*, guarding against token fusion.

        Inserts a space if the left string's last character and the right
        string's first character are both non-whitespace.
        """
        if left and right and not left[-1].isspace() and not right[0].isspace():
            return f"{left} {right}"
        return f"{left}{right}"

    # ---------------------------------------------------------------------- #
    out: List[T] = []
    for chunk in chunks:
        content: str = chunk if isinstance(chunk, str) else chunk.page_content

        # Prepend tail from the **last output** chunk, not the raw input.
        if out:
            prev_txt = (
                out[-1]  # The content of out[-1] is already overlapped.
                if isinstance(out[-1], str)
                else out[-1].page_content
            )
            content = _concat(_tail(prev_txt), content)

        if isinstance(chunk, str):
            out.append(content)
        else:  # Document
            # ⚠️ NEVER pass the original dict – downstream mutation would
            #    couple siblings. deep-copy for full isolation.
            out.append(
                Document(page_content=content, metadata=deepcopy(chunk.metadata))
            )

    return out
