"""
Purpose & Context
-----------------
The helper converts an arbitrary *source* representation (file‑system path
or opaque string) into a deterministic *identifier prefix* embedded in every
chunk ID produced by the Insight Ingenious chunk writer.  By centralising the
logic here we guarantee that **all** components (agents, CLI, interactive
APIs) treat a document origin the same way, which is crucial for deduplication,
traceability and reproducible hashing across distributed workers.

Key Algorithms / Design Choices
-------------------------------
* **Three operation modes** – ``abs``, ``rel`` and ``hash`` – cover the most
  common privacy vs. readability trade‑offs without over‑engineering.
* **Salted SHA‑256 digest** – ubiquitously available in the standard library
  and fast enough even for billions of inputs.  A configurable bit‑length
  provides a knob for corpus scale without changing the algorithm.
* **Pure function** – the implementation performs *zero* I/O and mutates no
  global state, so it can be safely called from threads, subprocess pools or
  within async task executors.
* **Unicode‑safety** – all strings are processed and returned as UTF‑8, with
  the ``surrogatepass`` error handler to preserve lone surrogates that may
  appear on broken file systems.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Union

from ..config import ChunkConfig

# --------------------------------------------------------------------------- #
# Helper – digest truncation                                                  #
# --------------------------------------------------------------------------- #


def _trunc_digest(data: str, bits: int) -> str:
    """Return a truncated SHA‑256 hex digest for *data*.

    Summary
        Compute the SHA‑256 of *data* and return the first ``bits / 4`` hex
        characters.

    Rationale
        SHA‑256 is both ubiquitous and sufficiently strong; truncating keeps
        identifiers human‑manageable while offering collision probabilities
        appropriate for multi‑billion‑chunk corpora (see ticket #432).

    Args
        data: Arbitrary string to hash (UTF‑8 encoded with ``surrogatepass``).
        bits: Requested digest length in **bits**.  Must be a multiple of 4 so
            we cut on whole‑nibble boundaries.

    Returns
        str: Hexadecimal digest with exactly ``bits / 4`` characters.

    Raises
        ValueError: If *bits* is not divisible by 4.

    Implementation Notes
        The helper is kept separate to make the math obvious and to allow
        targeted unit tests (see ``tests/utils/test_id_path.py``).
    """
    if bits % 4 != 0:
        raise ValueError("id_hash_bits must be a multiple of 4")

    hex_len = bits // 4  # 1 hex digit = 4 bits
    return hashlib.sha256(data.encode("utf-8", "surrogatepass")).hexdigest()[:hex_len]


# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #


def _norm_source(src: Union[str, Path], cfg: ChunkConfig) -> str:
    """Normalise *src* to the canonical identifier prefix.

    Summary
        Convert a user‑supplied *source* reference into the deterministic
        representation dictated by ``cfg.id_path_mode``.  The output is a
        POSIX‑style string suitable for embedding in chunk IDs.

    Rationale
        A single canonicaliser avoids subtle inconsistencies and ensures that
        deduplication, filtering and metrics always agree on document identity.

    Args
        src: File‑system path (``str`` | ``Path``) **or** any opaque string
            (e.g. URL, S3 key).  Non‑path inputs are treated as opaque and
            directly hashed when required.
        cfg: Immutable :class:`~ingenious.chunk.config.ChunkConfig` whose
            relevant fields (**id_path_mode**, **id_hash_bits**, **id_base**)
            have already been validated at construction time.

    Returns
        str: POSIX‑style path segment (no back‑slashes) ready for chunk IDs.

    Raises
        ValueError: Propagated from :func:`_trunc_digest` when an invalid
            *id_hash_bits* is supplied via *cfg*.

    Implementation Notes
        * Resolution is performed with ``strict=False`` so broken symlinks still
          map to deterministic identifiers.
        * For ``rel`` mode we hash the *absolute* path when outside *id_base*
          to avoid collisions between identically named files in different
          directories.
        * ``hash`` mode prepends a user‑supplied *salt* (``cfg.id_base``)
          enabling namespace separation across projects.
    """
    raw = str(src)  # accept Path | str uniformly

    # 1) Try to resolve the input to an absolute POSIX path.  If this fails
    #    (e.g. on invalid bytes or Windows UNC issues) we fall back to hashing
    #    the raw string so the caller still receives a unique identifier.
    try:
        p = Path(raw).resolve(strict=False)
    except (OSError, ValueError):
        return _trunc_digest(raw, cfg.id_hash_bits)

    mode = cfg.id_path_mode

    # 2) abs‑mode – return fully qualified path for maximum transparency.
    if mode == "abs":
        return p.as_posix()

    # 3) rel‑mode – use a readable relative path when inside *id_base*;
    #    otherwise hash to disambiguate equal names in different directories.
    if mode == "rel":
        base = (cfg.id_base or Path.cwd()).resolve()
        try:
            return p.relative_to(base).as_posix()
        except ValueError:
            return _trunc_digest(p.as_posix(), cfg.id_hash_bits)

    # 4) hash‑mode – always return a salted digest.
    salt = cfg.id_base.as_posix() if cfg.id_base else ""
    return _trunc_digest(f"{salt}:{p.as_posix()}", cfg.id_hash_bits)
