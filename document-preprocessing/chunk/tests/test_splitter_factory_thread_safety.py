"""
Verifies thread-safety of the text splitter factory at standard and stress levels.

Purpose & Context:
This test module ensures the `ingenious.chunk.factory.build_splitter` function
is safe for concurrent use. In the Insight Ingenious architecture, document chunking
is a foundational step in ingestion pipelines, often executed in parallel by multiple
workers or agents. This test guarantees that the splitter factory, a critical shared
component, is free from race conditions and does not improperly share splitter
instances across threads.

Key Algorithms / Design Choices:
The test logic is parameterized to run in two modes:
1.  **Standard**: A quick check with a modest number of threads and tasks to ensure
    basic thread-safety.
2.  **Stress**: A high-contention scenario with many tasks and threads to uncover
    more subtle race conditions that might only appear under heavy load.

The test uses `concurrent.futures.ThreadPoolExecutor` to simulate these scenarios.
To ensure tests are fast and hermetic (i.e., isolated from external services),
it uses `unittest.mock.patch` to replace the `OpenAIEmbeddings` class. The core
validation asserts that the memory ID (`id()`) of every splitter instance created
by the factory is unique, providing direct proof of thread safety.
"""

import concurrent.futures
from unittest.mock import MagicMock, patch

import pytest

from ingenious.chunk.config import ChunkConfig
from ingenious.chunk.factory import build_splitter

# To use the `@pytest.mark.slow` marker, add the following to your pytest.ini:
# [pytest]
# markers =
#     slow: marks tests as slow to run


def _fake_embedder() -> MagicMock:
    """Creates a mock embedding object to avoid network I/O during tests.

    Rationale:
        The 'semantic' splitting strategy depends on an embedding model. Calling a
        real API (e.g., OpenAI) would make tests slow, network-dependent, and require
        API keys. This mock provides a fast and deterministic stand-in, allowing the
        test to focus solely on the factory's logic.

    Returns:
        MagicMock: A mock object configured to simulate the `embed_documents` method.
    """
    stub = MagicMock()
    stub.embed_documents.side_effect = lambda txts: [[0.0] * 5 for _ in txts]
    return stub


@pytest.mark.parametrize(
    "test_id, num_tasks, max_workers",
    [
        # A quick, standard check for basic thread-safety.
        ("standard", 32, 16),
        # A high-contention stress test to find subtle race conditions.
        pytest.param("stress", 2_000, 32, marks=pytest.mark.slow),
    ],
)
@patch(
    "ingenious.chunk.strategy.langchain_semantic.OpenAIEmbeddings",
    return_value=_fake_embedder(),
)
def test_splitter_factory_is_threadsafe(
    _: MagicMock, test_id: str, num_tasks: int, max_workers: int
) -> None:
    """Verifies build_splitter is thread-safe under standard and stress conditions.

    Rationale:
        This single, parameterized test covers both a basic concurrency check and a
        high-contention stress test. It ensures that the splitter factory provides
        each thread with a separate, independent instance, preventing state
        corruption and race conditions in a multi-threaded application.

    Args:
        _: The `MagicMock` object injected by the `@patch` decorator.
        test_id (str): The identifier for the test case ('standard' or 'stress').
        num_tasks (int): The total number of splitter build tasks to execute.
        max_workers (int): The number of concurrent threads to use in the pool.

    Raises:
        AssertionError: If splitter instances were shared across threads or if any
            of the concurrent tasks failed to produce text chunks.

    Implementation Notes:
        The function's behavior is controlled by the parameters supplied by pytest.
        It validates two critical post-conditions:
        1. All tasks completed successfully and produced a non-zero number of chunks.
        2. The memory ID of each splitter object is unique across all tasks.
    """
    STRATEGIES = ["recursive", "markdown", "token", "semantic"]

    def _task(idx: int) -> tuple[int, int]:
        """A single unit of work for the thread pool."""
        strategy = STRATEGIES[idx % len(STRATEGIES)]
        cfg = ChunkConfig(strategy=strategy, chunk_size=64, chunk_overlap=8)
        splitter = build_splitter(cfg)
        chunks = splitter.split_text("abc " * 50)
        return id(splitter), len(chunks)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        results = list(pool.map(_task, range(num_tasks)))

    # 1. Verify all tasks succeeded and produced chunks.
    assert all(count > 0 for _, count in results), "A task failed to produce chunks."

    # 2. Verify every splitter instance ID is unique, proving no sharing.
    splitter_ids = [sid for sid, _ in results]
    assert len(splitter_ids) == len(set(splitter_ids)), (
        "Splitter instances were shared across threads."
    )
