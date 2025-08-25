"""
Purpose & context
-----------------
Exercises the public splitter factory against a *representative
parameter matrix* to guarantee that **chunk‑overlap behaviour** is
consistent across all officially supported strategies (``recursive``,
``markdown``, ``token``, ``semantic``). This test sits in the
*black‑box* layer: only the contract of ``build_splitter`` and **no
internal implementation details** are relied on.

Key algorithms / design choices
-------------------------------
* **Cartesian matrix** – Uses ``itertools.product`` to enumerate the
  cross‑product of strategies, overlap units and custom separator
  choices. This ensures that newly added strategies automatically
  participate in the test when they appear in ``_STRATEGIES``.
* **Unicode‑safe overlap assertion** – For *token* overlap the test
  obtains the project‑level encoding via ``tiktoken.get_encoding``.
  Character overlap is validated by direct slicing. This mirrors the
  behaviour inside the runtime splitter.
* **Embedding stub** – The semantic strategy relies on an embedder
  object; a **``unittest.mock.MagicMock``** stub is injected via
  ``patch`` to keep the test hermetic and deterministic.
"""

from itertools import product
from unittest.mock import MagicMock, patch

import pytest
from tiktoken import get_encoding

from ingenious.chunk.config import ChunkConfig
from ingenious.chunk.factory import build_splitter

# --------------------------------------------------------------------------- #
# Test‑matrix parameters                                                      #
# --------------------------------------------------------------------------- #
_STRATEGIES = ["recursive", "markdown", "token", "semantic"]
_UNITS = ["tokens", "characters"]
_SEPARATORS = ["", "---"]  # empty ⇒ default

_fake_embed = MagicMock()
_fake_embed.embed_documents.side_effect = lambda txts: [[0.0] * 5 for _ in txts]


# --------------------------------------------------------------------------- #
# Parametrised test                                                           #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "strategy,unit,sep",
    list(product(_STRATEGIES, _UNITS, _SEPARATORS)),
)
@patch(
    "ingenious.chunk.strategy.langchain_semantic.OpenAIEmbeddings",
    return_value=_fake_embed,
)
def test_param_surface(_, strategy: str, unit: str, sep: str):
    """Smoke‑test a single combination of the parameter matrix.

    Summary
    -------
    Ensures that the selected *chunking strategy* honours the configured
    ``overlap_unit`` for both **characters** and **tokens**.

    Rationale
    ---------
    A parametrised test is used instead of bespoke cases to reduce
    duplication and to guarantee coverage of edge interactions such as
    custom separator lists.

    Args
    ----
    strategy:
        Name of the chunking strategy under test.
    unit:
        The overlap unit, either ``"characters"`` or ``"tokens"``.
    sep:
        Custom separator string; an empty string delegates to the
        strategy's default separators.

    Raises
    ------
    AssertionError
        If the overlap contract is violated for the given combination.

    Notes
    -----
    When *semantic* strategy is paired with ``"characters"`` the
    combination is **unsupported** by design. The case is **skipped**
    early to communicate intent without failing the build.
    """

    # Skip the now‑invalid combination of semantic and characters
    if strategy == "semantic" and unit == "characters":
        pytest.skip("Semantic strategy does not support character overlap unit.")

    text = "alpha --- beta --- gamma " * 20
    cfg = ChunkConfig(
        strategy=strategy,
        chunk_size=32,
        chunk_overlap=8,
        overlap_unit=unit,
        separators=sep.split("|") if sep else None,
    )

    splitter = build_splitter(cfg)
    chunks = splitter.split_text(text)

    # -- sanity ----------------------------------------------------------- #
    assert len(chunks) >= 1  # Semantic can correctly return 1 chunk

    # Only check for overlap if there is something to overlap
    if len(chunks) < 2:
        return

    k = cfg.chunk_overlap
    enc = get_encoding(cfg.encoding_name)

    # -- invariant -------------------------------------------------------- #
    for i in range(1, len(chunks)):
        if unit == "characters":
            # exact last‑k characters must re‑appear at the next head
            assert chunks[i - 1][-k:] == chunks[i][:k]
        else:  # tokens
            prev_tail = enc.decode(enc.encode(chunks[i - 1])[-k:])
            head_text = chunks[i][: len(prev_tail) + 2]  # allow space token
            assert head_text.lstrip().startswith(prev_tail.lstrip())
