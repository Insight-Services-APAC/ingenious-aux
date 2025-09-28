"""
🧪 **Unit tests** for `ingenious.dataprep.crawl.crawler.Crawler`.

*Goal*: exercise the public façade (`scrape`, `batch`) **without a network**.
We keep the *real* `Crawler` class so its internal forwarding logic is covered,
but patch its low‑level helper `fetch_pages` with an in‑process fake to avoid
HTTP, API keys, or Scrapfly quota.
"""

from __future__ import annotations

# ───────────────────────────  third‑party / local imports  ───────────────────
from ingenious_docprep.dataprep.crawl import Crawler

# =========================================================================== #
# 1.  test_scrape_calls_fetch_pages
#     • Creates a fake `fetch_pages` that records its inputs.
#     • Instantiates Crawler(foo="bar") and calls .scrape("http://example.com").
#     • Asserts the wrapper forwarded exactly *one* URL and the kwargs.
# =========================================================================== #


def test_scrape_calls_fetch_pages(monkeypatch) -> None:  # noqa: D401
    """Verify `scrape` forwards one URL and all kwargs to `fetch_pages`."""

    # Dict used as a mutable ‘out parameter’ to capture values inside the stub.
    captured: dict[str, object] = {}

    # ----------------------------------------------------------------------
    # Stub implementation that *pretends* to be the real HTTP-layer helper.
    # It accepts the same positional + keyword signature but simply records
    # the arguments and returns a deterministic page payload.
    # ----------------------------------------------------------------------
    def _fake_fetch_pages(urls, **cfg):  # type: ignore[override]
        captured["urls"] = urls  # save list of URLs passed in
        captured["cfg"] = cfg  # save any extra kwargs (cfg)
        # Return a list with one synthetic page record so the caller proceeds.
        return [{"url": urls[0], "content": "fake content"}]

    # ----------------------------------------------------------------------
    # Monkey‑patch: replace *the exact symbol* the wrapper module imports.
    # • dotted path → the attribute inside the target module
    # • raising=True (default) → test fails loudly if the path is wrong,
    #   catching future refactors early.
    # ----------------------------------------------------------------------
    monkeypatch.setattr(
        "ingenious.dataprep.crawl.crawler.fetch_pages",
        _fake_fetch_pages,
    )

    # Instantiate the real wrapper; any kwargs should be transparently stored
    # and forwarded when we invoke .scrape().
    crawler = Crawler(foo="bar")

    # Act: call .scrape() with *one* URL. Under the hood this should execute
    # our fake helper exactly once.
    result = crawler.scrape("http://example.com")

    # ----------------------------------------------------------------------
    # Assertions – prove the wrapper behaved correctly.
    # ----------------------------------------------------------------------
    # 1️⃣  The synthetic payload is returned unchanged.
    assert result == {"url": "http://example.com", "content": "fake content"}

    # 2️⃣  Helper received a **one‑element list** – wrapper added no extras.
    assert captured["urls"] == ["http://example.com"]

    # 3️⃣  All kwargs supplied at construction time were forwarded verbatim.
    assert captured["cfg"] == {"foo": "bar"}


# =========================================================================== #
# 2.  test_batch_calls_fetch_pages
#     • Provides two URLs.
#     • Stub counts how many times it is called and echoes back pages.
#     • Asserts wrapper makes exactly one call and preserves order.
# =========================================================================== #


def test_batch_calls_fetch_pages(monkeypatch) -> None:  # noqa: D401
    """Ensure `batch` passes the full list and calls `fetch_pages` once."""

    call_count = {"n": 0}  # mutable int wrapped in dict for closure access

    def _fake_fetch_pages(urls, **_):  # type: ignore[override]
        # Increment counter so we can assert call frequency later.
        call_count["n"] += 1
        # Echo back a synthetic page for every URL.
        return [{"url": u, "content": "batch"} for u in urls]

    monkeypatch.setattr(
        "ingenious.dataprep.crawl.crawler.fetch_pages",
        _fake_fetch_pages,
    )

    # Two URLs to test order preservation.
    urls = ["http://a.com", "http://b.com"]

    pages = Crawler().batch(urls)

    # 1️⃣  Wrapper should have called helper exactly once.
    assert call_count["n"] == 1

    # 2️⃣  Output order must match input order – no re‑sorting occurred.
    assert [p["url"] for p in pages] == urls
