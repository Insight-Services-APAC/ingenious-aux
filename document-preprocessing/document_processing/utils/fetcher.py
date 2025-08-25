"""
Insight Ingenious – Remote-source fetch helper
=============================================

A tiny, **fail-soft** helper that downloads HTTP/S resources for downstream
extractors.  The helper makes no assumptions about the payload type: it simply
returns the raw bytes or *None* if the resource cannot be retrieved safely.

Responsibilities
----------------
1. **URL validation** – a lightweight regular-expression gate keeps non-HTTP/S
   strings out of the download path.
2. **Streaming download** – content is streamed in 16 KiB chunks so very large
   files never reach memory if they exceed the configured quota.
3. **Safety guard** – an upper-bound (MiB) aborts oversize transfers early,
   protecting both memory and bandwidth.  The limit is controlled by the
   ``INGEN_MAX_DOWNLOAD_MB`` environment variable (default: 20 MiB).
4. **Timeout budget** – the entire request must complete within the number of
   seconds defined by ``INGEN_URL_TIMEOUT_SEC`` (default: 30 s).
5. **Fail-soft semantics** – *all* network and size errors are logged at
   **WARNING** level and the function returns *None*; no exception propagates
   to the caller.

Example
-------
```python
from ingenious.document_processing.utils.fetcher import fetch, is_url

url = "https://example.com/report.pdf"
if is_url(url):
    payload = fetch(url)
    if payload is not None:
        process(payload)
```
"""

from __future__ import annotations

import contextlib
import os
import re
from typing import Final, Union

import requests

from ingenious.core.structured_logging import get_logger
from ingenious.errors.processing import (
    ErrorCode,
    ErrorContext,
    NetworkError,
)

__all__ = ["is_url", "fetch"]

logger = get_logger(__name__)

# --------------------------------------------------------------------------- #
# Configuration                                                               #
# --------------------------------------------------------------------------- #

#: Regex that recognises an absolute HTTP or HTTPS URL (case-insensitive).
_URL_RE: Final[re.Pattern[str]] = re.compile(r"^https?://", re.IGNORECASE)

#: Maximum payload size in **MiB** before the transfer is aborted.
_MAX_MB: Final[int] = int(os.getenv("INGEN_MAX_DOWNLOAD_MB", "20"))

#: Overall request timeout in **seconds**.
_TIMEOUT: Final[int] = int(os.getenv("INGEN_URL_TIMEOUT_SEC", "30"))


# --------------------------------------------------------------------------- #
# Public helpers                                                              #
# --------------------------------------------------------------------------- #
def is_url(src: Union[str, os.PathLike[str]]) -> bool:
    """
    Return *True* if *src* looks like an absolute HTTP/S URL.

    Parameters
    ----------
    src:
        A candidate string or :class:`pathlib.Path` identifying a resource.

    Notes
    -----
    The check is intentionally lightweight – it only validates the scheme
    prefix (``http://`` or ``https://``).  Callers must ensure the rest of
    the URL is well-formed.
    """
    return bool(_URL_RE.match(str(src)))


