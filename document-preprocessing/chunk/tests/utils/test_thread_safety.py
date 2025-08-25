"""
Verifies thread safety of core chunking utility functions.

Purpose & Context:
    This test module ensures that helper functions within the `ingenious.chunk.utils`
    namespace are re-entrant and thread-safe. In the Insight Ingenious architecture,
    text processing and data preparation pipelines are often executed concurrently,
    either across multiple agents or within parallelized data ingestion flows. Core
    utilities like token counting (`token_len`) and overlap injection
    (`inject_overlap`) must be free of race conditions and shared mutable state to
    prevent data corruption or deadlocks under load.

Key Algorithms / Design Choices:
    The test employs a "smoke test" methodology using Python's
    `concurrent.futures.ThreadPoolExecutor`. It creates a pool of worker threads
    and simultaneously calls the target utility functions many times with varied
    inputs.

    The test's success condition is the absence of exceptions (e.g., `AttributeError`,
    `IndexError` from race conditions) or interpreter crashes during execution. It
    does not validate the specific return values, as coordinating this in a
    multi-threaded context is complex and not the primary goal. The focus is on
    verifying re-entrancy.
"""

import concurrent.futures
from pathlib import Path

from ingenious.chunk.utils.overlap import inject_overlap
from ingenious.chunk.utils.token_len import token_len


def _task(idx: int) -> None:
    """
    Represents a single unit of work for a worker thread in the smoke test.

    It generates unique text and calls the target utility functions to simulate
    a realistic workload.

    Args:
        idx: An integer index to ensure input text is unique for each task.
    """
    # Create text unique to this thread to avoid unintended caching effects.
    txt = f"lorem ipsum {idx} " * 40

    # Exercise the target utility functions.
    token_len(txt)
    inject_overlap([txt[:100], txt[100:]], k=5)


def test_helpers_thread_safe(tmp_path: Path) -> None:
    """
    Verifies that `token_len` and `inject_overlap` are thread-safe.

    Rationale:
        This test is crucial for ensuring system stability in concurrent
        environments, a core operational scenario for Insight Ingenious agents
        and data pipelines. It directly simulates high-throughput, multi-threaded
        access to the utility functions. The use of `ThreadPoolExecutor` is a
        standard and effective method for creating this load. The test is
        designed to pass if no exceptions are raised, confirming the functions'
        re-entrancy.

    Implementation Notes:
        - This is a smoke test that subjects the functions to concurrent execution.
        - It creates 16 worker threads and maps the `_task` function across 250
          iterations to generate significant concurrent load.
        - The test passes if it completes without deadlocking or raising an
          exception, which would indicate a thread-safety violation (e.g., a
          race condition related to global state in the tested functions).
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        # The list() constructor forces the lazy map iterator to be fully consumed,
        # which is a concise way to ensure we wait for all threads to complete
        # their execution before the `with` block exits.
        list(pool.map(_task, range(250)))
