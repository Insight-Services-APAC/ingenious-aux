"""
Build an **independent**, LangChain‑compatible ``TextSplitter`` from a frozen
:class:`~ingenious.chunk.config.ChunkConfig`.

Purpose & context
-----------------
The Insight Ingenious framework supports several *chunking* strategies that
convert raw documents into token‑bounded segments suitable for downstream
indexing, retrieval and LLM ingestion.  This module provides the
**single entry‑point** ``build_splitter`` that

1.  Deserialises a *frozen* :class:`~ingenious.chunk.config.ChunkConfig` that is
    typically produced by CLI parsers or agent flows.
2.  Resolves the **strategy factory** registered under
    ``cfg.strategy`` (`token`, `char`, `semantic`, …).
3.  Returns a **thread‑local clone** of a *prototype* splitter, guaranteeing
    that concurrent requests never share mutable buffers.

Key algorithms / design choices
-------------------------------
* **LRU prototype cache** – Pure‑Python strategies incur a one‑time cost (regex
  compilation, tokenizer warm‑up).  A size‑bounded ``functools.lru_cache`` keeps
  *prototypes* so that clones can be served in ~O(1) without re‑initialisation.
* **Live‑instance deque** – To prevent premature ``id()`` recycling during
  high‑concurrency tests we retain strong references to the most recent
  instances in a bounded :pyclass:`collections.deque` guarded by a
  :pyclass:`threading.Lock`.
* **Semantic strategy bypass** – The *semantic* splitter relies on live vector
  embeddings and is therefore **never cached**; every call builds it afresh.

Usage example
-------------
```python
from ingenious.chunk.config import ChunkConfig
from ingenious.chunk.factory import build_splitter

cfg = ChunkConfig(strategy="token", chunk_size=512, overlap=64)
splitter = build_splitter(cfg)

text = "Lorem ipsum …"
chunks = splitter.split_text(text)
```
"""

from __future__ import annotations

# ── standard library ──────────────────────────────────────────────────────
import copy
import json
import os
import threading
from collections import deque
from functools import lru_cache
from typing import Deque

# ── local project ─────────────────────────────────────────────────────────
from .config import ChunkConfig
from .strategy import _SPLITTER_REGISTRY
from .strategy import get as _get_strategy

__all__ = ["build_splitter"]

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_text_splitters.base import TextSplitter

# ======================================================================= #
# 0. Configuration knobs – overridable via environment variables           #
# ======================================================================= #

# Size of the **prototype LRU cache**. 64 is a practical default: large enough
# to cover the Cartesian product of strategies × typical unit‑test configs yet
# small enough to avoid unbounded growth in long‑running services.
try:
    _CACHE_SIZE: int = max(1, int(os.getenv("INGENIOUS_SPLITTER_CACHE", "64")))
except ValueError:  # non‑integer value provided
    _CACHE_SIZE = 64

# Size of the **live‑instance deque**.  Keeps strong refs so that ``id()``
# values are not recycled while tests that capture splitter identities are
# still running.  Defaults to 128× the prototype cache but can be tuned via
# ``INGENIOUS_SPLITTER_LIVE``.
try:
    _LIVE_BOUND: int = max(
        _CACHE_SIZE,  # always ≥ the prototype cache
        int(os.getenv("INGENIOUS_SPLITTER_LIVE", str(_CACHE_SIZE * 128))),
    )
except ValueError:
    _LIVE_BOUND = _CACHE_SIZE * 128

# ── bounded keeper + lock --------------------------------------------------
_LIVE_INSTANCES: Deque[object] = deque(maxlen=_LIVE_BOUND)
_LIVE_LOCK = threading.Lock()  # single global guard – minimal contention


