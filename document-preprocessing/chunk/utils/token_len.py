"""
Provides a fast, cached utility for calculating token length.

Purpose & Context
-----------------
This module offers a simple function, `token_len`, to count the number of
tokens in a string according to a specific `tiktoken` encoding. It is a
foundational utility within the Insight Ingenious architecture, primarily used by
text processing and chunking strategies in `ingenious.chunk`. These strategies
must frequently calculate token lengths to ensure that text segments adhere to
the context window limits of Large Language Models (LLMs).

Key Algorithms & Design Choices
-------------------------------
The core of this module's design is performance and resource management. The
`tiktoken.get_encoding()` function can be computationally expensive as it loads
large encoding vocabularies. To mitigate this, this module employs a
memoization pattern using `functools.lru_cache`.

- **Bounded LRU Cache:** The `_enc` helper function caches `tiktoken.Encoding`
  instances with a Least Recently Used (LRU) strategy. This ensures that for
  any given run, an `Encoding` object is created only once per encoding name.
  The cache is *bounded* to prevent unbounded memory growth in long-running
  workers that might encounter many different model or encoding names over time.
- **Configurability:** The cache size is configurable via the environment
  variable `INGENIOUS_TOKEN_CACHE_SIZE`, allowing operators to tune memory
  usage based on deployment needs. It defaults to a sensible value of 32.

Usage Example
-------------
The module provides a single public function, `token_len`.

.. code-block:: python

    from ingenious.chunk.utils.token_len import token_len

    # Calculate token length using the default encoding ('cl100k_base')
    # This encoding is used by GPT-3.5 and GPT-4 models.
    text_one = "Insight Ingenious helps build robust AI agents."
    num_tokens = token_len(text_one)
    print(f"'{text_one}' -> {num_tokens} tokens")
    # >>> 'Insight Ingenious helps build robust AI agents.' -> 8 tokens

    # Use a different encoding, e.g., for older models
    text_two = "Old models use different tokenizers."
    num_tokens_p50k = token_len(text_two, enc_name="p50k_base")
    print(f"'{text_two}' -> {num_tokens_p50k} tokens (p50k_base)")
    # >>> 'Old models use different tokenizers.' -> 6 tokens (p50k_base)
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import TYPE_CHECKING

# The `tiktoken` library is a performance-critical dependency.
# It is developed by OpenAI for fast BPE tokenization.
import tiktoken

if TYPE_CHECKING:
    from tiktoken import Encoding

# --------------------------------------------------------------------------- #
# Configurable Cache Bound for Memoized Encoding Objects                      #
# --------------------------------------------------------------------------- #
_CACHE_SIZE: int
try:
    # Read cache size from env var for deployment-time configuration.
    _CACHE_SIZE = max(1, int(os.getenv("INGENIOUS_TOKEN_CACHE_SIZE", "32")))
except (ValueError, TypeError):  # Fall back to default if var is invalid.
    _CACHE_SIZE = 32


@lru_cache(maxsize=_CACHE_SIZE)
def _enc(name: str) -> Encoding:
    """Returns and memoizes a `tiktoken` encoding instance using an LRU cache.

    This private helper is the core of the module's performance optimization.
    It prevents the expensive re-initialization of `Encoding` objects.

    Args:
        name: A valid `tiktoken` encoding name (e.g., "cl100k_base").

    Returns:
        A cached `tiktoken.Encoding` object for the given name.
    """
    return tiktoken.get_encoding(name)


def token_len(text: str, enc_name: str = "cl100k_base") -> int:
    """Calculates the number of tokens in a text for the requested encoding.

    Rationale:
        This function provides a simple, high-performance API for a very common
        task in the Insight Ingenious framework. The default encoding,
        `cl100k_base`, was chosen as it is the standard for modern OpenAI
        models (GPT-3.5-Turbo, GPT-4) and is therefore the most frequent use
        case. The actual tokenization logic is delegated to the highly
        optimized `tiktoken` library, while caching is handled transparently by
        the internal `_enc` helper.

    Args:
        text: The text string for which to calculate the token length.
        enc_name: The name of the `tiktoken` encoding to use. Must be a name
            that `tiktoken.get_encoding()` can resolve. Defaults to
            "cl100k_base".

    Returns:
        The exact number of tokens in the input `text`.

    Raises:
        KeyError: If `enc_name` is not a valid encoding name recognized by the
            `tiktoken` library. Callers should be prepared to handle this
            exception, for instance, by logging the error and falling back to a
            default chunking strategy.

    Implementation Notes:
        The first call for a given `enc_name` will be slower as it triggers
        the loading and instantiation of the `Encoding` object. Subsequent
        calls with the same `enc_name` will be significantly faster due to the
        LRU cache in the `_enc` function. The computational complexity of the
        `encode` method itself is approximately linear, $O(N)$, with respect
        to the length of the input `text`.
    """
    if not text:
        return 0
    # Retrieve the (potentially cached) encoding object and count tokens.
    encoder = _enc(enc_name)
    return len(encoder.encode(text, disallowed_special=()))