def fetch(url: str, raise_on_error: bool = False) -> bytes | None:
    """
    Download *url* defensively and return its raw bytes.

    Fail-soft contract
    ------------------
    * By default, never raises – any network/size error is logged and **None** is returned.
    * When raise_on_error=True, raises structured NetworkError exceptions.
    * Aborts early if the payload exceeds ``_MAX_MB`` MiB.

    Parameters
    ----------
    url : str
        Fully-qualified HTTP/S URL.
    raise_on_error : bool, default=False
        Whether to raise NetworkError exceptions instead of returning None.

    Returns
    -------
    bytes | None
        Raw response body on success, otherwise *None* (unless raise_on_error=True).

    Raises
    ------
    NetworkError
        When raise_on_error=True and a network operation fails.
    """
    resp: requests.Response | None = None  # pre-declare for finally
    try:
        resp = requests.get(url, timeout=_TIMEOUT, stream=True)
        resp.raise_for_status()

        # ── Fast guard via Content-Length header ──────────────────────────
        try:
            content_length = int(resp.headers.get("Content-Length", "0"))
        except ValueError:
            content_length = 0

        if content_length and content_length > (_MAX_MB << 20):
            if raise_on_error:
                context = ErrorContext(
                    url=url,
                    operation="size_check",
                    component="document_processing.network",
                )
                context.metadata["content_length_mb"] = content_length >> 20
                context.metadata["max_mb"] = _MAX_MB

                raise NetworkError(
                    f"Content size ({content_length >> 20} MB) exceeds limit ({_MAX_MB} MB) for {url}",
                    error_code=ErrorCode.DOWNLOAD_SIZE_EXCEEDED,
                    context=context,
                )

            logger.warning(
                "Content size exceeds limit, skipping download",
                url=url,
                max_mb=_MAX_MB,
                content_length_mb=content_length >> 20,
            )
            return None

        # ── Stream with incremental size check ────────────────────────────
        buffer = bytearray()
        for chunk in resp.iter_content(chunk_size=1 << 14):  # 16 KiB
            buffer.extend(chunk)
            if len(buffer) > (_MAX_MB << 20):
                if raise_on_error:
                    context = ErrorContext(
                        url=url,
                        operation="download",
                        component="document_processing.network",
                    )
                    context.metadata["current_size_mb"] = len(buffer) >> 20
                    context.metadata["max_mb"] = _MAX_MB

                    raise NetworkError(
                        f"Download size ({len(buffer) >> 20} MB) exceeds limit ({_MAX_MB} MB) for {url}",
                        error_code=ErrorCode.DOWNLOAD_SIZE_EXCEEDED,
                        context=context,
                    )

                logger.warning(
                    "Download size exceeds limit, aborting",
                    url=url,
                    max_mb=_MAX_MB,
                    current_size_mb=len(buffer) >> 20,
                )
                return None

        return bytes(buffer)

    except requests.Timeout as exc:
        if raise_on_error:
            context = ErrorContext(
                url=url, operation="download", component="document_processing.network"
            )
            context.metadata["timeout_seconds"] = _TIMEOUT

            raise NetworkError(
                f"Download timeout for {url}",
                error_code=ErrorCode.NETWORK_TIMEOUT,
                context=context,
                cause=exc,
            )

        logger.warning(
            "Download timeout",
            url=url,
            timeout_seconds=_TIMEOUT,
            error=str(exc),
        )
        return None

    except requests.ConnectionError as exc:
        if raise_on_error:
            raise NetworkError(
                f"Connection failed for {url}",
                error_code=ErrorCode.NETWORK_CONNECTION_FAILED,
                context=ErrorContext(
                    url=url,
                    operation="download",
                    component="document_processing.network",
                ),
                cause=exc,
            )

        logger.warning(
            "Connection failed",
            url=url,
            error=str(exc),
        )
        return None

    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response else None
        response_headers = dict(exc.response.headers) if exc.response else {}

        if raise_on_error:
            context = ErrorContext(
                url=url,
                operation="download",
                component="document_processing.network",
                status_code=status_code,
            )
            context.metadata["response_headers"] = response_headers

            raise NetworkError(
                f"HTTP error {status_code} for {url}",
                error_code=ErrorCode.HTTP_ERROR,
                context=context,
                cause=exc,
            )

        logger.warning(
            "HTTP error during download",
            url=url,
            status_code=status_code,
            error=str(exc),
        )
        return None

    except requests.RequestException as exc:
        if raise_on_error:
            raise NetworkError(
                f"Request failed for {url}",
                error_code=ErrorCode.NETWORK_CONNECTION_FAILED,
                context=ErrorContext(
                    url=url,
                    operation="download",
                    component="document_processing.network",
                ),
                cause=exc,
            )

        logger.warning(
            "Download failed",
            url=url,
            exception_type=exc.__class__.__name__,
            error=str(exc),
        )
        return None

    finally:
        # Always release the socket (real or stub); ignore any close errors.
        if resp is not None and hasattr(resp, "close"):
            with contextlib.suppress(Exception):
                resp.close()