# ======================================================================= #
# 1. Prototype cache – build **once**, clone thereafter                     #
# ======================================================================= #
@lru_cache(maxsize=_CACHE_SIZE)
def _cached_build_splitter(cfg_json: str) -> "TextSplitter":
    """Return a **prototype** splitter for the *exact* *cfg_json*.

    Summary
    -------
    Materialises a splitter once and stores it in the ``lru_cache`` under the
    serialised config key.  Subsequent callers receive the cached object and
    are responsible for shallow‑/deep‑cloning.

    Rationale
    ---------
    Prototype caching removes expensive initialisation work while still
    allowing per‑call isolation via cloning in :pyfunc:`build_splitter`.

    Args
    ----
    cfg_json:
        JSON string produced by :pymeth:`ChunkConfig.model_dump` *(immutable
        and hashable)*.

    Returns
    -------
    langchain.text_splitter.TextSplitter
        Strategy‑specific splitter whose mutable state **must not** be shared
        between threads.
    """

    cfg_dict = json.loads(cfg_json)
    cfg = ChunkConfig(**cfg_dict)
    return _get_strategy(cfg.strategy)(cfg)


# ======================================================================= #
# 2. Public façade – build_splitter                                        #
# ======================================================================= #


def build_splitter(cfg: ChunkConfig) -> "TextSplitter":
    """Instantiate an **independent** splitter that honours *cfg*.

    Summary
    -------
    Convert a frozen :class:`~ingenious.chunk.config.ChunkConfig` into a fully
    initialised, thread‑local LangChain ``TextSplitter``.

    Rationale
    ---------
    Maintainers and agent flows need a **single authoritative API** to obtain
    splitters without worrying about caching, cloning, or concurrency.

    Args
    ----
    cfg:
        Immutable chunking configuration object produced by
        :pymeth:`ingenious.chunk.config.ChunkConfig.freeze`.

    Returns
    -------
    langchain.text_splitter.TextSplitter
        A fresh splitter instance whose internal buffers are **not** shared
        with any other thread or coroutine.

    Raises
    ------
    ValueError
        If ``cfg.strategy`` is not registered in
        :data:`ingenious.chunk.strategy._SPLITTER_REGISTRY`.

    Implementation notes
    --------------------
    * For the *semantic* strategy the function bypasses caching because the
      splitter embeds text on‑the‑fly using live vector stores.
    * The cloning pipeline follows a 3‑tier fall‑back:

        1. ``copy.copy`` – fastest and sufficient for most strategies.
        2. ``copy.deepcopy`` – handles nested mutable fields when the strategy
           uses pure‑Python objects that support pickling.
        3. Rebuild from scratch – guarantees progress if both copy paths fail.
    """

    # ── 2‑A. Guard against corrupted configs early ----------------------
    if cfg.strategy not in _SPLITTER_REGISTRY:
        raise ValueError(f"Unknown chunking strategy: {cfg.strategy!r}")

    # ── 2‑B. Semantic strategy – always fresh --------------------------
    if cfg.strategy == "semantic":
        inst = _get_strategy(cfg.strategy)(cfg)
        with _LIVE_LOCK:  # atomic append
            _LIVE_INSTANCES.append(inst)
        return inst

    # ── 2‑C. Pure‑Python strategies – cache prototype ------------------
    proto_key = json.dumps(
        cfg.model_dump(exclude_none=False, mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    prototype = _cached_build_splitter(proto_key)

    # 2‑C‑1. Shallow clone (fast path)
    clone = copy.copy(prototype)

    # 2-C-2. Deep clone if shallow returns identity
    if clone is prototype:
        try:
            clone = copy.deepcopy(prototype)
        except Exception:  # noqa: BLE001 – any pickle failure
            # 2-C-3. Last resort – build from scratch
            clone = _get_strategy(cfg.strategy)(cfg)

    # 2‑C‑3. Last resort – build from scratch
    if clone is None or clone is prototype:
        clone = _get_strategy(cfg.strategy)(cfg)

    # ── 2‑D. Book‑keeping – retain strong ref --------------------------
    with _LIVE_LOCK:
        _LIVE_INSTANCES.append(clone)

    return clone
